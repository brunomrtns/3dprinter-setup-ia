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


def repair_texture(rgb: np.ndarray, pr_cfg: dict) -> tuple[np.ndarray, dict]:
    mask, patches = detect_bright_patches_in_dark(rgb, pr_cfg)
    h, w, _ = rgb.shape
    total_px = h * w
    before_px = int((mask > 0).sum())
    before_pct = round(before_px / total_px * 100.0, 4)

    if before_px == 0:
        return rgb.copy(), {
            "patches_detected": 0,
            "patches_repaired": 0,
            "patch_texels_before": 0,
            "patch_texels_before_pct": 0.0,
            "patch_texels_after": 0,
            "patch_texels_after_pct": 0.0,
            "patches": [],
        }

    # Slight dilation (2px) to remove bright anti-aliased fringe before Telea inpaint
    k_dil = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    inpaint_mask = cv2.dilate(mask, k_dil, iterations=1)
    radius = int(pr_cfg.get("inpaint_radius_px", 9))

    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    inpainted_bgr = cv2.inpaint(bgr, inpaint_mask, radius, cv2.INPAINT_TELEA)
    inpainted_rgb = cv2.cvtColor(inpainted_bgr, cv2.COLOR_BGR2RGB)

    # Soft feathered alpha blend on mask edges
    sigma = float(pr_cfg.get("feather_sigma", 2.0))
    alpha = cv2.GaussianBlur(inpaint_mask.astype(np.float32) / 255.0, (0, 0), sigmaX=sigma)
    alpha = np.clip(alpha, 0.0, 1.0)[..., None]
    out_rgb = np.clip(inpainted_rgb.astype(np.float32) * alpha + rgb.astype(np.float32) * (1.0 - alpha), 0, 255).astype(np.uint8)

    # Re-measure residual patches after repair
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
        "patches": patches[:40],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--input-dir", required=True, help="Directory with <variant_id>_*.png textures")
    ap.add_argument("--output-dir", required=True, help="Directory to write repaired <variant_id>_repaired.png")
    ap.add_argument("--report-out", required=True)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    pr_cfg = cfg["patch_repair"]
    in_dir = Path(args.input_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {"stage": "C_patch_repair", "asset_id": cfg["asset_id"], "variants": {}}
    for var in cfg["variants"]:
        vid = var["id"]
        cands = sorted(in_dir.glob(f"{vid}_*.png"))
        if not cands:
            raise FileNotFoundError(f"No input texture for {vid} in {in_dir}")
        src = cands[0]
        rgb = np.asarray(Image.open(src).convert("RGB"), dtype=np.uint8)
        repaired, stats = repair_texture(rgb, pr_cfg)
        dst = out_dir / f"{vid}_repaired.png"
        Image.fromarray(repaired, mode="RGB").save(dst)
        summary["variants"][vid] = {"src": str(src), "dst": str(dst), **stats}
        print(
            f"[stage_c] {vid}: patches={stats['patches_detected']} "
            f"texels {stats['patch_texels_before_pct']}% -> {stats['patch_texels_after_pct']}%",
            flush=True,
        )

    Path(args.report_out).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("STAGE_C_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
