#!/usr/bin/env python3
"""Universal Asset Texture Painting — Stage D (Quality Evaluation & Side-by-Side Crops).

Renders 6 views (front, back, left, right, top, three_quarter) in Blender with
Emission + view_transform='Standard' + look='None', computes:
  - Sharpness (Laplacian variance on texture and rendered views)
  - Defective bright-patch % (before vs final, using generic detector)
  - HSV saturation vs GT references across all views (both sides)
  - Side-by-side crops (BEFORE | FINAL) driven strictly by --config <asset.json>
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_fill_holes

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch_repair import detect_bright_patches_in_dark

BLENDER_RENDER_6VIEWS = r'''
import bpy, math, os, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
obj_path, tex_path, out_dir, prefix, res = argv[0], argv[1], argv[2], argv[3], int(argv[4])
os.makedirs(out_dir, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 1
scene.cycles.use_denoising = False
scene.render.resolution_x = res
scene.render.resolution_y = res
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.view_settings.exposure = 0.0

bpy.ops.wm.obj_import(filepath=obj_path)
objs = [o for o in scene.objects if o.type == "MESH"]
obj = objs[0]

mat = bpy.data.materials.new("EvalEmission")
mat.use_nodes = True
nt = mat.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputMaterial")
em = nt.nodes.new("ShaderNodeEmission")
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = bpy.data.images.load(tex_path)
tex.image.colorspace_settings.name = "sRGB"
nt.links.new(tex.outputs["Color"], em.inputs["Color"])
nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
obj.data.materials.clear()
obj.data.materials.append(mat)

# Compute world bbox
pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
center = (mn + mx) * 0.5
ext = mx - mn
max_dim = max(ext.x, ext.y, ext.z)

cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

# Canonical views: front (+Y or -Y matching eval_paint_4views), back, left, right, top, three_quarter
dist = max_dim * 2.5
views = {
    "front":         (Vector((0, -dist, 0)), True,  max_dim * 1.18),
    "back":          (Vector((0,  dist, 0)), True,  max_dim * 1.18),
    "left":          (Vector((-dist, 0, 0)), True,  max_dim * 1.18),
    "right":         (Vector(( dist, 0, 0)), True,  max_dim * 1.18),
    "top":           (Vector((0, 0,  dist)), True,  max_dim * 1.18),
    "three_quarter": (Vector((-dist * 0.65, -dist * 0.72, dist * 0.42)), False, 50.0),
}

for vname, (offset, is_ortho, scale_or_lens) in views.items():
    cam.location = center + offset
    direction = center - cam.location
    rot_quat = direction.to_track_quat("-Z", "Y")
    cam.rotation_euler = rot_quat.to_euler()
    if is_ortho:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = scale_or_lens
    else:
        cam_data.type = "PERSP"
        cam_data.lens = scale_or_lens
    scene.render.filepath = os.path.join(out_dir, f"{prefix}_{vname}.png")
    bpy.ops.render.render(write_still=True)

print("BLENDER_6VIEWS_OK")
'''


def render_6views(uv_obj: Path, tex_path: Path, out_dir: Path, prefix: str, res: int) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
        tf.write(BLENDER_RENDER_6VIEWS)
        script_p = tf.name
    try:
        cmd = [
            "blender", "-b", "-P", script_p, "--",
            str(uv_obj), str(tex_path), str(out_dir), prefix, str(res),
        ]
        p = subprocess.run(cmd, text=True, capture_output=True)
        if p.returncode != 0:
            raise RuntimeError(f"Blender render failed:\n{p.stderr[-1000:]}")
    finally:
        Path(script_p).unlink(missing_ok=True)


def load_rgba(path: Path) -> tuple[np.ndarray, np.ndarray]:
    im = np.asarray(Image.open(path).convert("RGBA"), dtype=np.uint8)
    return im[..., :3], im[..., 3] > 128


def crop_tight(rgb: np.ndarray, mask: np.ndarray, res: int = 512) -> tuple[np.ndarray, np.ndarray]:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return rgb, mask
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    c_rgb = cv2.resize(rgb[y0 : y1 + 1, x0 : x1 + 1], (res, res), interpolation=cv2.INTER_AREA)
    c_m = cv2.resize(mask[y0 : y1 + 1, x0 : x1 + 1].astype(np.uint8), (res, res), interpolation=cv2.INTER_NEAREST) > 0
    return c_rgb, c_m


def lap_var_masked(rgb: np.ndarray, mask: np.ndarray | None = None) -> float:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    if mask is not None and mask.any():
        return round(float(lap[mask].var()), 2)
    return round(float(lap.var()), 2)


def sat_mean_pct(rgb: np.ndarray, mask: np.ndarray | None = None) -> float:
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    s = hsv[..., 1].astype(np.float32)
    if mask is not None and mask.any():
        s = s[mask]
    return round(float(s.mean() / 255.0 * 100.0), 2)


def make_crop_pair(before_p: Path, final_p: Path, box_norm: list[float], out_p: Path, title: str) -> None:
    brgb, bm = load_rgba(before_p)
    frgb, fm = load_rgba(final_p)
    bt, _ = crop_tight(brgb, bm, 512)
    ft, _ = crop_tight(frgb, fm, 512)
    x0, y0, x1, y1 = [int(round(v * 512)) for v in box_norm]
    cb = cv2.resize(bt[y0:y1, x0:x1], (256, 256), interpolation=cv2.INTER_NEAREST)
    cf = cv2.resize(ft[y0:y1, x0:x1], (256, 256), interpolation=cv2.INTER_NEAREST)
    canvas = Image.new("RGB", (520, 282), (24, 24, 28))
    canvas.paste(Image.fromarray(cb), (0, 26))
    canvas.paste(Image.fromarray(cf), (264, 26))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 6), f"{title} - BEFORE (5f4945d)", fill=(230, 230, 230))
    draw.text((272, 6), f"{title} - FINAL", fill=(140, 255, 160))
    canvas.save(out_p)


def evaluate_texture_set(tex_path: Path, render_dir: Path, prefix: str, views: list[str], pr_cfg: dict) -> dict:
    tex_rgb = np.asarray(Image.open(tex_path).convert("RGB"), dtype=np.uint8)
    pmask, patches = detect_bright_patches_in_dark(tex_rgb, pr_cfg)
    tex_patch_pct = round(float((pmask > 0).sum()) / float(tex_rgb.shape[0] * tex_rgb.shape[1]) * 100.0, 4)

    view_stats = {}
    view_laps = []
    for v in views:
        rgb, m = load_rgba(render_dir / f"{prefix}_{v}.png")
        lv = lap_var_masked(rgb, m)
        view_laps.append(lv)
        pix = rgb[m].astype(np.float32) if m.any() else rgb.reshape(-1, 3).astype(np.float32)
        lum = 0.299 * pix[:, 0] + 0.587 * pix[:, 1] + 0.114 * pix[:, 2]
        view_stats[v] = {
            "laplacian_var": lv,
            "sat_pct": sat_mean_pct(rgb, m),
            "lum_mean": round(float(lum.mean()), 1),
            "dark_lt80_pct": round(float((lum < 80).mean() * 100.0), 1),
            "bright_gt180_pct": round(float((lum > 180).mean() * 100.0), 1),
        }

    return {
        "texture_size": list(tex_rgb.shape[:2]),
        "texture_laplacian_var": lap_var_masked(tex_rgb),
        "texture_sat_pct": sat_mean_pct(tex_rgb),
        "patch_count": len(patches),
        "patch_texels_pct": tex_patch_pct,
        "views_laplacian_mean": round(float(np.mean(view_laps)), 2),
        "views": view_stats,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--final-dir", required=True, help="Directory with final <vid>_*.png textures")
    ap.add_argument("--report-out", required=True)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    evid = Path(cfg["evidence_dir"])
    r_before = evid / "renders" / "before"
    r_final = evid / "renders" / "final"
    r_crops = evid / "renders" / "crops"
    for d in (r_before, r_final, r_crops):
        d.mkdir(parents=True, exist_ok=True)

    res = int(cfg["eval"].get("render_res", 512))
    views = cfg["eval"]["views"]
    crop_boxes = cfg["eval"].get("crop_boxes", {})
    pr_cfg = cfg["patch_repair"]
    final_dir = Path(args.final_dir)

    out = {"stage": "D_eval_quality", "asset_id": cfg["asset_id"], "variants": {}}

    for var in cfg["variants"]:
        vid = var["id"]
        uv_obj = Path(var["uv_obj"])
        prev_tex = Path(var["prev_texture"])
        cands = sorted(final_dir.glob(f"{vid}_*.png"))
        if not cands:
            raise FileNotFoundError(f"No final texture for {vid} in {final_dir}")
        final_tex = cands[0]

        render_6views(uv_obj, prev_tex, r_before, f"{vid}_before", res)
        render_6views(uv_obj, final_tex, r_final, f"{vid}_final", res)

        before_m = evaluate_texture_set(prev_tex, r_before, f"{vid}_before", views, pr_cfg)
        final_m = evaluate_texture_set(final_tex, r_final, f"{vid}_final", views, pr_cfg)

        # GT saturation average across all provided GT views
        gt_sats = []
        for gp in var.get("gt_views", {}).values():
            grgb = np.asarray(Image.open(gp).convert("RGB"), dtype=np.uint8)
            gfg = binary_fill_holes((grgb < 247).any(axis=-1))
            gt_sats.append(sat_mean_pct(grgb, gfg))
        gt_sat_mean = round(float(np.mean(gt_sats)), 2) if gt_sats else 0.0

        # Side-by-side crops
        crop_files = {}
        for cname, cspec in crop_boxes.items():
            vname = cspec["view"]
            box = cspec["box"]
            cp = r_crops / f"{vid}_{cname}.png"
            make_crop_pair(
                r_before / f"{vid}_before_{vname}.png",
                r_final / f"{vid}_final_{vname}.png",
                box,
                cp,
                f"{vid} {cname}",
            )
            crop_files[cname] = str(cp)

        lap_ratio = round(final_m["texture_laplacian_var"] / max(1e-6, before_m["texture_laplacian_var"]), 2)
        view_lap_ratio = round(final_m["views_laplacian_mean"] / max(1e-6, before_m["views_laplacian_mean"]), 2)
        patches_improved = final_m["patch_texels_pct"] <= before_m["patch_texels_pct"]
        sharpness_improved = (lap_ratio >= 1.15) or (view_lap_ratio >= 1.05)
        wins = bool(patches_improved and sharpness_improved)

        out["variants"][vid] = {
            "before": before_m,
            "final": final_m,
            "gt_sat_mean_pct": gt_sat_mean,
            "sharpness_tex_ratio": lap_ratio,
            "sharpness_views_ratio": view_lap_ratio,
            "wins_vs_prev": wins,
            "crops": crop_files,
        }
        print(
            f"[stage_d] {vid}: tex_lap {before_m['texture_laplacian_var']}->{final_m['texture_laplacian_var']} ({lap_ratio}x) | "
            f"view_lap {before_m['views_laplacian_mean']}->{final_m['views_laplacian_mean']} ({view_lap_ratio}x) | "
            f"patches {before_m['patch_count']}({before_m['patch_texels_pct']}%)->{final_m['patch_count']}({final_m['patch_texels_pct']}%) | "
            f"wins={wins}",
            flush=True,
        )

    Path(args.report_out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("STAGE_D_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
