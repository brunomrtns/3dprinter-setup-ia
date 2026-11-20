#!/usr/bin/env python3
"""Universal Asset Texture Painting — Stage A (Hunyuan3D-Paint v2-0 native 2048 + per-view SR).

Generic, asset-agnostic pipeline driven strictly by --config <asset.json>.
Preserves input mesh geometry and UV layout verbatim (no UV re-wrapping).
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault(
    "PYTORCH_CUDA_ALLOC_CONF",
    "expandable_segments:True,garbage_collection_threshold:0.65,max_split_size_mb:128",
)

HY2_HOME = os.path.expanduser("~/tools/Hunyuan3D-2")
sys.path.insert(0, HY2_HOME)
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools" / "generator"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from scipy.ndimage import distance_transform_edt  # noqa: E402
import torch  # noqa: E402
import trimesh  # noqa: E402
from huggingface_hub import snapshot_download  # noqa: E402
from PIL import Image  # noqa: E402

from gpu_guard import GpuJobContext  # noqa: E402
from upscale_and_pack_fox import RRDBNet, upscale_tiled  # noqa: E402


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


def seed_all(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def laplacian_variance(img: Image.Image) -> float:
    gray = cv2.cvtColor(np.asarray(img.convert("RGB"), dtype=np.uint8), cv2.COLOR_RGB2GRAY)
    return round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 2)


def hsv_sat_pct(img: Image.Image) -> float:
    hsv = cv2.cvtColor(np.asarray(img.convert("RGB"), dtype=np.uint8), cv2.COLOR_RGB2HSV)
    return round(float(hsv[..., 1].astype(np.float32).mean() / 255.0 * 100.0), 3)


def ensure_weights() -> tuple[str, str]:
    p_delight = snapshot_download(
        repo_id="tencent/Hunyuan3D-2",
        allow_patterns=["hunyuan3d-delight-v2-0/*"],
    )
    p_paint = snapshot_download(
        repo_id="tencent/Hunyuan3D-2",
        allow_patterns=["hunyuan3d-paint-v2-0/*"],
    )
    return (
        os.path.join(p_delight, "hunyuan3d-delight-v2-0"),
        os.path.join(p_paint, "hunyuan3d-paint-v2-0"),
    )


def run_delight(delight_ckpt: str, ref_paths: list[Path], cache_dir: Path, seed: int) -> list[Image.Image]:
    cache_paths = [cache_dir / f"delight_{rp.stem}.png" for rp in ref_paths]
    if all(cp.exists() for cp in cache_paths):
        print("[stage_a] Reusing cached delighted references.", flush=True)
        return [Image.open(cp).convert("RGB").resize((512, 512), Image.Resampling.LANCZOS) for cp in cache_paths]

    from diffusers import DiffusionPipeline, EulerAncestralDiscreteScheduler

    print(f"[stage_a] Running delight on {len(ref_paths)} references...", flush=True)
    pipe = DiffusionPipeline.from_pretrained(delight_ckpt, torch_dtype=torch.float16)
    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(
        pipe.scheduler.config, timestep_spacing="trailing"
    )
    pipe.set_progress_bar_config(disable=True)
    if hasattr(pipe, "enable_vae_slicing"):
        pipe.enable_vae_slicing()
    if hasattr(pipe, "enable_vae_tiling"):
        pipe.enable_vae_tiling()
    pipe.enable_model_cpu_offload()

    delighted = []
    with torch.inference_mode():
        for rp, cp in zip(ref_paths, cache_paths):
            im = Image.open(rp).convert("RGB").resize((512, 512), Image.Resampling.LANCZOS)
            gen = torch.Generator(device="cuda").manual_seed(seed)
            out = pipe(
                prompt="",
                image=im,
                generator=gen,
                num_inference_steps=50,
                image_guidance_scale=1.5,
                guidance_scale=1.0,
            ).images[0].resize((512, 512), Image.Resampling.LANCZOS)
            out.save(cp)
            delighted.append(out)
    pipe.to("cpu")
    del pipe
    gc.collect()
    torch.cuda.empty_cache()
    return delighted


def upscale_multiviews_sr(multiviews: list[Image.Image], target_size: int) -> list[Image.Image]:
    """Super-resolve synthesized 512px views -> 2048px with RealESRGAN_x4plus BEFORE back-projection."""
    weights_path = Path.home() / ".cache" / "realesrgan" / "RealESRGAN_x4plus.pth"
    if not weights_path.exists() or target_size <= 512:
        return [mv.resize((target_size, target_size), Image.Resampling.LANCZOS) for mv in multiviews]

    print(f"[stage_a] Per-view Real-ESRGAN x4 SR ({len(multiviews)} views -> {target_size}px)...", flush=True)
    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    ck = torch.load(str(weights_path), map_location="cpu", weights_only=True)
    sd = ck.get("params_ema", ck.get("params", ck))
    model.load_state_dict(sd, strict=True)
    model.eval().half().cuda()

    out_views = []
    for mv in multiviews:
        sr = upscale_tiled(model, mv, scale=4, tile_size=256, tile_pad=16, device="cuda")
        if sr.size != (target_size, target_size):
            sr = sr.resize((target_size, target_size), Image.Resampling.LANCZOS)
        out_views.append(sr)

    del model
    gc.collect()
    torch.cuda.empty_cache()
    return out_views


def apply_uv_island_gutter_bleed(
    mesh: trimesh.Trimesh,
    tex_rgb: np.ndarray,
    valid_mask: np.ndarray,
    gutter_px: int = 24,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Per-island UV flood + Voronoi gutter bleed BEFORE uv_inpaint (zero cross-island bleed).

    1. Rasterizes UV triangles to find connected UV islands.
    2. Fills uncovered texels INSIDE each island strictly from that island's own valid texels
       (iterative masked dilation so colors never cross island boundaries).
    3. Floods each island's own color outward up to `gutter_px` via exact Voronoi EDT.
    """
    h, w, _ = tex_rgb.shape
    uv = getattr(mesh.visual, "uv", None)
    if uv is None or len(uv) != len(mesh.vertices):
        return tex_rgb, valid_mask, 0

    uv_px = np.empty_like(uv, dtype=np.float32)
    uv_px[:, 0] = np.clip(uv[:, 0], 0.0, 1.0) * (w - 1)
    uv_px[:, 1] = (1.0 - np.clip(uv[:, 1], 0.0, 1.0)) * (h - 1)
    tris = np.round(uv_px[np.asarray(mesh.faces, dtype=np.int32)]).astype(np.int32)

    uv_mask = np.zeros((h, w), dtype=np.uint8)
    for tri in tris:
        cv2.fillConvexPoly(uv_mask, tri, 255)

    num_labels, labels = cv2.connectedComponents(uv_mask, connectivity=4)
    num_islands = max(0, int(num_labels) - 1)

    out = tex_rgb.copy()
    filled = (valid_mask > 0) & (uv_mask > 0)

    # Step 1: Intra-island fill (strictly respects island ID, never crosses islands)
    k3 = np.ones((3, 3), dtype=np.uint8)
    unfilled_inside = (uv_mask > 0) & (~filled)
    if unfilled_inside.any():
        # Fast 8-neighbor propagation restricted to matching island label
        shifts = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
        for _ in range(max(16, gutter_px)):
            if not unfilled_inside.any():
                break
            newly_filled = np.zeros((h, w), dtype=bool)
            acc = np.zeros((h, w, 3), dtype=np.float32)
            cnt = np.zeros((h, w), dtype=np.float32)
            for dy, dx in shifts:
                src_y0 = max(0, -dy)
                src_y1 = h - max(0, dy)
                src_x0 = max(0, -dx)
                src_x1 = w - max(0, dx)
                dst_y0 = max(0, dy)
                dst_y1 = h - max(0, -dy)
                dst_x0 = max(0, dx)
                dst_x1 = w - max(0, -dx)

                same_isl = (
                    unfilled_inside[dst_y0:dst_y1, dst_x0:dst_x1]
                    & filled[src_y0:src_y1, src_x0:src_x1]
                    & (labels[dst_y0:dst_y1, dst_x0:dst_x1] == labels[src_y0:src_y1, src_x0:src_x1])
                )
                if same_isl.any():
                    acc_slice = acc[dst_y0:dst_y1, dst_x0:dst_x1]
                    cnt_slice = cnt[dst_y0:dst_y1, dst_x0:dst_x1]
                    acc_slice[same_isl] += out[src_y0:src_y1, src_x0:src_x1][same_isl]
                    cnt_slice[same_isl] += 1.0
                    newly_filled[dst_y0:dst_y1, dst_x0:dst_x1] |= same_isl
            if not newly_filled.any():
                break
            out[newly_filled] = np.clip(
                np.round(acc[newly_filled] / cnt[newly_filled][..., None]), 0, 255
            ).astype(np.uint8)
            filled |= newly_filled
            unfilled_inside &= ~newly_filled

    # Step 2: Outward gutter bleed (exact Voronoi EDT up to gutter_px outside islands)
    if filled.any() and gutter_px > 0:
        dist, idx = distance_transform_edt(~filled, return_indices=True)
        gutter = (~filled) & (dist <= float(gutter_px))
        if gutter.any():
            out[gutter] = out[idx[0][gutter], idx[1][gutter]]
            filled |= gutter

    return out, (filled.astype(np.uint8) * 255), num_islands


def paint_variant(
    uv_obj_path: Path,
    delighted_imgs: list[Image.Image],
    paint_ckpt: str,
    paint_cfg: dict,
    seed: int,
    tex_size: int,
) -> tuple[Image.Image, dict]:
    from diffusers import DiffusionPipeline, EulerAncestralDiscreteScheduler
    from hy3dgen.texgen.differentiable_renderer.mesh_render import MeshRender

    t0 = time.time()
    seed_all(seed)

    mesh = trimesh.load(str(uv_obj_path), force="mesh", process=False)
    camera_azims = paint_cfg["camera_azims"]
    camera_elevs = paint_cfg["camera_elevs"]
    view_weights = paint_cfg["view_weights"]
    num_steps = int(paint_cfg.get("num_inference_steps", 30))

    # Render normal/position maps at 512 (input to multiview diffusion)
    render_ctrl = MeshRender(default_resolution=512, texture_size=512)
    render_ctrl.load_mesh(mesh)
    normal_maps = [render_ctrl.render_normal(el, az, use_abs_coor=True, return_type="pl") for el, az in zip(camera_elevs, camera_azims)]
    position_maps = [render_ctrl.render_position(el, az, return_type="pl") for el, az in zip(camera_elevs, camera_azims)]
    del render_ctrl
    gc.collect()
    torch.cuda.empty_cache()

    camera_info = [
        (((az // 30) + 9) % 12) // {-20: 1, 0: 1, 20: 1, -90: 3, 90: 3}[el]
        + {-20: 0, 0: 12, 20: 24, -90: 36, 90: 40}[el]
        for az, el in zip(camera_azims, camera_elevs)
    ]

    custom_pipe_dir = os.path.join(HY2_HOME, "hy3dgen", "texgen", "hunyuanpaint")
    pipe = DiffusionPipeline.from_pretrained(
        paint_ckpt,
        custom_pipeline=custom_pipe_dir,
        torch_dtype=torch.float16,
    )
    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(
        pipe.scheduler.config, timestep_spacing="trailing"
    )
    pipe.set_progress_bar_config(disable=True)
    if hasattr(pipe, "enable_vae_slicing"):
        pipe.enable_vae_slicing()
    if hasattr(pipe, "enable_vae_tiling"):
        pipe.enable_vae_tiling()
    if hasattr(pipe, "enable_attention_slicing"):
        pipe.enable_attention_slicing(1)

    pipe.to("cuda")
    torch.cuda.empty_cache()
    orig_denoise = pipe.denoise

    def _staged_denoise(*args, **kwargs):
        pipe.vae.to("cpu")
        gc.collect()
        torch.cuda.empty_cache()
        out_lat = orig_denoise(*args, **kwargs)
        pipe.unet.to("cpu")
        gc.collect()
        torch.cuda.empty_cache()
        pipe.vae.to("cuda")
        return out_lat

    pipe.denoise = _staged_denoise

    control_images = [im.resize((512, 512)) for im in (normal_maps + position_maps)]
    num_view = len(camera_azims)
    normal_in = [[control_images[i] for i in range(num_view)]]
    pos_in = [[control_images[i + num_view] for i in range(num_view)]]
    ref_in = [im.resize((512, 512)) for im in delighted_imgs]

    with torch.inference_mode():
        gen = torch.Generator(device="cuda").manual_seed(seed)
        multiviews = pipe(
            ref_in,
            num_inference_steps=num_steps,
            generator=gen,
            width=512,
            height=512,
            num_in_batch=num_view,
            camera_info_gen=[camera_info],
            camera_info_ref=[[0, 3, 6, 9][: len(ref_in)]],
            normal_imgs=normal_in,
            position_imgs=pos_in,
        ).images

    pipe.denoise = orig_denoise
    del orig_denoise, _staged_denoise
    pipe.to("cpu")
    del pipe
    gc.collect()
    torch.cuda.empty_cache()
    print(f"  [stage_a] 6 multiviews generated (VRAM now {query_vram_used_mib()} MiB)", flush=True)

    # Per-view SR 512 -> tex_size (2048) BEFORE native back-projection & bake!
    mv_hires = upscale_multiviews_sr(multiviews, tex_size)

    render_bake = MeshRender(default_resolution=tex_size, texture_size=tex_size)
    render_bake.load_mesh(mesh)

    project_textures, project_weighted_cos = [], []
    for mv, el, az, wt in zip(mv_hires, camera_elevs, camera_azims, view_weights):
        ptex, pcos, _ = render_bake.back_project(mv, el, az)
        project_textures.append(ptex)
        project_weighted_cos.append(wt * (pcos ** 4))

    tex_t, trust_t = render_bake.fast_bake_texture(project_textures, project_weighted_cos)
    mask_np = ((trust_t > 1e-8).squeeze(-1).cpu().numpy() * 255).astype(np.uint8)
    raw_bake_np = np.clip((tex_t.detach().cpu().numpy() * 255.0), 0, 255).astype(np.uint8)

    gutter_px = int(paint_cfg.get("gutter_px", 24))
    bled_np, bled_mask, num_islands = apply_uv_island_gutter_bleed(mesh, raw_bake_np, mask_np, gutter_px=gutter_px)
    print(f"  [stage_a] UV gutter bleed: islands={num_islands}, gutter_px={gutter_px}", flush=True)

    # Run uv_inpaint only on any remaining uncovered background after per-island gutter bleed
    bled_t = torch.from_numpy(bled_np.astype(np.float32) / 255.0).to(tex_t.device)
    tex_np = render_bake.uv_inpaint(bled_t, bled_mask)
    tex_img = Image.fromarray(np.clip(tex_np, 0, 255).astype(np.uint8), mode="RGB")

    del render_bake, tex_t, trust_t, bled_t, project_textures, project_weighted_cos
    gc.collect()
    torch.cuda.empty_cache()

    return tex_img, {
        "texture_size": tex_size,
        "per_view_sr": True,
        "num_uv_islands": num_islands,
        "gutter_px": gutter_px,
        "tempo_s": round(time.time() - t0, 2),
        "laplacian_var": laplacian_variance(tex_img),
        "sat_pct": hsv_sat_pct(tex_img),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    seed = int(cfg["seed"])
    evid = Path(cfg["evidence_dir"])
    out_dir = evid / "etapa_a"
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = evid / "delight_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    delight_ckpt, paint_ckpt = ensure_weights()
    ref_paths = [Path(p) for p in cfg["reference_images"]]
    paint_cfg = cfg["paint"]
    target_sz = int(paint_cfg.get("target_texture_size", 2048))
    fallback_sz = int(paint_cfg.get("fallback_texture_size", 1024))
    vram_limit = int(paint_cfg.get("vram_limit_mib", 11000))

    sampler = VramSampler10s(interval_s=10.0)
    report = {
        "stage": "A_hunyuan_native",
        "asset_id": cfg["asset_id"],
        "seed": seed,
        "target_texture_size": target_sz,
        "vram_limit_mib": vram_limit,
        "variants": {},
        "notes": [],
    }

    with GpuJobContext(min_free_mib=7500, job_name=f"{cfg['asset_id']}_stage_a"):
        sampler.start()
        t_all = time.time()
        delighted = run_delight(delight_ckpt, ref_paths, cache_dir, seed)

        for var in cfg["variants"]:
            vid = var["id"]
            uv_obj = Path(var["uv_obj"])
            print(f"\n=== [STAGE A] Painting {vid} (target={target_sz}) ===", flush=True)
            tex_img = None
            info = None
            try:
                tex_img, info = paint_variant(uv_obj, delighted, paint_ckpt, paint_cfg, seed, target_sz)
                if sampler.peak_mib > vram_limit:
                    msg = f"{vid}: peak VRAM {sampler.peak_mib} MiB > limit {vram_limit} MiB -> falling back to {fallback_sz}"
                    print(f"  [warn] {msg}", flush=True)
                    report["notes"].append(msg)
                    tex_img, info = paint_variant(uv_obj, delighted, paint_ckpt, paint_cfg, seed, fallback_sz)
            except torch.cuda.OutOfMemoryError as e:
                gc.collect()
                torch.cuda.empty_cache()
                msg = f"{vid}: OOM at {target_sz} ({str(e)[:100]}) -> falling back to {fallback_sz}"
                print(f"  [warn] {msg}", flush=True)
                report["notes"].append(msg)
                tex_img, info = paint_variant(uv_obj, delighted, paint_ckpt, paint_cfg, seed, fallback_sz)

            out_path = out_dir / f"{vid}_native_{info['texture_size']}.png"
            tex_img.save(out_path)
            report["variants"][vid] = {"texture_path": str(out_path), **info}
            print(
                f"  {vid} OK: tex={info['texture_size']} lap_var={info['laplacian_var']} "
                f"sat={info['sat_pct']}% t={info['tempo_s']}s peak={sampler.peak_mib}MiB",
                flush=True,
            )

        report["tempo_total_s"] = round(time.time() - t_all, 2)
        report.update(sampler.stop())

    (out_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("STAGE_A_OK=" + json.dumps({"peak_mib": report["vram_pico_mib"], "tempo_s": report["tempo_total_s"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
