#!/usr/bin/env python3
"""Universal Asset Texture Painting — Stage B (Silhouette-IoU Photo Alignment & Detail Blending).

Generic, asset-agnostic photometric detail transfer driven strictly by --config <asset.json>:
  1. Aligns each reference photo to the 3D mesh via coarse-to-fine silhouette IoU optimization
     (yaw, pitch, bbox scale/offset) + fine photometric SSIM refinement.
  2. Saves visual alignment overlays and enforces mandatory IoU >= min_iou (default 0.90) gate.
  3. Computes Z-buffered visibility + normal-angle weight w = smoothstep(cos, cos_lo, cos_hi)
     with silhouette edge feathering, blending multiple views weighted by cos^2.
  4. Applies illumination-preserving frequency-split detail transfer:
     albedo_final = (1 - w_eff) * albedo + w_eff * (blur(albedo) + (photo - blur(photo))).
  5. Exports per-view weight heatmaps + photo_ref / photo_cos maps for Stage C photo-consistency guard.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import trimesh
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools" / "generator"))
from rebake_fox_paint import (  # noqa: E402
    build_ortho_depth_buffer,
    compute_fg_mask,
    rasterize_uv_attributes,
    tight_bbox_2d,
)
from upscale_and_pack_fox import VramSampler10s  # noqa: E402


def rot_yaw_pitch(yaw_deg: float, pitch_deg: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns camera basis (right, up, view_dir) in mesh coordinates (Y-up or Z-up auto-handled).

    view_dir points FROM surface TOWARD camera.
    Mesh convention (trimesh obj from Hunyuan/Blender): X=right/left, Y=up, Z=front/back
    (we detect up-axis automatically from mesh extents or standard Y-up).
    """
    yr = math.radians(yaw_deg)
    pr = math.radians(pitch_deg)
    # Camera looking from (sin(yr)*cos(pr), sin(pr), cos(yr)*cos(pr)) toward origin (Y-up)
    view_dir = np.array(
        [math.sin(yr) * math.cos(pr), math.sin(pr), math.cos(yr) * math.cos(pr)],
        dtype=np.float32,
    )
    view_dir /= max(1e-8, float(np.linalg.norm(view_dir)))
    world_up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    right = np.cross(world_up, view_dir)
    if np.linalg.norm(right) < 1e-6:
        right = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    else:
        right /= float(np.linalg.norm(right))
    up = np.cross(view_dir, right)
    up /= max(1e-8, float(np.linalg.norm(up)))
    return right, up, view_dir


def project_silhouette_fast(
    verts: np.ndarray,
    faces_sub: np.ndarray,
    yaw_deg: float,
    pitch_deg: float,
    photo_fg: np.ndarray,
    res: int = 256,
    scale_mul: tuple[float, float] = (1.0, 1.0),
    shift_px: tuple[float, float] = (0.0, 0.0),
) -> tuple[np.ndarray, float, dict]:
    """Projects mesh onto ortho camera matching photo_fg tight bbox and returns (mask, iou, transform)."""
    right, up, view_dir = rot_yaw_pitch(yaw_deg, pitch_deg)
    u_raw = verts @ right
    v_raw = -(verts @ up)  # image y points downward

    umin, umax = float(u_raw.min()), float(u_raw.max())
    vmin, vmax = float(v_raw.min()), float(v_raw.max())
    ur = max(1e-6, umax - umin)
    vr = max(1e-6, vmax - vmin)

    # Match photo_fg tight bbox
    px0, py0, px1, py1 = tight_bbox_2d(photo_fg)
    pw = max(1.0, float(px1 - px0))
    ph = max(1.0, float(py1 - py0))
    pcx = 0.5 * (px0 + px1) + shift_px[0]
    pcy = 0.5 * (py0 + py1) + shift_px[1]
    sw = pw * scale_mul[0]
    sh = ph * scale_mul[1]

    u_n = (u_raw - 0.5 * (umin + umax)) / ur  # [-0.5, 0.5]
    v_n = (v_raw - 0.5 * (vmin + vmax)) / vr
    img_x = u_n * sw + pcx
    img_y = v_n * sh + pcy

    sil = np.zeros((res, res), dtype=np.uint8)
    tris = np.stack([img_x[faces_sub], img_y[faces_sub]], axis=-1).round().astype(np.int32)
    cv2.fillPoly(sil, list(tris), 255)
    sil_b = sil > 0

    inter = int((sil_b & photo_fg).sum())
    union = int((sil_b | photo_fg).sum())
    iou = float(inter) / max(1, union)

    # Normalized [0,1] mapping parameters for full-res projection
    xform = {
        "yaw_deg": yaw_deg,
        "pitch_deg": pitch_deg,
        "umin": umin,
        "umax": umax,
        "vmin": vmin,
        "vmax": vmax,
        "pcx_norm": pcx / float(res),
        "pcy_norm": pcy / float(res),
        "sw_norm": sw / float(res),
        "sh_norm": sh / float(res),
    }
    return sil_b, iou, xform


def compute_ssim_gray(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float:
    if not mask.any():
        return 0.0
    x = a[mask].astype(np.float64)
    y = b[mask].astype(np.float64)
    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    mx, my = x.mean(), y.mean()
    vx, vy = x.var(), y.var()
    cov = ((x - mx) * (y - my)).mean()
    return float(((2 * mx * my + c1) * (2 * cov + c2)) / ((mx**2 + my**2 + c1) * (vx + vy + c2)))


def align_photo_to_mesh(
    verts: np.ndarray,
    faces: np.ndarray,
    photo_rgb: np.ndarray,
    init_yaw: float,
    init_pitch: float,
) -> tuple[dict, float, np.ndarray]:
    """Coarse-to-fine silhouette IoU alignment (yaw, pitch, scale, offset)."""
    # Subsample faces for super-fast 256px silhouette optimization
    step = max(1, len(faces) // 35000)
    faces_sub = faces[::step]

    res = 256
    photo_256 = cv2.resize(photo_rgb, (res, res), interpolation=cv2.INTER_AREA)
    fg_256 = compute_fg_mask(photo_256, thresh=247)

    # 1. Auto-detect correct 180-deg facing (generic for any mesh axis convention)
    best_base_yaw = init_yaw
    best_base_iou = -1.0
    for cand_yaw in (init_yaw, (init_yaw + 180.0) % 360.0):
        _, ciou, _ = project_silhouette_fast(verts, faces_sub, cand_yaw, init_pitch, fg_256, res)
        if ciou > best_base_iou:
            best_base_iou = ciou
            best_base_yaw = cand_yaw

    best_iou = best_base_iou
    best_yaw = best_base_yaw
    best_pitch = init_pitch
    best_scale = (1.0, 1.0)
    best_shift = (0.0, 0.0)

    # Coarse yaw/pitch search around canonical orientation
    for dy in (-6.0, -3.0, 0.0, 3.0, 6.0):
        for dp in (-4.0, -2.0, 0.0, 2.0, 4.0):
            _, iou, _ = project_silhouette_fast(verts, faces_sub, best_base_yaw + dy, init_pitch + dp, fg_256, res)
            if iou > best_iou:
                best_iou = iou
                best_yaw = best_base_yaw + dy
                best_pitch = init_pitch + dp

    # Coarse-to-fine scale & shift (handles thin protrusions like antennas shifting tight bbox)
    for sx in (0.94, 0.98, 1.0, 1.03, 1.06):
        for sy in (0.94, 0.98, 1.0, 1.03, 1.06):
            for tx in (-4.0, 0.0, 4.0):
                for ty in (-6.0, -3.0, 0.0, 3.0, 6.0):
                    _, iou, _ = project_silhouette_fast(
                        verts, faces_sub, best_yaw, best_pitch, fg_256, res, (sx, sy), (tx, ty)
                    )
                    if iou > best_iou:
                        best_iou = iou
                        best_scale = (sx, sy)
                        best_shift = (tx, ty)

    # Fine refinement around best (yaw, pitch, scale, shift)
    cy, cp = best_yaw, best_pitch
    csx, csy = best_scale
    ctx, cty = best_shift
    for dy in (-2.0, -1.0, 0.0, 1.0, 2.0):
        for dp in (-1.5, 0.0, 1.5):
            _, iou, _ = project_silhouette_fast(verts, faces_sub, cy + dy, cp + dp, fg_256, res, (csx, csy), (ctx, cty))
            if iou > best_iou:
                best_iou = iou
                best_yaw = cy + dy
                best_pitch = cp + dp

    for dsx in (-0.015, 0.0, 0.015):
        for dsy in (-0.015, 0.0, 0.015):
            for dtx in (-2.0, 0.0, 2.0):
                for dty in (-2.0, 0.0, 2.0):
                    _, iou, _ = project_silhouette_fast(
                        verts, faces_sub, best_yaw, best_pitch, fg_256, res,
                        (csx + dsx, csy + dsy), (ctx + dtx, cty + dty),
                    )
                    if iou > best_iou:
                        best_iou = iou
                        best_scale = (csx + dsx, csy + dsy)
                        best_shift = (ctx + dtx, cty + dty)

    # Final exact IoU at 512px with ALL faces
    res_eval = 512
    photo_512 = cv2.resize(photo_rgb, (res_eval, res_eval), interpolation=cv2.INTER_AREA)
    fg_512 = compute_fg_mask(photo_512, thresh=247)
    sil_512, final_iou, xform = project_silhouette_fast(
        verts,
        faces,
        best_yaw,
        best_pitch,
        fg_512,
        res_eval,
        best_scale,
        (best_shift[0] * 2.0, best_shift[1] * 2.0),
    )

    # Create visual overlay (photo + green silhouette tint + cyan contour)
    ov = photo_512.copy().astype(np.float32)
    ov[sil_512] = ov[sil_512] * 0.68 + np.array([30.0, 220.0, 80.0], dtype=np.float32) * 0.32
    ov_u8 = np.clip(ov, 0, 255).astype(np.uint8)
    contours, _ = cv2.findContours(sil_512.astype(np.uint8) * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(ov_u8, contours, -1, (0, 255, 255), 2)
    ov_im = Image.fromarray(ov_u8)
    draw = ImageDraw.Draw(ov_im)
    draw.rectangle([4, 4, 290, 28], fill=(16, 18, 22))
    draw.text((10, 9), f"IoU={final_iou:.4f} yaw={best_yaw:.1f} pitch={best_pitch:.1f}", fill=(140, 255, 160))

    return xform, round(final_iou, 4), np.asarray(ov_im)


def smoothstep(x: np.ndarray, edge0: float, edge1: float) -> np.ndarray:
    t = np.clip((x - edge0) / max(1e-6, edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--input-dir", required=True, help="Directory with Stage A <vid>_*.png textures")
    ap.add_argument("--output-dir", required=True, help="Directory to write Stage B blended textures + reports")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    pb_cfg = cfg["photo_blend"]
    in_dir = Path(args.input_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    min_iou = float(pb_cfg.get("min_iou", 0.90))
    cos_lo = float(pb_cfg.get("cos_lo", 0.80))
    cos_hi = float(pb_cfg.get("cos_hi", 0.92))
    w_max = float(pb_cfg.get("w_max", 0.80))
    sigma = float(pb_cfg.get("lowpass_sigma", 28.0))
    feather_px = int(pb_cfg.get("silhouette_feather_px", 6))
    z_res = int(pb_cfg.get("render_size", 1024))

    sampler = VramSampler10s(interval_s=10.0)
    sampler.start()
    t0 = time.time()

    report = {
        "stage": "B_photo_blend",
        "asset_id": cfg["asset_id"],
        "seed": int(cfg["seed"]),
        "params": pb_cfg,
        "variants": {},
    }

    for var in cfg["variants"]:
        vid = var["id"]
        t_v = time.time()
        uv_obj = Path(var["uv_obj"])
        cands = sorted(in_dir.glob(f"{vid}_*.png"))
        if not cands:
            raise FileNotFoundError(f"No input texture for {vid} in {in_dir}")
        src_tex_p = cands[0]

        albedo = np.asarray(Image.open(src_tex_p).convert("RGB"), dtype=np.float32)
        if albedo.shape[0] < 2048:
            albedo = cv2.resize(albedo, (2048, 2048), interpolation=cv2.INTER_CUBIC)
        tex_size = albedo.shape[0]
        albedo_blur = cv2.GaussianBlur(albedo, (0, 0), sigmaX=sigma)

        mesh = trimesh.load(str(uv_obj), force="mesh", process=False)
        verts = np.asarray(mesh.vertices, dtype=np.float32)
        faces = np.asarray(mesh.faces, dtype=np.int32)
        normals = np.asarray(mesh.vertex_normals, dtype=np.float32)
        uvs = np.asarray(mesh.visual.uv, dtype=np.float32)

        print(f"[stage_b] Rasterizing UV attributes ({tex_size}x{tex_size}) for {vid}...", flush=True)
        pos_map, nrm_map, valid_uv = rasterize_uv_attributes(verts, normals, uvs, faces, size=tex_size)

        # Accumulators across all accepted views (weighted by cos^2)
        acc_detail_rgb = np.zeros((tex_size, tex_size, 3), dtype=np.float32)
        acc_photo_rgb = np.zeros((tex_size, tex_size, 3), dtype=np.float32)
        acc_w_num = np.zeros((tex_size, tex_size), dtype=np.float32)
        acc_w_den = np.zeros((tex_size, tex_size), dtype=np.float32)
        max_w_map = np.zeros((tex_size, tex_size), dtype=np.float32)
        max_cos_map = np.zeros((tex_size, tex_size), dtype=np.float32)

        views_report = {}

        for vspec in pb_cfg["views"]:
            vname = vspec["name"]
            photo_p = Path(vspec["image"])
            photo_rgb = np.asarray(Image.open(photo_p).convert("RGB"), dtype=np.uint8)

            xform, iou, ov_np = align_photo_to_mesh(
                verts, faces, photo_rgb, float(vspec["init_yaw_deg"]), float(vspec["init_pitch_deg"])
            )
            ov_path = out_dir / f"{vid}_overlay_{vname}.png"
            Image.fromarray(ov_np).save(ov_path)

            accepted = iou >= min_iou
            print(f"  [stage_b] {vid}/{vname}: IoU={iou:.4f} (gate>={min_iou}) -> {'ACCEPTED' if accepted else 'SKIPPED'}", flush=True)

            if not accepted:
                views_report[vname] = {
                    "iou": iou,
                    "accepted": False,
                    "overlay_png": str(ov_path),
                    "xform": xform,
                    "texels_covered_pct": 0.0,
                }
                continue

            # Build exact Z-buffer in camera space at z_res x z_res
            right, up, view_dir = rot_yaw_pitch(xform["yaw_deg"], xform["pitch_deg"])
            u_raw = verts @ right
            v_raw = -(verts @ up)
            d_raw = verts @ view_dir
            ur = max(1e-6, xform["umax"] - xform["umin"])
            vr = max(1e-6, xform["vmax"] - xform["vmin"])

            u_v = ((u_raw - 0.5 * (xform["umin"] + xform["umax"])) / ur) * xform["sw_norm"] + xform["pcx_norm"]
            v_v = ((v_raw - 0.5 * (xform["vmin"] + xform["vmax"])) / vr) * xform["sh_norm"] + xform["pcy_norm"]
            z_buf = build_ortho_depth_buffer(verts, faces, u_v, v_v, d_raw, res=z_res)

            # Prepare photo & silhouette feather at z_res x z_res
            ph_z = cv2.resize(photo_rgb, (z_res, z_res), interpolation=cv2.INTER_AREA).astype(np.float32)
            ph_fg = compute_fg_mask(ph_z.astype(np.uint8), thresh=247)
            dist_in = distance_transform_edt(ph_fg)
            sil_feather = np.clip(dist_in / max(1.0, float(feather_px)), 0.0, 1.0).astype(np.float32)

            # Photo high/mid-frequency detail (photo - blur(photo))
            # Blur only inside foreground (normalized convolution) so white background doesn't bleed in!
            fg_f = ph_fg.astype(np.float32)[..., None]
            ph_blur_num = cv2.GaussianBlur(ph_z * fg_f, (0, 0), sigmaX=sigma * (z_res / float(tex_size)))
            ph_blur_den = cv2.GaussianBlur(fg_f, (0, 0), sigmaX=sigma * (z_res / float(tex_size)))
            ph_blur = ph_blur_num / np.maximum(ph_blur_den, 1e-4)[..., None]
            ph_detail = ph_z - ph_blur

            # Project every UV texel into this camera view
            pu = (
                ((pos_map[..., 0] * right[0] + pos_map[..., 1] * right[1] + pos_map[..., 2] * right[2])
                 - 0.5 * (xform["umin"] + xform["umax"])) / ur
            ) * xform["sw_norm"] + xform["pcx_norm"]
            pv = (
                (-(pos_map[..., 0] * up[0] + pos_map[..., 1] * up[1] + pos_map[..., 2] * up[2])
                 - 0.5 * (xform["vmin"] + xform["vmax"])) / vr
            ) * xform["sh_norm"] + xform["pcy_norm"]
            pd = pos_map[..., 0] * view_dir[0] + pos_map[..., 1] * view_dir[1] + pos_map[..., 2] * view_dir[2]
            cos_v = nrm_map[..., 0] * view_dir[0] + nrm_map[..., 1] * view_dir[1] + nrm_map[..., 2] * view_dir[2]

            in_bounds = valid_uv & (pu >= 0.0) & (pu <= 1.0) & (pv >= 0.0) & (pv <= 1.0) & (cos_v > 0.1)
            ix = np.clip(np.round(pu * (z_res - 1)).astype(np.int32), 0, z_res - 1)
            iy = np.clip(np.round(pv * (z_res - 1)).astype(np.int32), 0, z_res - 1)

            depth_tol = float(d_raw.max() - d_raw.min()) * 0.015
            vis = in_bounds & (pd >= (z_buf[iy, ix] - depth_tol)) & ph_fg[iy, ix]

            # Bilinear sampling of photo, photo_detail, and silhouette feather
            map_x = (pu * (z_res - 1)).astype(np.float32)
            map_y = (pv * (z_res - 1)).astype(np.float32)
            samp_photo = cv2.remap(ph_z, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            samp_detail = cv2.remap(ph_detail, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            samp_fth = cv2.remap(sil_feather, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0.0)

            w_view = np.where(vis, smoothstep(cos_v, cos_lo, cos_hi) * samp_fth, 0.0).astype(np.float32)
            cos2 = np.where(vis, np.clip(cos_v, 0.0, 1.0) ** 2, 0.0).astype(np.float32)

            # Accumulate weighted by cos^2
            acc_detail_rgb += samp_detail * (w_view * cos2)[..., None]
            acc_photo_rgb += samp_photo * cos2[..., None]
            acc_w_num += w_view * cos2
            acc_w_den += cos2
            max_w_map = np.maximum(max_w_map, w_view)
            max_cos_map = np.maximum(max_cos_map, np.where(vis, cos_v, 0.0))

            # Save heatmap of w_view
            hm_u8 = np.clip(w_view * 255.0, 0, 255).astype(np.uint8)
            hm_color = cv2.cvtColor(cv2.applyColorMap(hm_u8, cv2.COLORMAP_INFERNO), cv2.COLOR_BGR2RGB)
            hm_path = out_dir / f"{vid}_heatmap_{vname}.png"
            Image.fromarray(hm_color).save(hm_path)

            # Coverage stats: % of visible texels facing this camera (cos > 0.6) touched with w > 0.1
            facing = valid_uv & (cos_v > 0.6)
            touched = facing & (w_view > 0.1)
            cov_pct = round(float(touched.sum()) / max(1, int(facing.sum())) * 100.0, 2)
            views_report[vname] = {
                "iou": iou,
                "accepted": True,
                "overlay_png": str(ov_path),
                "heatmap_png": str(hm_path),
                "xform": xform,
                "facing_texels_covered_pct": cov_pct,
                "total_uv_touched_pct": round(float((w_view > 0.1).sum()) / max(1, int(valid_uv.sum())) * 100.0, 2),
            }
            print(f"    -> facing coverage (cos>0.6, w>0.1): {cov_pct}%", flush=True)

        # Combine blended detail with albedo (illumination-preserving frequency split)
        has_blend = acc_w_num > 1e-5
        avg_detail = np.zeros_like(albedo)
        avg_detail[has_blend] = acc_detail_rgb[has_blend] / acc_w_num[has_blend, None]
        photo_ref = np.zeros_like(albedo)
        has_photo = acc_w_den > 1e-5
        photo_ref[has_photo] = acc_photo_rgb[has_photo] / acc_w_den[has_photo, None]

        # Frequency-split target: blur(albedo) + (photo - blur(photo)), plus gentle low-freq pull (0.35)
        # so dark UV-seam smudges under the photo also clean up to true photo tone without baking harsh shadows
        target_rgb = np.clip(0.65 * (albedo_blur + avg_detail) + 0.35 * photo_ref, 0.0, 255.0)
        w_eff = np.clip(max_w_map * w_max, 0.0, w_max)[..., None]
        blended = np.clip((1.0 - w_eff) * albedo + w_eff * target_rgb, 0.0, 255.0).astype(np.uint8)

        out_tex = out_dir / f"{vid}_blended_{tex_size}.png"
        Image.fromarray(blended, mode="RGB").save(out_tex)

        # Save photo_ref and max_cos_map for Stage C photo-consistency guard
        ref_path = out_dir / f"{vid}_photo_ref_{tex_size}.png"
        cos_path = out_dir / f"{vid}_photo_cos_{tex_size}.npy"
        Image.fromarray(np.clip(photo_ref, 0, 255).astype(np.uint8), mode="RGB").save(ref_path)
        np.save(cos_path, max_cos_map.astype(np.float16))

        report["variants"][vid] = {
            "src_texture": str(src_tex_p),
            "blended_texture": str(out_tex),
            "photo_ref_png": str(ref_path),
            "photo_cos_npy": str(cos_path),
            "tempo_s": round(time.time() - t_v, 2),
            "views": views_report,
        }

    report["tempo_total_s"] = round(time.time() - t0, 2)
    report.update(sampler.stop())
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"STAGE_B_PHOTO_BLEND_OK peak={report['vram_pico_mib']}MiB t={report['tempo_total_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
