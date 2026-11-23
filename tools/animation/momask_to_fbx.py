#!/usr/bin/env python3
"""
tools/animation/momask_to_fbx.py — Pipeline reutilizavel MoMask (texto -> movimento) -> FBX Unity Humanoid 60 fps.
Parte da Lei 9 / ADR-012 (RUN mega_v6). 100% local, MIT License, guard de VRAM 10 GB, seed 42.

Uso (WSL):
  python3 tools/animation/momask_to_fbx.py \
      --prompt "a person walks forward naturally" \
      --name walk_natural --seed 42 --motion-length 80 --in-place \
      --out /caminho/walk_natural.fbx
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "generator"))
try:
    from gpu_guard import reclaim_windows_vram, resolve_min_free_mib
except Exception:
    reclaim_windows_vram = None
    def resolve_min_free_mib(x=None): return int(x or 10000)

MOMASK_DIR = Path(os.environ.get("MOMASK_DIR", str(Path.home() / "tools" / "momask-codes")))
MOMASK_PY = Path(os.environ.get("MOMASK_PY", str(Path.home() / ".venvs" / "momask" / "bin" / "python")))
BPY_PY = Path(os.environ.get("UNIRIG_PY", str(Path.home() / ".venvs" / "unirig" / "bin" / "python")))
BVH_CONVERTER = Path(__file__).resolve().parent / "bvh_to_humanoid_fbx.py"


def query_vram_mib() -> tuple[int, int]:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.free", "--format=csv,noheader,nounits"],
            text=True, timeout=5,
        ).strip().splitlines()[0]
        u, f = [int(x.strip()) for x in out.split(",")]
        return u, f
    except Exception:
        return -1, -1


class VramMonitor:
    def __init__(self, limit_mib: int = 10000):
        self.limit_mib = limit_mib
        self.peak_mib = 0
        self.breached = False
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)

    def start(self): self._t.start()
    def _run(self):
        while not self._stop.is_set():
            u, _ = query_vram_mib()
            if u > self.peak_mib: self.peak_mib = u
            if u > self.limit_mib: self.breached = True
            self._stop.wait(1.0)
    def stop(self):
        self._stop.set()
        self._t.join(timeout=2.0)


def main() -> None:
    ap = argparse.ArgumentParser(description="MoMask -> FBX Unity Humanoid 60 fps (ADR-012 / Lei 9)")
    ap.add_argument("--prompt", required=True, help="Prompt em ingles descrevendo o movimento")
    ap.add_argument("--name", required=True, help="Slug do clip (ex.: dez_walk_loop)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--motion-length", type=int, default=80, help="Frames a 20 fps (80 = 4.0s)")
    ap.add_argument("--fps", type=int, default=60, help="FPS alvo do FBX (padrao 60)")
    ap.add_argument("--in-place", action="store_true", help="Remove deslocamento XZ da raiz")
    ap.add_argument("--out", required=True, help="Caminho .fbx de saida")
    ap.add_argument("--vram-limit", type=int, default=10000)
    args = ap.parse_args()

    out_fbx = Path(args.out).resolve()
    out_fbx.parent.mkdir(parents=True, exist_ok=True)

    if reclaim_windows_vram:
        try: reclaim_windows_vram()
        except Exception: pass
    used, free = query_vram_mib()
    min_free = min(9000, resolve_min_free_mib())
    if 0 <= free < min_free:
        raise RuntimeError(f"VRAM insuficiente: free={free} MiB < {min_free} MiB")

    ext_name = f"mega_v6_{args.name}_s{args.seed}"
    gen_dir = MOMASK_DIR / "generation" / ext_name
    if gen_dir.exists():
        shutil.rmtree(gen_dir)

    cmd_momask = [
        str(MOMASK_PY), "gen_t2m.py",
        "--gpu_id", "0",
        "--ext", ext_name,
        "--text_prompt", args.prompt,
        "--motion_length", str(args.motion_length),
        "--repeat_times", "1",
        "--seed", str(args.seed),
    ]

    mon = VramMonitor(limit_mib=args.vram_limit)
    mon.start()
    t0 = time.time()
    try:
        print(f"[momask_to_fbx] 1/2 Gerando movimento MoMask: '{args.prompt}' (seed={args.seed}, len={args.motion_length})...", flush=True)
        res = subprocess.run(cmd_momask, cwd=str(MOMASK_DIR), capture_output=True, text=True)
        bvhs_check = sorted(gen_dir.rglob("*_ik.bvh"))
        if res.returncode != 0 and not bvhs_check:
            print(res.stdout[-2000:])
            print(res.stderr[-2000:])
            raise RuntimeError(f"Falha no MoMask gen_t2m.py (exit {res.returncode})")
        elif res.returncode != 0 and bvhs_check:
            print(f"[momask_to_fbx] AVISO: plot_3d_motion (matplotlib) retornou {res.returncode}, mas BVH com foot-IK foi gerado com sucesso ({bvhs_check[0].name}).", flush=True)
    finally:
        t_gen = round(time.time() - t0, 2)
        mon.stop()

    bvhs = sorted(gen_dir.rglob("*_ik.bvh"))
    if not bvhs:
        raise FileNotFoundError(f"Nenhum *_ik.bvh gerado em {gen_dir}")
    bvh_path = bvhs[0]

    # Copia BVH ao lado para rastreabilidade
    bvh_copy = out_fbx.with_suffix(".bvh")
    shutil.copy2(bvh_path, bvh_copy)

    print(f"[momask_to_fbx] 2/2 Convertendo BVH -> FBX Humanoid {args.fps}fps ({bvh_path.name})...", flush=True)
    cmd_bpy = [
        str(BPY_PY), str(BVH_CONVERTER),
        "--input", str(bvh_copy),
        "--output", str(out_fbx),
        "--target-fps", str(args.fps),
        "--src-fps", "20",
        "--clip-name", args.name,
    ]
    if args.in_place:
        cmd_bpy.append("--in-place")
    res_bpy = subprocess.run(cmd_bpy, capture_output=True, text=True)
    print(res_bpy.stdout[-1500:])
    if res_bpy.returncode != 0:
        print(res_bpy.stderr[-1500:])
        raise RuntimeError(f"Falha na conversao BVH->FBX (exit {res_bpy.returncode})")

    prov = {
        "runner": "3dprinter-setup-ia/tools/animation/momask_to_fbx.py",
        "model": "MoMask (t2m_nlayer8_nhead6_ld384_ff1024_cdp0.1_rvq6ns)",
        "license": "MIT (code) / HumanML3D checkpoints (same policy as FLUX-dev, ADR-012)",
        "name": args.name,
        "prompt": args.prompt,
        "seed": args.seed,
        "src_frames_20fps": args.motion_length,
        "target_fps": args.fps,
        "in_place": args.in_place,
        "bvh_path": str(bvh_copy),
        "fbx_path": str(out_fbx),
        "fbx_bytes": out_fbx.stat().st_size if out_fbx.exists() else 0,
        "elapsed_gen_sec": t_gen,
        "peak_vram_mib": mon.peak_mib,
        "vram_guard_mib": args.vram_limit,
        "guard_ok": not mon.breached,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    out_fbx.with_suffix(".provenance.json").write_text(json.dumps(prov, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[momask_to_fbx] CONCLUIDO: {out_fbx} ({prov['fbx_bytes']} bytes) | gen={t_gen}s | peak_vram={mon.peak_mib} MiB (guard_ok={prov['guard_ok']})", flush=True)


if __name__ == "__main__":
    main()
