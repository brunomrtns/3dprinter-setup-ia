#!/usr/bin/env python3
"""
tools/generator/concept_flux.py — Runner headless ComfyUI + FLUX.1-dev FP8 (ADR-010 / RUN mega_v4).

Gera conceitos 2D de alta aderência ao prompt via ComfyUI headless (`--lowvram`, offload automático)
sob guard de VRAM (10.000 MiB na RTX 3060 12 GB) + logger de VRAM 1 Hz + provenance JSON com SHA-256.

Uso (single):
  ~/.venvs/comfyui/bin/python tools/generator/concept_flux.py \
      --prompt "..." --seed 42 --size 768 --steps 20 --out /caminho/saida.png

Uso (batch, 1 único boot do ComfyUI):
  ~/.venvs/comfyui/bin/python tools/generator/concept_flux.py --batch-json jobs.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "generator"))
try:
    from gpu_guard import reclaim_windows_vram, resolve_min_free_mib
except Exception:
    reclaim_windows_vram = None
    def resolve_min_free_mib(x=None): return int(x or 10000)

DEFAULT_COMFY_DIR = Path(os.environ.get("COMFYUI_DIR", str(Path.home() / "tools" / "comfyui")))
DEFAULT_COMFY_PY = Path(os.environ.get("COMFYUI_PY", str(Path.home() / ".venvs" / "comfyui" / "bin" / "python")))
DEFAULT_CKPT = "flux1-dev-fp8.safetensors"


def query_vram_mib() -> tuple[int, int]:
    """Retorna (used_mib, free_mib) via nvidia-smi."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.free", "--format=csv,noheader,nounits"],
            text=True,
            timeout=5,
        ).strip().splitlines()[0]
        used, free = [int(x.strip()) for x in out.split(",")]
        return used, free
    except Exception:
        return -1, -1


class VramMonitor:
    def __init__(self, limit_mib: int = 10000):
        self.limit_mib = limit_mib
        self.peak_used_mib = 0
        self.min_free_mib = 999999
        self.guard_breached = False
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            used, free = query_vram_mib()
            if used > self.peak_used_mib:
                self.peak_used_mib = used
            if 0 <= free < self.min_free_mib:
                self.min_free_mib = free
            if used > self.limit_mib:
                self.guard_breached = True
            self._stop.wait(1.0)

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)


def wait_for_gpu_ready(min_free_mib: int, timeout_s: int = 120) -> tuple[int, int]:
    if reclaim_windows_vram:
        try:
            reclaim_windows_vram()
        except Exception:
            pass
    t0 = time.time()
    while True:
        used, free = query_vram_mib()
        if free >= min_free_mib or free < 0:
            print(f"[concept_flux] GPU guard OK: used={used} MiB free={free} MiB (min_free={min_free_mib} MiB)", flush=True)
            return used, free
        if time.time() - t0 > timeout_s:
            raise RuntimeError(f"VRAM insuficiente apos {timeout_s}s: free={free} MiB < {min_free_mib} MiB")
        print(f"[concept_flux] Aguardando VRAM livre: {free}/{min_free_mib} MiB...", flush=True)
        time.sleep(2.0)


def get_ckpt_sha256(ckpt_path: Path) -> str:
    sidecar = Path(str(ckpt_path) + ".sha256")
    if sidecar.exists():
        txt = sidecar.read_text(encoding="utf-8").strip().split()
        if txt:
            return txt[0]
    h = hashlib.sha256()
    with ckpt_path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    digest = h.hexdigest()
    sidecar.write_text(f"{digest}  {ckpt_path.name}\n", encoding="utf-8")
    return digest


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def build_flux_workflow(
    ckpt_name: str,
    prompt: str,
    width: int,
    height: int,
    seed: int,
    steps: int,
    guidance: float,
    prefix: str,
) -> dict:
    """Workflow ComfyUI canonico para checkpoint all-in-one FLUX.1-dev FP8 / FLUX.1-schnell FP8."""
    return {
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": ckpt_name},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["4", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "", "clip": ["4", 1]},
        },
        "26": {
            "class_type": "FluxGuidance",
            "inputs": {"guidance": float(guidance), "conditioning": ["6", 0]},
        },
        "5": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": int(width), "height": int(height), "batch_size": 1},
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": int(seed),
                "steps": int(steps),
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["26", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": prefix, "images": ["8", 0]},
        },
    }


def http_json(url: str, data: dict | None = None, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8") if data is not None else None,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def start_comfy_server(comfy_dir: Path, comfy_py: Path, port: int, extra_args: list[str]) -> subprocess.Popen:
    cmd = [
        str(comfy_py),
        str(comfy_dir / "main.py"),
        "--listen", "127.0.0.1",
        "--port", str(port),
        "--lowvram",
        "--reserve-vram", "3.5",
        "--disable-auto-launch",
        *extra_args,
    ]
    print(f"[concept_flux] Subindo ComfyUI headless na porta {port} (--lowvram --reserve-vram 3.5)...", flush=True)
    proc = subprocess.Popen(cmd, cwd=str(comfy_dir), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    base = f"http://127.0.0.1:{port}"
    for _ in range(90):
        if proc.poll() is not None:
            out = proc.stdout.read() if proc.stdout else ""
            raise RuntimeError(f"ComfyUI encerrou prematuramente (exit {proc.returncode}):\n{out[-1500:]}")
        try:
            http_json(f"{base}/system_stats", timeout=2)
            print(f"[concept_flux] ComfyUI pronto em {base}", flush=True)
            return proc
        except Exception:
            time.sleep(1.0)
    proc.terminate()
    raise RuntimeError("Timeout aguardando servidor ComfyUI headless responder.")


def run_one_job(
    base_url: str,
    comfy_dir: Path,
    ckpt_name: str,
    ckpt_sha256: str,
    job: dict,
    vram_limit_mib: int,
) -> dict:
    prompt = job["prompt"]
    seed = int(job.get("seed", 42))
    width = int(job.get("width", job.get("size", 768)))
    height = int(job.get("height", job.get("size", 768)))
    steps = int(job.get("steps", 20))
    guidance = float(job.get("guidance", 3.5))
    out_path = Path(job["out"])
    out_path.parent.mkdir(parents=True, exist_ok=True)

    prefix = f"flux_{uuid.uuid4().hex[:8]}"
    wf = build_flux_workflow(ckpt_name, prompt, width, height, seed, steps, guidance, prefix)

    mon = VramMonitor(limit_mib=vram_limit_mib)
    mon.start()
    t0 = time.time()
    try:
        resp = http_json(f"{base_url}/prompt", {"prompt": wf, "client_id": "concept_flux"})
        pid = resp["prompt_id"]
        while True:
            hist = http_json(f"{base_url}/history/{pid}", timeout=10)
            if pid in hist:
                entry = hist[pid]
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise RuntimeError(f"Erro no workflow ComfyUI: {status}")
                outputs = entry.get("outputs", {})
                if "9" in outputs and outputs["9"].get("images"):
                    img_info = outputs["9"]["images"][0]
                    src = comfy_dir / "output" / img_info.get("subfolder", "") / img_info["filename"]
                    shutil.copy2(src, out_path)
                    try:
                        src.unlink()
                    except OSError:
                        pass
                    break
            time.sleep(1.0)
    finally:
        elapsed = round(time.time() - t0, 2)
        mon.stop()

    prov = {
        "runner": "3dprinter-setup-ia/tools/generator/concept_flux.py",
        "backend": "ComfyUI headless (--lowvram)",
        "model": ckpt_name.replace(".safetensors", ""),
        "weights_file": str(comfy_dir / "models" / "checkpoints" / ckpt_name),
        "weights_sha256": ckpt_sha256,
        "license_note": "FLUX.1-dev = BFL non-commercial (personal/vertical-slice OK; migrate to FLUX.1-schnell Apache 2.0 or BFL license for commercial release)",
        "seed": seed,
        "width": width,
        "height": height,
        "steps": steps,
        "guidance": guidance,
        "prompt": prompt,
        "output_png": str(out_path),
        "elapsed_sec": elapsed,
        "peak_vram_mib": mon.peak_used_mib,
        "vram_guard_mib": vram_limit_mib,
        "guard_ok": not mon.guard_breached,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    prov_path = out_path.with_suffix(".provenance.json")
    prov_path.write_text(json.dumps(prov, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"[concept_flux] OK {out_path.name} | {elapsed}s | peak_vram={mon.peak_used_mib} MiB "
        f"(guard {vram_limit_mib} MiB: {'PASS' if prov['guard_ok'] else 'BREACHED'})",
        flush=True,
    )
    return prov


def main() -> None:
    ap = argparse.ArgumentParser(description="Runner headless ComfyUI + FLUX.1-dev FP8")
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--size", type=int, default=768)
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--height", type=int, default=None)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--guidance", type=float, default=3.5)
    ap.add_argument("--ckpt", default=DEFAULT_CKPT)
    ap.add_argument("--out", default=None)
    ap.add_argument("--batch-json", default=None, help="JSON list of jobs [{prompt, seed, size/width/height, steps, guidance, out}]")
    ap.add_argument("--vram-limit", type=int, default=10000)
    ap.add_argument("--comfy-dir", default=str(DEFAULT_COMFY_DIR))
    ap.add_argument("--comfy-py", default=str(DEFAULT_COMFY_PY))
    args = ap.parse_args()

    comfy_dir = Path(args.comfy_dir)
    comfy_py = Path(args.comfy_py)
    ckpt_path = comfy_dir / "models" / "checkpoints" / args.ckpt
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Checkpoint nao encontrado: {ckpt_path}")

    if args.batch_json:
        jobs = json.loads(Path(args.batch_json).read_text(encoding="utf-8"))
    else:
        if not args.prompt or not args.out:
            ap.error("Informe --prompt e --out, ou --batch-json")
        jobs = [{
            "prompt": args.prompt,
            "seed": args.seed,
            "width": args.width or args.size,
            "height": args.height or args.size,
            "steps": args.steps,
            "guidance": args.guidance,
            "out": args.out,
        }]

    ckpt_sha = get_ckpt_sha256(ckpt_path)
    wait_for_gpu_ready(min_free_mib=min(9000, resolve_min_free_mib()))

    port = find_free_port()
    proc = start_comfy_server(comfy_dir, comfy_py, port, extra_args=[])
    base_url = f"http://127.0.0.1:{port}"
    results = []
    try:
        for j in jobs:
            results.append(run_one_job(base_url, comfy_dir, args.ckpt, ckpt_sha, j, args.vram_limit))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        time.sleep(1.5)
        used, free = query_vram_mib()
        print(f"[concept_flux] ComfyUI encerrado. VRAM pos-run: used={used} MiB free={free} MiB", flush=True)

    print("REPORT_JSON:" + json.dumps(results if args.batch_json else results[0], ensure_ascii=False))


if __name__ == "__main__":
    main()
