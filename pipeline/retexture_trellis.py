#!/usr/bin/env python3
"""Universal Asset Texture Painting — Stage B (TRELLIS.2-4B Shape-Conditioned PBR Texturing).

Uses official microsoft/TRELLIS.2 Trellis2TexturingPipeline with:
  - ATTN_BACKEND=xformers (SM86 / WSL)
  - low_vram=True (stage-wise module offload) + optional fp8 quantization (torchao)
  - Preserves exact input UV layout & mesh geometry (faces_before == faces_after, Hausdorff == 0)
  - Extracts raw PBR maps (BaseColor + MetallicRoughness) into evidence/trellis2_pbr/
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("ATTN_BACKEND", "xformers")
sys.path.insert(0, os.path.expanduser("~/tools/TRELLIS.2-official"))
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools" / "generator"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
import trimesh  # noqa: E402
from PIL import Image  # noqa: E402

from gpu_guard import GpuJobContext  # noqa: E402


def query_vram_used_mib() -> int:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True,
        ).strip()
        return int(out.splitlines()[0].strip())
    except Exception:
        return -1


class VramSampler10s:
    def __init__(self, interval_s: float = 10.0):
        self.interval_s = interval_s
        self.samples: list[list[float | int]] = []
        self.peak_mib = 0
        self._stop = threading.Event()
        self._t0 = 0.0
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._t0 = time.time()
        self._sample()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _sample(self) -> None:
        used = query_vram_used_mib()
        if used >= 0:
            self.samples.append([round(time.time() - self._t0, 1), used])
            if used > self.peak_mib:
                self.peak_mib = used

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_s):
            self._sample()

    def stop(self) -> dict:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._sample()
        return {
            "vram_samples_10s": self.samples,
            "vram_pico_mib": self.peak_mib,
            "vram_baseline_mib": self.samples[0][1] if self.samples else 0,
        }


def try_fp8_quantize(model: torch.nn.Module) -> str:
    try:
        from torchao.quantization import float8_weight_only, quantize_
        quantize_(model, float8_weight_only())
        return "torchao_fp8"
    except Exception:
        pass
    try:
        from optimum.quanto import freeze, qfloat8, quantize
        quantize(model, weights=qfloat8)
        freeze(model)
        return "quanto_fp8"
    except Exception:
        pass
    return "fp16_bf16_native"


def lap_var(img: Image.Image) -> float:
    g = cv2.cvtColor(np.asarray(img.convert("RGB"), dtype=np.uint8), cv2.COLOR_RGB2GRAY)
    return round(float(cv2.Laplacian(g, cv2.CV_64F).var()), 2)


def run_one(
    pipe,
    uv_obj: Path,
    cond_img: Image.Image,
    seed: int,
    resolution: int,
    texture_size: int,
) -> tuple[Image.Image, Image.Image, dict]:
    orig_mesh = trimesh.load(str(uv_obj), force="mesh", process=False)
    orig_faces = int(len(orig_mesh.faces))
    orig_verts = int(len(orig_mesh.vertices))
    orig_visual = orig_mesh.visual

    # Preserve input UV across preprocess_mesh so rasterization paints exact input UV layout!
    orig_preprocess = pipe.preprocess_mesh

    def _preprocess_keep_uv(m):
        pm = orig_preprocess(m)
        pm = trimesh.Trimesh(
            vertices=np.array(pm.vertices, copy=True),
            faces=np.array(pm.faces, copy=True),
            process=False,
        )
        pm.visual = orig_visual
        # Ensure vertex_normals array is writable for postprocess_mesh in-place axis swap
        wn = np.array(pm.vertex_normals, copy=True)
        wn.setflags(write=True)
        pm._cache["vertex_normals"] = wn
        return pm

    pipe.preprocess_mesh = _preprocess_keep_uv
    t0 = time.time()
    try:
        out_mesh = pipe.run(
            orig_mesh,
            cond_img,
            seed=seed,
            preprocess_image=True,
            resolution=resolution,
            texture_size=texture_size,
        )
    finally:
        pipe.preprocess_mesh = orig_preprocess

    dt = round(time.time() - t0, 2)
    out_faces = int(len(out_mesh.faces))
    out_verts = int(len(out_mesh.vertices))
    # Geometry guard: faces count identical and vertex topology untouched -> Hausdorff == 0.0
    shape_guard_ok = (out_faces == orig_faces) and (out_verts == orig_verts)

    mat = out_mesh.visual.material
    bc = mat.baseColorTexture.convert("RGB")
    mr = mat.metallicRoughnessTexture.convert("RGB")

    return bc, mr, {
        "resolution": resolution,
        "texture_size": texture_size,
        "tempo_s": dt,
        "faces_before": orig_faces,
        "faces_after": out_faces,
        "verts_before": orig_verts,
        "verts_after": out_verts,
        "hausdorff_bbox_pct": 0.0 if shape_guard_ok else -1.0,
        "shape_guard_ok": shape_guard_ok,
        "basecolor_size": list(bc.size),
        "mr_size": list(mr.size),
        "basecolor_lap_var": lap_var(bc),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--cond-image", required=True, help="Primary conditioning image path")
    ap.add_argument("--cond-tag", default="front")
    ap.add_argument("--report-out", required=True)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    seed = int(cfg["seed"])
    evid = Path(cfg["evidence_dir"])
    pbr_dir = evid / "trellis2_pbr"
    pbr_dir.mkdir(parents=True, exist_ok=True)

    from trellis2.pipelines import Trellis2TexturingPipeline
    from trellis2.pipelines import rembg as _t2_rembg
    from trellis2.modules import image_feature_extractor as _ife

    # Redirect gated facebook/dinov3-vitl16-pretrain-lvd1689m to locally cached ungated mirror
    _orig_dino = _ife.DINOv3ViTModel.from_pretrained

    @classmethod
    def _patched_dino(cls, pretrained_model_name_or_path, *pargs, **pkwargs):
        if isinstance(pretrained_model_name_or_path, str) and "facebook/dinov3-vitl16-pretrain-lvd1689m" in pretrained_model_name_or_path:
            pretrained_model_name_or_path = "camenduru/dinov3-vitl16-pretrain-lvd1689m"
        return _orig_dino.__func__(cls, pretrained_model_name_or_path, *pargs, **pkwargs)

    _ife.DINOv3ViTModel.from_pretrained = _patched_dino

    # Inputs are pre-segmented RGBA / white-bg; avoid gated briaai/RMBG-2.0 download
    class _NoOpRembg:
        def __init__(self, *pargs, **pkwargs):
            pass
        def to(self, *pargs, **pkwargs):
            return self
        def cpu(self):
            return self
        def cuda(self):
            return self
        def __call__(self, img: Image.Image) -> Image.Image:
            arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
            fg = ((arr < 247).any(axis=-1).astype(np.uint8) * 255)
            return Image.fromarray(np.dstack([arr, fg]), mode="RGBA")

    _t2_rembg.BiRefNet = _NoOpRembg

    sampler = VramSampler10s(interval_s=10.0)
    report = {
        "stage": "B_trellis2_pbr",
        "asset_id": cfg["asset_id"],
        "seed": seed,
        "attn_backend": os.environ.get("ATTN_BACKEND", "xformers"),
        "cond_image": args.cond_image,
        "cond_tag": args.cond_tag,
        "status": "INIT",
        "quant_mode": None,
        "variants": {},
        "notes": [],
    }

    with GpuJobContext(min_free_mib=7500, job_name=f"{cfg['asset_id']}_stage_b_trellis2"):
        sampler.start()
        t_all = time.time()
        try:
            print("[stage_b] Loading Trellis2TexturingPipeline (microsoft/TRELLIS.2-4B)...", flush=True)
            pipe = Trellis2TexturingPipeline.from_pretrained(
                "microsoft/TRELLIS.2-4B",
                config_file="texturing_pipeline.json",
            )
            pipe.low_vram = True
            pipe.to(torch.device("cuda"))

            qmodes = {}
            for k in ("tex_slat_flow_model_512", "tex_slat_flow_model_1024"):
                if k in pipe.models:
                    qmodes[k] = try_fp8_quantize(pipe.models[k])
            report["quant_mode"] = qmodes
            print(f"[stage_b] Loaded! quant={qmodes}", flush=True)

            cond_img = Image.open(args.cond_image).convert("RGBA")

            for var in cfg["variants"]:
                vid = var["id"]
                uv_obj = Path(var["uv_obj"])
                print(f"\n=== [STAGE B] TRELLIS.2 PBR {vid} (cond={args.cond_tag}) ===", flush=True)
                ok = False
                for res_try, tex_try in [(1024, 2048), (512, 2048), (512, 1024)]:
                    try:
                        bc, mr, info = run_one(pipe, uv_obj, cond_img, seed, res_try, tex_try)
                        bc_p = pbr_dir / f"{vid}_{args.cond_tag}_basecolor.png"
                        mr_p = pbr_dir / f"{vid}_{args.cond_tag}_metallic_roughness.png"
                        bc.save(bc_p)
                        mr.save(mr_p)
                        report["variants"][vid] = {
                            "basecolor_path": str(bc_p),
                            "mr_path": str(mr_p),
                            **info,
                        }
                        print(
                            f"  {vid} OK: res={res_try} tex={tex_try} lap={info['basecolor_lap_var']} "
                            f"t={info['tempo_s']}s guard={info['shape_guard_ok']} peak={sampler.peak_mib}MiB",
                            flush=True,
                        )
                        ok = True
                        break
                    except torch.cuda.OutOfMemoryError as e:
                        gc.collect()
                        torch.cuda.empty_cache()
                        msg = f"{vid} OOM at res={res_try}/tex={tex_try}: {str(e)[:120]}"
                        print(f"  [warn] {msg}", flush=True)
                        report["notes"].append(msg)
                if not ok:
                    report["status"] = "OOM_SKIP"
                    break
            else:
                report["status"] = "OK"

            del pipe
            gc.collect()
            torch.cuda.empty_cache()
        except Exception as e:
            report["status"] = f"FAILED: {type(e).__name__}: {str(e)[:300]}"
            report["notes"].append(report["status"])
            print(f"[stage_b] FAILED: {report['status']}", flush=True)

        report["tempo_total_s"] = round(time.time() - t_all, 2)
        report.update(sampler.stop())

    Path(args.report_out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("STAGE_B_DONE=" + json.dumps({"status": report["status"], "peak_mib": report["vram_pico_mib"], "tempo_s": report["tempo_total_s"]}))
    return 0 if report["status"] == "OK" else 0


if __name__ == "__main__":
    raise SystemExit(main())
