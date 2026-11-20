#!/usr/bin/env python3
"""Universal Asset Texture Painting — Stage C (Generic Isolated Bright-Patch Repair).

Asset-agnostic detector: finds bright connected components (delta L > threshold)
surrounded by a coherent dark neighborhood (>= dark_perimeter_ratio_min of perimeter),
repairs them with Telea inpainting from surrounding dark/coherent texels + soft Gaussian
edge feathering (zero flat fill). Driven strictly by --config <asset.json>.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import trimesh
from PIL import Image


def detect_bright_patches_in_dark(rgb: np.ndarray, pr_cfg: dict) -> tuple[np.ndarray, list[dict]]:
    """Returns (uint8 binary mask 0/255 of defective patches, list of patch metadata)."""
    h, w, _ = rgb.shape
    lum = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]).astype(np.float32)

    bright_min = float(pr_cfg.get("bright_lum_min", 180))
    dark_max = float(pr_cfg.get("dark_ring_lum_max", 85))
    delta_min = float(pr_cfg.get("delta_lum_min", 95))
    peri_min = float(pr_cfg.get("dark_perimeter_ratio_min", 0.70))
    min_px = int(pr_cfg.get("min_component_px", 12))
    max_px = int(float(pr_cfg.get("max_component_area_ratio", 0.015)) * h * w)
    ring_w = int(pr_cfg.get("ring_width_px", 6))

    bright_bin = (lum >= bright_min).astype(np.uint8)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(bright_bin, connectivity=8)

    k_ring = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ring_w + 1, 2 * ring_w + 1))
    repair_mask = np.zeros((h, w), dtype=np.uint8)
    patches: list[dict] = []

    for lbl in range(1, num_labels):
        area = int(stats[lbl, cv2.CC_STAT_AREA])
        if area < min_px or area > max_px:
            continue

        x = int(stats[lbl, cv2.CC_STAT_LEFT])
        y = int(stats[lbl, cv2.CC_STAT_TOP])
        bw = int(stats[lbl, cv2.CC_STAT_WIDTH])
        bh = int(stats[lbl, cv2.CC_STAT_HEIGHT])

        # Local ROI with padding for fast morphological ring check
        pad = ring_w + 2
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(w, x + bw + pad), min(h, y + bh + pad)

        comp_roi = (labels[y0:y1, x0:x1] == lbl).astype(np.uint8)
        dil = cv2.dilate(comp_roi, k_ring, iterations=1)
        ring = (dil > 0) & (comp_roi == 0)
        if not ring.any():
            continue

        lum_roi = lum[y0:y1, x0:x1]
        comp_lum = float(lum_roi[comp_roi > 0].mean())
        ring_vals = lum_roi[ring]
        ring_dark_ratio = float((ring_vals <= dark_max).mean())
        ring_med_lum = float(np.median(ring_vals))
        delta_l = comp_lum - ring_med_lum

        if ring_dark_ratio >= peri_min and delta_l >= delta_min:
            repair_mask[y0:y1, x0:x1][comp_roi > 0] = 255
            cx, cy = float(centroids[lbl][0]), float(centroids[lbl][1])
            patches.append({
                "area_px": area,
                "uv_center": [round(cx / w, 4), round(1.0 - cy / h, 4)],
                "bbox_px": [x, y, bw, bh],
                "comp_lum": round(comp_lum, 1),
                "ring_med_lum": round(ring_med_lum, 1),
                "dark_perimeter_ratio": round(ring_dark_ratio, 3),
            })

    return repair_mask, patches


def detect_dark_specks_in_bright(
    rgb: np.ndarray,
    pr_cfg: dict,
    photo_ref_lum: np.ndarray | None = None,
    photo_cos: np.ndarray | None = None,
) -> tuple[np.ndarray, list[dict], list[dict]]:
    """Generic symmetric detector: small isolated dark specks inside coherent bright surfaces.

    Photo-consistency guard: if a real reference photo sees the component head-on
    (photo_cos >= photo_guard_cos_min) and its pixels are also dark there, BLOCK repair
    so genuine small dark surface details are preserved.
    """
    h, w, _ = rgb.shape
    lum = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]).astype(np.float32)

    dark_max = float(pr_cfg.get("dark_speck_lum_max", 115))
    bright_min = float(pr_cfg.get("bright_ring_lum_min", 185))
    delta_min = float(pr_cfg.get("dark_speck_delta_min", 75))
    peri_min = float(pr_cfg.get("bright_perimeter_ratio_min", 0.75))
    min_px = int(pr_cfg.get("dark_speck_min_px", 1))
    max_px = int(float(pr_cfg.get("dark_speck_max_area_ratio", 0.0006)) * h * w)
    ring_w = int(pr_cfg.get("dark_speck_ring_width_px", 5))
    guard_cos = float(pr_cfg.get("photo_guard_cos_min", 0.80))
    guard_tol = float(pr_cfg.get("photo_guard_lum_tol", 25.0))
    guard_cons = float(pr_cfg.get("photo_guard_consistency_min", 0.50))

    dark_bin = (lum <= dark_max).astype(np.uint8)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(dark_bin, connectivity=8)

    k_ring = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ring_w + 1, 2 * ring_w + 1))
    repair_mask = np.zeros((h, w), dtype=np.uint8)
    specks: list[dict] = []
    blocked: list[dict] = []

    for lbl in range(1, num_labels):
        area = int(stats[lbl, cv2.CC_STAT_AREA])
        if area < min_px or area > max_px:
            continue

        x = int(stats[lbl, cv2.CC_STAT_LEFT])
        y = int(stats[lbl, cv2.CC_STAT_TOP])
        bw = int(stats[lbl, cv2.CC_STAT_WIDTH])
        bh = int(stats[lbl, cv2.CC_STAT_HEIGHT])

        pad = ring_w + 2
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(w, x + bw + pad), min(h, y + bh + pad)

        comp_roi = (labels[y0:y1, x0:x1] == lbl).astype(np.uint8)
        dil = cv2.dilate(comp_roi, k_ring, iterations=1)
        ring = (dil > 0) & (comp_roi == 0)
        if not ring.any():
            continue

        lum_roi = lum[y0:y1, x0:x1]
        comp_lum = float(lum_roi[comp_roi > 0].mean())
        ring_vals = lum_roi[ring]
        ring_bright_ratio = float((ring_vals >= bright_min).mean())
        ring_med_lum = float(np.median(ring_vals))
        delta_l = ring_med_lum - comp_lum

        if ring_bright_ratio >= peri_min and delta_l >= delta_min:
            cx, cy = float(centroids[lbl][0]), float(centroids[lbl][1])
            meta = {
                "area_px": area,
                "uv_center": [round(cx / w, 4), round(1.0 - cy / h, 4)],
                "comp_lum": round(comp_lum, 1),
                "ring_med_lum": round(ring_med_lum, 1),
            }
            # Photo-consistency guard
            if photo_ref_lum is not None and photo_cos is not None:
                c_mask = comp_roi > 0
                cos_vals = photo_cos[y0:y1, x0:x1][c_mask]
                if (cos_vals >= guard_cos).mean() >= 0.4:
                    p_lums = photo_ref_lum[y0:y1, x0:x1][c_mask]
                    photo_dark_ratio = float((p_lums <= (dark_max + guard_tol)).mean())
                    if photo_dark_ratio >= guard_cons:
                        meta["photo_dark_ratio"] = round(photo_dark_ratio, 3)
                        blocked.append(meta)
                        continue

            repair_mask[y0:y1, x0:x1][comp_roi > 0] = 255
            specks.append(meta)

    return repair_mask, specks, blocked


def _apply_telea_feather(rgb: np.ndarray, mask: np.ndarray, radius: int, sigma: float, dilate_px: int = 2) -> np.ndarray:
    if not (mask > 0).any():
        return rgb.copy()
    k_dil = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * dilate_px + 1, 2 * dilate_px + 1))
    inpaint_mask = cv2.dilate(mask, k_dil, iterations=1)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    inpainted_rgb = cv2.cvtColor(cv2.inpaint(bgr, inpaint_mask, radius, cv2.INPAINT_TELEA), cv2.COLOR_BGR2RGB)
    alpha = cv2.GaussianBlur(inpaint_mask.astype(np.float32) / 255.0, (0, 0), sigmaX=sigma)
    alpha = np.clip(alpha, 0.0, 1.0)[..., None]
    return np.clip(inpainted_rgb.astype(np.float32) * alpha + rgb.astype(np.float32) * (1.0 - alpha), 0, 255).astype(np.uint8)


def repair_texture(
    rgb: np.ndarray,
    pr_cfg: dict,
    photo_ref_lum: np.ndarray | None = None,
    photo_cos: np.ndarray | None = None,
) -> tuple[np.ndarray, dict]:
    mask, patches = detect_bright_patches_in_dark(rgb, pr_cfg)
    h, w, _ = rgb.shape
    total_px = h * w
    before_px = int((mask > 0).sum())
    before_pct = round(before_px / total_px * 100.0, 4)

    radius = int(pr_cfg.get("inpaint_radius_px", 9))
    sigma = float(pr_cfg.get("feather_sigma", 2.0))
    out_rgb = _apply_telea_feather(rgb, mask, radius, sigma, dilate_px=2)

    dark_specks_before = 0
    dark_specks_after = 0
    blocked_2d: list[dict] = []
    if pr_cfg.get("repair_dark_specks", False):
        dmask, dspecks, blocked_2d = detect_dark_specks_in_bright(out_rgb, pr_cfg, photo_ref_lum, photo_cos)
        dark_specks_before = len(dspecks)
        if dark_specks_before > 0:
            out_rgb = _apply_telea_feather(out_rgb, dmask, max(5, radius - 2), max(1.2, sigma - 0.5), dilate_px=2)
            _, dspecks_after, _ = detect_dark_specks_in_bright(out_rgb, pr_cfg, photo_ref_lum, photo_cos)
            dark_specks_after = len(dspecks_after)

    after_mask, after_patches = detect_bright_patches_in_dark(out_rgb, pr_cfg)
    after_px = int((after_mask > 0).sum())
    after_pct = round(after_px / total_px * 100.0, 4)

    return out_rgb, {
        "patches_detected": len(patches),
        "patches_repaired": len(patches) - len(after_patches),
        "patches_residual": len(after_patches),
        "patch_texels_before": before_px,
        "patch_texels_before_pct": before_pct,
        "patch_texels_after": after_px,
        "patch_texels_after_pct": after_pct,
        "dark_specks_detected": dark_specks_before,
        "dark_specks_residual": dark_specks_after,
        "blocked_by_photo_guard_2d": len(blocked_2d),
        "blocked_2d_samples": blocked_2d[:30],
        "patches": patches[:40],
    }


def repair_3d_uv_island_specks(
    uv_obj_path: Path,
    rgb: np.ndarray,
    pr_cfg: dict,
    photo_ref_lum: np.ndarray | None = None,
    photo_cos: np.ndarray | None = None,
) -> tuple[np.ndarray, int, int]:
    """Generic 3D-topology coherence repair with photo-consistency guard."""
    mesh = trimesh.load(str(uv_obj_path), force="mesh", process=False)
    uv = getattr(mesh.visual, "uv", None)
    if uv is None or len(uv) != len(mesh.vertices):
        return rgb, 0, 0

    h, w, _ = rgb.shape
    faces = np.asarray(mesh.faces, dtype=np.int32)
    uv_px = np.empty_like(uv, dtype=np.float32)
    uv_px[:, 0] = np.clip(uv[:, 0], 0.0, 1.0) * (w - 1)
    uv_px[:, 1] = (1.0 - np.clip(uv[:, 1], 0.0, 1.0)) * (h - 1)

    fc_uv = uv_px[faces].mean(axis=1)
    cx = np.clip(np.round(fc_uv[:, 0]).astype(np.int32), 0, w - 1)
    cy = np.clip(np.round(fc_uv[:, 1]).astype(np.int32), 0, h - 1)
    face_rgb = rgb[cy, cx].astype(np.float32)
    face_lum = 0.299 * face_rgb[:, 0] + 0.587 * face_rgb[:, 1] + 0.114 * face_rgb[:, 2]

    dark_max = float(pr_cfg.get("dark_speck_lum_max", 115))
    bright_min = float(pr_cfg.get("bright_ring_lum_min", 185))
    guard_cos = float(pr_cfg.get("photo_guard_cos_min", 0.80))
    guard_tol = float(pr_cfg.get("photo_guard_lum_tol", 25.0))
    guard_cons = float(pr_cfg.get("photo_guard_consistency_min", 0.50))
    n_faces = len(faces)

    v_round = np.round(np.asarray(mesh.vertices, dtype=np.float64), 5)
    _, inv = np.unique(v_round, axis=0, return_inverse=True)
    f_welded = inv[faces]
    from collections import defaultdict
    v2f: dict[int, list[int]] = defaultdict(list)
    for fi, (a, b, c) in enumerate(f_welded):
        v2f[int(a)].append(fi)
        v2f[int(b)].append(fi)
        v2f[int(c)].append(fi)

    is_dark = face_lum <= dark_max
    visited = np.zeros(n_faces, dtype=bool)
    max_comp_faces = int(pr_cfg.get("max_3d_speck_faces", 450))
    peri_min = float(pr_cfg.get("bright_perimeter_ratio_min", 0.75))

    out_rgb = rgb.copy()
    bad_face_mask = np.zeros((h, w), dtype=np.uint8)
    fixed_comps = 0
    blocked_3d = 0

    for start_f in np.where(is_dark)[0]:
        if visited[start_f]:
            continue
        comp = []
        border_nbrs = set()
        stack = [int(start_f)]
        visited[start_f] = True
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for v in f_welded[cur]:
                for nf in v2f[int(v)]:
                    if is_dark[nf]:
                        if not visited[nf]:
                            visited[nf] = True
                            stack.append(nf)
                    else:
                        border_nbrs.add(nf)
        if len(comp) > max_comp_faces or not border_nbrs:
            continue

        nbr_arr = np.fromiter(border_nbrs, dtype=np.int32)
        bright_ratio = float((face_lum[nbr_arr] >= bright_min).mean())
        if bright_ratio >= peri_min:
            # Photo-consistency guard on 3D component
            if photo_ref_lum is not None and photo_cos is not None:
                c_arr = np.asarray(comp, dtype=np.int32)
                c_cos = photo_cos[cy[c_arr], cx[c_arr]]
                if (c_cos >= guard_cos).mean() >= 0.4:
                    p_lums = photo_ref_lum[cy[c_arr], cx[c_arr]]
                    if (p_lums <= (dark_max + guard_tol)).mean() >= guard_cons:
                        blocked_3d += 1
                        continue

            fill_col = np.median(face_rgb[nbr_arr], axis=0).round().astype(np.uint8)
            for fi in comp:
                tri = np.round(uv_px[faces[fi]]).astype(np.int32)
                cv2.fillConvexPoly(out_rgb, tri, tuple(int(c) for c in fill_col))
                cv2.fillConvexPoly(bad_face_mask, tri, 255)
            fixed_comps += 1

    if fixed_comps > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        dil = cv2.dilate(bad_face_mask, k, iterations=1)
        fringe = (dil > 0) & (bad_face_mask == 0)
        if fringe.any():
            bgr = cv2.cvtColor(out_rgb, cv2.COLOR_RGB2BGR)
            inpainted = cv2.cvtColor(cv2.inpaint(bgr, fringe.astype(np.uint8) * 255, 5, cv2.INPAINT_TELEA), cv2.COLOR_BGR2RGB)
            out_rgb[fringe] = inpainted[fringe]

    return out_rgb, fixed_comps, blocked_3d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--input-dir", required=True, help="Directory with <variant_id>_*.png textures")
    ap.add_argument("--output-dir", required=True, help="Directory to write repaired <variant_id>_repaired.png")
    ap.add_argument("--photo-ref-dir", default="", help="Optional Stage B dir with <vid>_photo_ref_*.png and <vid>_photo_cos_*.npy")
    ap.add_argument("--report-out", required=True)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    pr_cfg = cfg["patch_repair"]
    in_dir = Path(args.input_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pref_dir = Path(args.photo_ref_dir) if args.photo_ref_dir else None

    summary = {"stage": "C_patch_repair", "asset_id": cfg["asset_id"], "variants": {}}
    for var in cfg["variants"]:
        vid = var["id"]
        cands = [p for p in sorted(in_dir.glob(f"{vid}_*.png")) if "overlay" not in p.name and "heatmap" not in p.name and "photo_ref" not in p.name]
        if not cands:
            raise FileNotFoundError(f"No input texture for {vid} in {in_dir}")
        src = cands[0]
        rgb = np.asarray(Image.open(src).convert("RGB"), dtype=np.uint8)

        photo_ref_lum = None
        photo_cos = None
        if pref_dir and pref_dir.exists():
            ref_cands = sorted(pref_dir.glob(f"{vid}_photo_ref_*.png"))
            cos_cands = sorted(pref_dir.glob(f"{vid}_photo_cos_*.npy"))
            if ref_cands and cos_cands:
                ref_rgb = np.asarray(Image.open(ref_cands[0]).convert("RGB"), dtype=np.float32)
                photo_ref_lum = 0.299 * ref_rgb[..., 0] + 0.587 * ref_rgb[..., 1] + 0.114 * ref_rgb[..., 2]
                photo_cos = np.load(cos_cands[0]).astype(np.float32)

        repaired, stats = repair_texture(rgb, pr_cfg, photo_ref_lum, photo_cos)
        uv_obj = Path(var["uv_obj"])
        if uv_obj.exists() and pr_cfg.get("repair_dark_specks", False):
            repaired, fixed_3d, blocked_3d = repair_3d_uv_island_specks(uv_obj, repaired, pr_cfg, photo_ref_lum, photo_cos)
            stats["dark_3d_uv_islands_repaired"] = fixed_3d
            stats["blocked_by_photo_guard_3d"] = blocked_3d
        dst = out_dir / f"{vid}_repaired.png"
        Image.fromarray(repaired, mode="RGB").save(dst)
        summary["variants"][vid] = {"src": str(src), "dst": str(dst), **stats}
        print(
            f"[stage_c] {vid}: bright_patches={stats['patches_detected']} "
            f"({stats['patch_texels_before_pct']}%->{stats['patch_texels_after_pct']}%) | "
            f"dark_2d={stats.get('dark_specks_detected', 0)} (blocked={stats.get('blocked_by_photo_guard_2d', 0)}) | "
            f"dark_3d={stats.get('dark_3d_uv_islands_repaired', 0)} (blocked={stats.get('blocked_by_photo_guard_3d', 0)})",
            flush=True,
        )

    Path(args.report_out).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("STAGE_C_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
