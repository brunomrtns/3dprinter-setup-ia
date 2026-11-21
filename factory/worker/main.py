#!/usr/bin/env python3
"""M3 — Fábrica 3D Local Worker (Python, outbound-only HTTP to VPS).

Loop: heartbeat -> poll/claim -> download inputs -> generate assets/<job>.json ->
run pipeline/run_asset.py (seed 42, gpu_guard, VRAM 10s, --resume) -> upload results -> review.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import httpx

WORKER_DIR = Path(__file__).resolve().parent
REPO_ROOT = WORKER_DIR.parent.parent
HUNYUAN_PY = "/home/bruno/.venvs/hunyuan/bin/python"
sys.path.insert(0, str(WORKER_DIR))

from edit_agent import execute_edit_request  # noqa: E402
from image_assistant import analyze_input_quality  # noqa: E402


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def query_vram() -> tuple[int, int]:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.free", "--format=csv,noheader,nounits"],
            text=True,
        ).strip()
        u, f = out.splitlines()[0].split(",")
        return int(u.strip()), int(f.strip())
    except Exception:
        return 0, 0


class FactoryWorker:
    def __init__(self) -> None:
        load_dotenv(WORKER_DIR / ".env")
        self.vps_url = os.environ["VPS_URL"].rstrip("/")
        self.token = os.environ["WORKER_TOKEN"]
        self.worker_id = os.environ.get("WORKER_ID", "local-rtx3060-12gb")
        self.poll_sec = float(os.environ.get("POLL_INTERVAL_SEC", "10"))
        self.headers = {"x-worker-token": self.token}
        self.current_job_id: str | None = None
        self._stop = threading.Event()

    def send_heartbeat(self) -> None:
        used, free = query_vram()
        try:
            httpx.post(
                f"{self.vps_url}/api/fab3d/worker/heartbeat",
                headers=self.headers,
                json={
                    "workerId": self.worker_id,
                    "currentJobId": self.current_job_id,
                    "vramUsedMib": used,
                    "vramFreeMib": free,
                },
                timeout=15,
            )
        except Exception as e:
            print(f"[worker] heartbeat warn: {e}", flush=True)

    def _hb_loop(self) -> None:
        while not self._stop.wait(30.0):
            self.send_heartbeat()

    def report_progress(self, job_id: str, stage: str, progress: int, status: str = "running", error: str | None = None, metrics: dict | None = None) -> None:
        payload: dict[str, Any] = {"status": status, "stage": stage, "progress": progress}
        if error:
            payload["error"] = error
        if metrics:
            payload["metrics"] = metrics
        httpx.patch(
            f"{self.vps_url}/api/fab3d/worker/jobs/{job_id}/progress",
            headers=self.headers,
            json=payload,
            timeout=20,
        )

    def claim_next(self) -> dict[str, Any] | None:
        r = httpx.post(
            f"{self.vps_url}/api/fab3d/worker/claim",
            headers=self.headers,
            json={"workerId": self.worker_id},
            timeout=20,
        )
        r.raise_for_status()
        return r.json().get("job")

    def download_inputs(self, job: dict[str, Any], dest_dir: Path) -> list[Path]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for inp in job.get("inputs", []):
            out_p = dest_dir / inp["filename"]
            with httpx.stream(
                "GET",
                f"{self.vps_url}/api/fab3d/worker/jobs/{job['id']}/inputs/{inp['id']}",
                headers=self.headers,
                timeout=120,
            ) as resp:
                resp.raise_for_status()
                with out_p.open("wb") as f:
                    for chunk in resp.iter_bytes():
                        f.write(chunk)
            paths.append(out_p)
        return paths

    def _find_latest_local_glbs(self, asset_id: str) -> dict[str, Path]:
        """Locate the most recent 8k/4k GLBs produced locally for this asset (or any recent job)."""
        jobs_root = REPO_ROOT / "evidence" / "fase-p" / "worker_jobs"
        if not jobs_root.is_dir():
            return {}
        candidates = sorted(jobs_root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        for jdir in candidates:
            staged = jdir / "run" / "staged_models"
            if staged.is_dir():
                g8 = list(staged.glob("*_8k.glb"))
                g4 = list(staged.glob("*_4k.glb"))
                if g8 or g4:
                    out: dict[str, Path] = {}
                    if g8:
                        out["glb_8k"] = g8[0]
                    if g4:
                        out["glb_4k"] = g4[0]
                    return out
        return {}

    def process_edit_job(self, job: dict[str, Any]) -> None:
        jid = job["id"]
        evid_dir = REPO_ROOT / "evidence" / "fase-p" / "worker_jobs" / jid
        self.report_progress(jid, "edit", 20)
        source_glbs = self._find_latest_local_glbs(job["assetId"])
        res = execute_edit_request(
            user_prompt=job.get("prompt") or "",
            qa_summary=job.get("metricsJson") or {},
            job_workspace=evid_dir,
            evidence_dir=evid_dir,
            source_glbs=source_glbs,
        )
        produced = res.get("produced_glbs") or {}
        if produced:
            self.report_progress(jid, "pack", 85)
            files = []
            for var_key, fpath_str in produced.items():
                fp = Path(fpath_str)
                if fp.is_file():
                    files.append((var_key, (fp.name, fp.read_bytes(), "model/gltf-binary")))
            if files:
                r = httpx.post(
                    f"{self.vps_url}/api/fab3d/worker/jobs/{jid}/results",
                    headers=self.headers,
                    data={"qa_json": json.dumps({"edit_agent": res}, ensure_ascii=False)},
                    files=files,
                    timeout=300,
                )
                r.raise_for_status()

        tok_info = f" | Tokens: {res.get('tokens_used', 0)}" if res.get("tokens_used") else ""
        status_note = (
            "Nova versão 8K/4K enviada para sua revisão no Studio 3D!"
            if produced
            else "Nenhuma alteração foi aplicada ao modelo 3D (ação não suportada ou bloqueada)."
        )
        reply_text = (
            f"{res['summary']}\n"
            f"Modelo: {res.get('provider')} | Bloqueados: {res['blocked_count']}{tok_info}.\n"
            f"{status_note}"
        )
        httpx.post(
            f"{self.vps_url}/api/fab3d/worker/jobs/{jid}/chat_reply",
            headers=self.headers,
            json={"content": reply_text, "plan": res, "artifacts": {"evidence": str(evid_dir), "glbs": produced}},
            timeout=30,
        )
        if not produced:
            # Do NOT leave asset stuck in 'review' if no GLB was modified
            self.report_progress(jid, "qa", 100, status="rejected", metrics=res)

    def process_new_job(self, job: dict[str, Any]) -> None:
        jid = job["id"]
        asset = job["asset"]
        mode = job["mode"]
        evid_dir = REPO_ROOT / "evidence" / "fase-p" / "worker_jobs" / jid
        in_dir = evid_dir / "inputs"

        self.report_progress(jid, "preprocess", 10)
        in_paths = self.download_inputs(job, in_dir)
        if not in_paths:
            raise RuntimeError("Job sem arquivos de entrada")

        # M5 weak-input check on downloaded images
        img_paths = [p for p in in_paths if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
        mesh_paths = [p for p in in_paths if p.suffix.lower() in (".glb", ".gltf", ".obj", ".stl")]
        input_diags = [analyze_input_quality(p) for p in img_paths]

        # Determine mesh path: if user uploaded a mesh, use it; otherwise if Fox multi-photo test mesh exists or generate shape
        if mesh_paths:
            mesh_path = str(mesh_paths[0])
            tier = "photos" if len(img_paths) >= 3 else ("single" if len(img_paths) == 1 else "none")
        else:
            # Default mesh generation / reuse via existing pipeline
            # For multi-photo Fox validation, reuse clean mv_b uv.obj if notes specifies --base-mesh=<path>
            notes = asset.get("notes") or ""
            base_mesh = ""
            for tok in notes.split():
                if tok.startswith("base_mesh="):
                    base_mesh = tok.split("=", 1)[1]
            if base_mesh and Path(base_mesh).exists():
                mesh_path = base_mesh
            else:
                self.report_progress(jid, "shape", 20)
                gen_out = evid_dir / "shape_gen"
                gen_out.mkdir(parents=True, exist_ok=True)
                triposf_obj = gen_out / "2_triposf512" / "mesh_reconstruction.obj"
                if not triposf_obj.exists():
                    subprocess.run(
                        ["bash", str(REPO_ROOT / "tools" / "generator" / "pipeline_imagem3d.sh"), str(img_paths[0]), str(gen_out), "42"],
                        check=True,
                    )
                if triposf_obj.exists():
                    mesh_path = str(triposf_obj)
                else:
                    cands = list(gen_out.rglob("*.obj")) + list(gen_out.rglob("*.glb"))
                    if not cands:
                        raise RuntimeError("Geração de malha não produziu .obj/.glb")
                    mesh_path = str(cands[0])
            tier = "photos" if mode == "multi" and len(img_paths) >= 3 else ("single" if img_paths else "none")

        # Build asset config JSON from pipeline/defaults.json schema
        job_cfg = {
            "id": f"job_{jid[:8]}",
            "variant_id": "pbr",
            "mesh": mesh_path,
            "uv": mesh_path,
            "tier": tier,
            "input_images": [str(p) for p in img_paths],
            "outputs": {
                "mode_8k": "pbr_8k",
                "mode_4k": "pbr_4k",
                "glb_names": [f"job_{jid[:8]}__pbr_8k.glb", f"job_{jid[:8]}__pbr_4k.glb"],
            },
            "qa": {"lap_min": 1000.0, "patch_max_pct": 0.10},
            "notes": f"Auto-generated by factory/worker for job {jid}",
        }
        if tier == "photos" and len(img_paths) >= 4:
            job_cfg["photo_blend"] = {
                "views": [
                    {"name": "front", "image": str(img_paths[0]), "init_yaw_deg": 0.0, "init_pitch_deg": 0.0},
                    {"name": "left",  "image": str(img_paths[1]), "init_yaw_deg": -90.0, "init_pitch_deg": 0.0},
                    {"name": "back",  "image": str(img_paths[2]), "init_yaw_deg": 180.0, "init_pitch_deg": 0.0},
                    {"name": "right", "image": str(img_paths[3]), "init_yaw_deg": 90.0, "init_pitch_deg": 0.0},
                ]
            }

        cfg_path = evid_dir / "job_asset.json"
        cfg_path.write_text(json.dumps(job_cfg, indent=2, ensure_ascii=False), encoding="utf-8")

        self.report_progress(jid, "paint", 35, metrics={"input_diagnostics": input_diags})
        subprocess.run(
            [
                HUNYUAN_PY,
                str(REPO_ROOT / "pipeline" / "run_asset.py"),
                "--config", str(cfg_path),
                "--out", str(evid_dir / "run"),
                "--resume",
            ],
            check=True,
        )

        # Upload GLB 8K/4K + renders + qa.json -> VPS MinIO (enters 'review', never auto-publishes!)
        self.report_progress(jid, "pack", 90)
        run_dir = evid_dir / "run"
        qa_p = run_dir / "qa.json"
        qa_txt = qa_p.read_text(encoding="utf-8") if qa_p.exists() else "{}"
        glb_8k = run_dir / "staged_models" / f"job_{jid[:8]}__pbr_8k.glb"
        glb_4k = run_dir / "staged_models" / f"job_{jid[:8]}__pbr_4k.glb"
        render_34 = run_dir / "renders" / "final" / "pbr_final_three_quarter_front.png"

        files = []
        if glb_8k.exists():
            files.append(("glb_8k", (glb_8k.name, glb_8k.read_bytes(), "model/gltf-binary")))
        if glb_4k.exists():
            files.append(("glb_4k", (glb_4k.name, glb_4k.read_bytes(), "model/gltf-binary")))
        if render_34.exists():
            files.append(("thumbnail", (render_34.name, render_34.read_bytes(), "image/png")))

        r = httpx.post(
            f"{self.vps_url}/api/fab3d/worker/jobs/{jid}/results",
            headers=self.headers,
            data={"qa_json": qa_txt},
            files=files,
            timeout=300,
        )
        r.raise_for_status()
        print(f"[worker] Job {jid} uploaded -> status=review", flush=True)

    def run(self, once: bool = False) -> int:
        self.send_heartbeat()
        hb_thread = threading.Thread(target=self._hb_loop, daemon=True)
        hb_thread.start()
        try:
            while True:
                try:
                    job = self.claim_next()
                except Exception as e:
                    print(f"[worker] claim warn (retrying in {self.poll_sec}s): {e}", flush=True)
                    if once:
                        return 1
                    time.sleep(self.poll_sec)
                    continue
                if not job:
                    if once:
                        print("[worker] No queued jobs (--once exiting).", flush=True)
                        return 0
                    time.sleep(self.poll_sec)
                    continue

                self.current_job_id = job["id"]
                print(f"[worker] Claimed job {job['id']} (type={job['type']}, mode={job['mode']})", flush=True)
                try:
                    if job["type"] == "edit":
                        self.process_edit_job(job)
                    else:
                        self.process_new_job(job)
                except Exception as e:
                    print(f"[worker] Job {job['id']} FAILED: {e}", flush=True)
                    self.report_progress(job["id"], job.get("stage", "paint"), 0, status="failed", error=str(e)[:400])
                finally:
                    self.current_job_id = None
                    self.send_heartbeat()

                if once:
                    return 0
        finally:
            self._stop.set()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="Process at most 1 queued job and exit")
    args = ap.parse_args()
    raise SystemExit(FactoryWorker().run(once=args.once))
