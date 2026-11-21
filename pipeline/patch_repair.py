#!/usr/bin/env python3
"""Universal Asset Texture Painting — Stage C v2 (Luminance Patches + Coherent-Neighborhood Color Outliers + VLM Triage).

Asset-agnostic detectors:
  1. Bright isolated patches in dark surfaces (luminance);
  2. Dark isolated specks in bright surfaces (2D + 3D UV island coherence with photo guard);
  3. Hue/color outliers in Lab space (CIE76 Delta-E vs local median) with shape compactness
     (excludes elongated seams), coherent ring check (excludes material transitions),
     UV island border guard, photo-consistency guard, and optional GLM Vision VLM triage
     (with conservative fallback when offline/no key).
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
from pathlib import Path

import cv2
import numpy as np
import trimesh
from PIL import Image


def _rgb_to_cie_lab(rgb: np.ndarray) -> np.ndarray:
    """Converts uint8 RGB to float32 CIE Lab (L in [0,100], a/b in [-128,127])."""
    lab_u8 = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    lab = np.empty_like(lab_u8)
    lab[..., 0] = lab_u8[..., 0] * (100.0 / 255.0)
    lab[..., 1] = lab_u8[..., 1] - 128.0
    lab[..., 2] = lab_u8[..., 2] - 128.0
    return lab


def rasterize_uv_mask(uv_obj_path: Path | None, h: int, w: int) -> np.ndarray | None:
    """Rasterizes UV triangles of uv_obj_path into a uint8 mask (255 inside UV islands, 0 outside)."""
    if uv_obj_path is None or not uv_obj_path.is_file():
        return None
    try:
        mesh = trimesh.load(str(uv_obj_path), force="mesh", process=False)
        uv = getattr(mesh.visual, "uv", None)
        if uv is None or len(uv) != len(mesh.vertices):
            return None
        uv_px = np.empty_like(uv, dtype=np.float32)
        uv_px[:, 0] = np.clip(uv[:, 0], 0.0, 1.0) * (w - 1)
        uv_px[:, 1] = (1.0 - np.clip(uv[:, 1], 0.0, 1.0)) * (h - 1)
        faces = np.asarray(mesh.faces, dtype=np.int32)
        tris = np.round(uv_px[faces]).astype(np.int32)
        mask = np.zeros((h, w), dtype=np.uint8)
        for tri in tris:
            cv2.fillConvexPoly(mask, tri, 255)
        return mask
    except Exception:
        return None


def _load_zai_vlm_credentials() -> tuple[str, str]:
    key = os.environ.get("ZAI_API_KEY", "").strip()
    url = os.environ.get("ZAI_API_URL", "https://api.z.ai/api/coding/paas/v4/chat/completions").strip()
    if not key:
        worker_env = Path(__file__).resolve().parent.parent / "factory" / "worker" / ".env"
        if worker_env.is_file():
            for line in worker_env.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == "ZAI_API_KEY":
                    key = v.strip().strip('"').strip("'")
                elif k.strip() == "ZAI_API_URL":
                    url = v.strip().strip('"').strip("'")
    return key, url


def _vlm_triage_crop(rgb: np.ndarray, bbox: tuple[int, int, int, int], model: str, api_key: str, api_url: str) -> tuple[str | None, str]:
    """Queries GLM Vision API with a focused crop around bbox (x, y, bw, bh).
    Returns ('defect' | 'detail' | None, note)."""
    try:
        import httpx

        h, w, _ = rgb.shape
        x, y, bw, bh = bbox
        pad = max(36, int(max(bw, bh) * 2.5))
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(w, x + bw + pad), min(h, y + bh + pad)
        crop = rgb[y0:y1, x0:x1].copy()
        # Draw thin green box highlighting candidate region
        cv2.rectangle(crop, (x - x0, y - y0), (x - x0 + bw, y - y0 + bh), (0, 255, 80), 2)
        crop_resized = cv2.resize(crop, (256, 256), interpolation=cv2.INTER_AREA)

        buf = io.BytesIO()
        Image.fromarray(crop_resized, mode="RGB").save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        r = httpx.post(
            api_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "In this 3D texture crop, is the small region inside the green rectangle "
                                "a painting defect/stray speckle or a legitimate painted detail (like eyes, "
                                "teeth, seam, shading, or logo)? Reply ONLY one word: defect or detail."
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                }],
                "max_tokens": 24,
                "temperature": 0.0,
                "thinking": {"type": "disabled"},
            },
            timeout=25,
        )
        if r.status_code != 200:
            return None, f"http_{r.status_code}"
        reply = (r.json()["choices"][0]["message"].get("content") or "").strip().lower()
        if "defect" in reply and "detail" not in reply:
            return "defect", reply[:40]
        if "detail" in reply:
            return "detail", reply[:40]
        return None, f"ambiguous:{reply[:40]}"
    except Exception as e:
        return None, f"error:{str(e)[:60]}"


def detect_bright_patches_in_dark(
    rgb: np.ndarray,
    pr_cfg: dict,
    allow_vlm: bool = False,
) -> tuple[np.ndarray, list[dict]]:
    """Returns (uint8 binary mask 0/255 of defective patches, list of patch metadata).

    When pr_cfg.get('vlm_guard_bright_in_dark', True) is enabled and allow_vlm=True,
    bright-in-dark candidates (which can be legitimate teeth/eyes) are triaged via GLM Vision
    (or conservatively skipped when VLM is unavailable).
    """
    h, w, _ = rgb.shape
    lum = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]).astype(np.float32)

    bright_min = float(pr_cfg.get("bright_lum_min", 180))
    dark_max = float(pr_cfg.get("dark_ring_lum_max", 85))
    delta_min = float(pr_cfg.get("delta_lum_min", 95))
    peri_min = float(pr_cfg.get("dark_perimeter_ratio_min", 0.70))
    min_px = int(pr_cfg.get("min_component_px", 12))
    max_px = int(float(pr_cfg.get("max_component_area_ratio", 0.015)) * h * w)
    ring_w = int(pr_cfg.get("ring_width_px", 6))

    vlm_guard = bool(pr_cfg.get("vlm_guard_bright_in_dark", True))
    vlm_enabled = bool(pr_cfg.get("vlm_triage_enabled", True)) and allow_vlm
    vlm_model = str(pr_cfg.get("vlm_triage_model", "glm-4.5v"))
    vlm_max_calls = int(pr_cfg.get("vlm_triage_max_calls", 20))
    api_key, api_url = _load_zai_vlm_credentials() if vlm_enabled else ("", "")
    vlm_available = bool(vlm_enabled and api_key)
    vlm_calls = 0

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
            if vlm_guard and allow_vlm:
                if vlm_available and vlm_calls < vlm_max_calls:
                    vlm_calls += 1
                    verdict, _ = _vlm_triage_crop(rgb, (x, y, bw, bh), vlm_model, api_key, api_url)
                    if verdict != "defect":
                        continue
                else:
                    # Conservative mode: do NOT erase bright-in-dark (teeth/eyes) without VLM approval
                    continue
            elif vlm_guard and not allow_vlm and pr_cfg.get("conservative_bright_in_dark", False):
                continue

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
    """Generic symmetric detector: small isolated dark specks inside coherent bright surfaces."""
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


def detect_color_outliers(
    rgb: np.ndarray,
    pr_cfg: dict,
    uv_mask: np.ndarray | None = None,
    photo_ref_rgb: np.ndarray | None = None,
    photo_cos: np.ndarray | None = None,
    allow_vlm: bool = True,
) -> tuple[np.ndarray, dict]:
    """Universal Lab-space color outlier detector with compactness, coherent ring, UV border guard,
    photo-consistency guard, and optional GLM Vision VLM triage (conservative fallback offline)."""
    h, w, _ = rgb.shape
    total_px = h * w

    de_min = float(pr_cfg.get("outlier_delta_e_min", 35.0))
    ksize = int(pr_cfg.get("outlier_median_ksize", 21))
    if ksize % 2 == 0:
        ksize += 1
    min_px = int(pr_cfg.get("outlier_min_px", 6))
    max_px = max(min_px + 1, int(float(pr_cfg.get("outlier_max_area_ratio", 0.0008)) * total_px))
    max_aspect = float(pr_cfg.get("outlier_max_aspect_ratio", 4.0))
    ring_w = int(pr_cfg.get("outlier_ring_width_px", 9))
    ring_coh_de = float(pr_cfg.get("outlier_ring_coherent_delta_e", 25.0))
    ring_coh_min = float(pr_cfg.get("outlier_ring_coherent_ratio_min", 0.60))
    uv_border_max = float(pr_cfg.get("outlier_uv_border_ratio_max", 0.30))

    vlm_enabled = bool(pr_cfg.get("vlm_triage_enabled", True)) and allow_vlm
    vlm_min_px = int(pr_cfg.get("vlm_triage_min_px", 120))
    vlm_model = str(pr_cfg.get("vlm_triage_model", "glm-4.5v"))
    vlm_max_calls = int(pr_cfg.get("vlm_triage_max_calls", 20))

    guard_cos = float(pr_cfg.get("photo_guard_cos_min", 0.80))

    lab_u8 = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    med_u8 = cv2.medianBlur(lab_u8, ksize)

    # Exact CIE76 Delta-E from OpenCV Lab
    dL = (lab_u8[..., 0].astype(np.float32) - med_u8[..., 0].astype(np.float32)) * (100.0 / 255.0)
    da = lab_u8[..., 1].astype(np.float32) - med_u8[..., 1].astype(np.float32)
    db = lab_u8[..., 2].astype(np.float32) - med_u8[..., 2].astype(np.float32)
    delta_e = np.sqrt(dL * dL + da * da + db * db)

    lab_f = _rgb_to_cie_lab(rgb)
    photo_lab = _rgb_to_cie_lab(photo_ref_rgb) if photo_ref_rgb is not None else None

    out_bin = (delta_e > de_min).astype(np.uint8)
    if uv_mask is not None:
        out_bin[uv_mask == 0] = 0

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(out_bin, connectivity=8)

    k_ring = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ring_w + 1, 2 * ring_w + 1))
    k3 = np.ones((3, 3), dtype=np.uint8)

    api_key, api_url = _load_zai_vlm_credentials() if vlm_enabled else ("", "")
    vlm_available = bool(vlm_enabled and api_key)
    vlm_calls = 0

    repair_mask = np.zeros((h, w), dtype=np.uint8)
    accepted: list[dict] = []
    vlm_deferred: list[dict] = []
    vlm_protected: list[dict] = []
    photo_blocked: list[dict] = []
    rejected_shape = 0
    rejected_ring = 0
    rejected_uv_border = 0

    for lbl in range(1, num_labels):
        area = int(stats[lbl, cv2.CC_STAT_AREA])
        if area < min_px or area > max_px:
            continue

        x = int(stats[lbl, cv2.CC_STAT_LEFT])
        y = int(stats[lbl, cv2.CC_STAT_TOP])
        bw = int(stats[lbl, cv2.CC_STAT_WIDTH])
        bh = int(stats[lbl, cv2.CC_STAT_HEIGHT])

        # Shape compactness filter: exclude elongated seams / lines
        aspect = float(max(bw, bh)) / float(max(1, min(bw, bh)))
        if aspect >= max_aspect:
            rejected_shape += 1
            continue

        pad = ring_w + 2
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(w, x + bw + pad), min(h, y + bh + pad)

        comp_roi = (labels[y0:y1, x0:x1] == lbl).astype(np.uint8)

        # UV island border guard: skip if >30% of component perimeter touches UV atlas border
        if uv_mask is not None:
            uv_roi = uv_mask[y0:y1, x0:x1]
            eroded = cv2.erode(comp_roi, k3, iterations=1)
            perim = (comp_roi > 0) & (eroded == 0)
            if perim.any():
                # Perimeter pixels whose 8-neighborhood touches outside UV mask
                outside_uv = (uv_roi == 0).astype(np.uint8)
                near_outside = cv2.dilate(outside_uv, k3, iterations=1) > 0
                border_touch_ratio = float((perim & near_outside).sum()) / float(perim.sum())
                if border_touch_ratio > uv_border_max:
                    rejected_uv_border += 1
                    continue

        # Coherent ring check
        dil = cv2.dilate(comp_roi, k_ring, iterations=1)
        ring = (dil > 0) & (comp_roi == 0)
        if uv_mask is not None:
            ring = ring & (uv_mask[y0:y1, x0:x1] > 0)
        if ring.sum() < 8:
            continue

        lab_roi = lab_f[y0:y1, x0:x1]
        ring_lab = lab_roi[ring]
        ring_med = np.median(ring_lab, axis=0)
        ring_de = np.linalg.norm(ring_lab - ring_med[None, :], axis=1)
        coh_ratio = float((ring_de <= ring_coh_de).mean())
        if coh_ratio < ring_coh_min:
            rejected_ring += 1
            continue

        comp_lab = lab_roi[comp_roi > 0]
        comp_med = np.median(comp_lab, axis=0)
        comp_de = float(np.linalg.norm(comp_med - ring_med))
        if comp_de < de_min * 0.85:
            continue

        cx, cy = float(centroids[lbl][0]), float(centroids[lbl][1])
        is_bright_in_dark = bool(comp_med[0] > (ring_med[0] + 15.0) and ring_med[0] < 45.0)
        meta = {
            "area_px": area,
            "bbox_px": [x, y, bw, bh],
            "uv_center": [round(cx / w, 4), round(1.0 - cy / h, 4)],
            "aspect": round(aspect, 2),
            "delta_e": round(comp_de, 1),
            "ring_coherence": round(coh_ratio, 3),
            "comp_L": round(float(comp_med[0]), 1),
            "ring_L": round(float(ring_med[0]), 1),
            "bright_in_dark": is_bright_in_dark,
        }

        # Photo-consistency guard (tier photos)
        if photo_lab is not None and photo_cos is not None:
            c_mask = comp_roi > 0
            cos_vals = photo_cos[y0:y1, x0:x1][c_mask]
            if (cos_vals >= guard_cos).mean() >= 0.4:
                p_med = np.median(photo_lab[y0:y1, x0:x1][c_mask], axis=0)
                if float(np.linalg.norm(p_med - ring_med)) >= ring_coh_de:
                    meta["photo_guard"] = "blocked"
                    photo_blocked.append(meta)
                    continue

        # VLM triage gate for larger regions (> vlm_min_px) OR bright-in-dark (teeth/eyes)
        needs_triage = bool(area > vlm_min_px or is_bright_in_dark)
        if needs_triage:
            if vlm_available and vlm_calls < vlm_max_calls:
                vlm_calls += 1
                verdict, note = _vlm_triage_crop(rgb, (x, y, bw, bh), vlm_model, api_key, api_url)
                meta["vlm_verdict"] = verdict or "error"
                meta["vlm_note"] = note
                if verdict == "detail":
                    vlm_protected.append(meta)
                    continue
                elif verdict is None:
                    # Conservative on VLM error: defer instead of risking detail erasure
                    meta["defer_reason"] = f"vlm_error:{note}"
                    vlm_deferred.append(meta)
                    continue
                # verdict == "defect" -> proceed to repair
            else:
                meta["defer_reason"] = "conservative_no_vlm" if not vlm_available else "vlm_budget_reached"
                vlm_deferred.append(meta)
                continue

        repair_mask[y0:y1, x0:x1][comp_roi > 0] = 255
        accepted.append(meta)

    info = {
        "count": len(accepted),
        "texels": int((repair_mask > 0).sum()),
        "texels_pct": round(float((repair_mask > 0).sum()) / float(total_px) * 100.0, 4),
        "vlm_enabled": vlm_available,
        "vlm_model": vlm_model if vlm_available else "conservative_offline",
        "vlm_calls": vlm_calls,
        "vlm_protected_count": len(vlm_protected),
        "vlm_deferred_count": len(vlm_deferred),
        "photo_blocked_count": len(photo_blocked),
        "rejected_shape_elongated": rejected_shape,
        "rejected_ring_incoherent": rejected_ring,
        "rejected_uv_border": rejected_uv_border,
        "vlm_protected": vlm_protected[:30],
        "vlm_deferred": vlm_deferred[:30],
        "samples": accepted[:40],
    }
    return repair_mask, info


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
    uv_mask: np.ndarray | None = None,
    photo_ref_rgb: np.ndarray | None = None,
    allow_vlm: bool = True,
) -> tuple[np.ndarray, dict]:
    # When repairing bright-in-dark, apply VLM guard (or conservative skip when offline)
    pr_bright = dict(pr_cfg)
    if not allow_vlm or not pr_cfg.get("vlm_triage_enabled", True):
        pr_bright["conservative_bright_in_dark"] = True
    mask, patches = detect_bright_patches_in_dark(rgb, pr_bright, allow_vlm=allow_vlm)
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

    # v2: Coherent-neighborhood Lab color outliers + VLM triage
    co_before = {"count": 0, "texels": 0, "texels_pct": 0.0, "vlm_deferred": [], "vlm_protected": []}
    co_after = {"count": 0, "texels": 0, "texels_pct": 0.0}
    if pr_cfg.get("repair_color_outliers", True):
        cmask, co_before = detect_color_outliers(
            out_rgb, pr_cfg, uv_mask=uv_mask, photo_ref_rgb=photo_ref_rgb, photo_cos=photo_cos, allow_vlm=allow_vlm
        )
        if co_before["count"] > 0:
            out_rgb = _apply_telea_feather(out_rgb, cmask, radius, sigma, dilate_px=2)
        _, co_after = detect_color_outliers(
            out_rgb, pr_cfg, uv_mask=uv_mask, photo_ref_rgb=photo_ref_rgb, photo_cos=photo_cos, allow_vlm=False
        )

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
        "color_outliers_before": {
            "count": co_before["count"],
            "texels": co_before["texels"],
            "texels_pct": co_before["texels_pct"],
            "rejected_shape_elongated": co_before.get("rejected_shape_elongated", 0),
            "rejected_ring_incoherent": co_before.get("rejected_ring_incoherent", 0),
            "rejected_uv_border": co_before.get("rejected_uv_border", 0),
        },
        "color_outliers_after": {
            "count": co_after["count"],
            "texels": co_after["texels"],
            "texels_pct": co_after["texels_pct"],
        },
        "vlm_triage": {
            "enabled": co_before.get("vlm_enabled", False),
            "model": co_before.get("vlm_model", "conservative_offline"),
            "calls": co_before.get("vlm_calls", 0),
            "protected_count": co_before.get("vlm_protected_count", 0),
            "deferred_count": co_before.get("vlm_deferred_count", 0),
        },
        "vlm_protected": co_before.get("vlm_protected", []),
        "vlm_deferred": co_before.get("vlm_deferred", []),
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
    ap.add_argument("--no-vlm", action="store_true", help="Force conservative offline triage without VLM API calls")
    ap.add_argument("--report-only", action="store_true", help="Detect and report defects/outliers without modifying texture")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    pr_cfg = cfg["patch_repair"]
    in_dir = Path(args.input_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pref_dir = Path(args.photo_ref_dir) if args.photo_ref_dir else None

    summary = {"stage": "C_patch_repair_v2", "asset_id": cfg["asset_id"], "variants": {}}
    for var in cfg["variants"]:
        vid = var["id"]
        cands = [p for p in sorted(in_dir.glob(f"{vid}_*.png")) if "overlay" not in p.name and "heatmap" not in p.name and "photo_ref" not in p.name]
        if not cands:
            raise FileNotFoundError(f"No input texture for {vid} in {in_dir}")
        src = cands[0]
        rgb = np.asarray(Image.open(src).convert("RGB"), dtype=np.uint8)

        photo_ref_rgb = None
        photo_ref_lum = None
        photo_cos = None
        if pref_dir and pref_dir.exists():
            ref_cands = sorted(pref_dir.glob(f"{vid}_photo_ref_*.png"))
            cos_cands = sorted(pref_dir.glob(f"{vid}_photo_cos_*.npy"))
            if ref_cands and cos_cands:
                photo_ref_rgb = np.asarray(Image.open(ref_cands[0]).convert("RGB"), dtype=np.uint8)
                ref_f = photo_ref_rgb.astype(np.float32)
                photo_ref_lum = 0.299 * ref_f[..., 0] + 0.587 * ref_f[..., 1] + 0.114 * ref_f[..., 2]
                photo_cos = np.load(cos_cands[0]).astype(np.float32)

        uv_obj = Path(var["uv_obj"])
        uv_mask = rasterize_uv_mask(uv_obj, rgb.shape[0], rgb.shape[1])

        repaired, stats = repair_texture(
            rgb,
            pr_cfg,
            photo_ref_lum=photo_ref_lum,
            photo_cos=photo_cos,
            uv_mask=uv_mask,
            photo_ref_rgb=photo_ref_rgb,
            allow_vlm=(not args.no_vlm),
        )
        if uv_obj.exists() and pr_cfg.get("repair_dark_specks", False) and not args.report_only:
            repaired, fixed_3d, blocked_3d = repair_3d_uv_island_specks(uv_obj, repaired, pr_cfg, photo_ref_lum, photo_cos)
            stats["dark_3d_uv_islands_repaired"] = fixed_3d
            stats["blocked_by_photo_guard_3d"] = blocked_3d
        dst = out_dir / f"{vid}_repaired.png"
        if args.report_only:
            stats["mode"] = "report_only"
            Image.fromarray(rgb, mode="RGB").save(dst)
        else:
            stats["mode"] = "repair"
            Image.fromarray(repaired, mode="RGB").save(dst)
        summary["variants"][vid] = {"src": str(src), "dst": str(dst), **stats}
        cob = stats["color_outliers_before"]
        coa = stats["color_outliers_after"]
        vlm = stats["vlm_triage"]
        print(
            f"[stage_c] {vid}: bright={stats['patches_detected']} ({stats['patch_texels_before_pct']}%->{stats['patch_texels_after_pct']}%) | "
            f"dark_2d={stats.get('dark_specks_detected', 0)} | dark_3d={stats.get('dark_3d_uv_islands_repaired', 0)} | "
            f"color_outliers={cob['count']}({cob['texels_pct']}%)->{coa['count']}({coa['texels_pct']}%) | "
            f"vlm(calls={vlm['calls']}, protected={vlm['protected_count']}, deferred={vlm['deferred_count']})",
            flush=True,
        )

    Path(args.report_out).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("STAGE_C_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
