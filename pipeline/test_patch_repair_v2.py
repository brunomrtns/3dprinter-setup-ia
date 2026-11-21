#!/usr/bin/env python3
"""Synthetic unit tests for pipeline/patch_repair.py v2 (detect_color_outliers + VLM conservative guard).

Verifies:
  1. Compact hue outliers (orange dots on blue fabric of similar luminance) ARE caught and repaired.
  2. Compact dark dots inside orange fur ARE caught and repaired.
  3. Elongated seam lines (aspect >= 4) on blue fabric are NOT touched.
  4. Bright teeth inside a dark mouth cavity (bright-in-dark) are NOT erased in conservative mode (deferred).
  5. Dots touching >30% of UV island border are NOT touched.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch_repair import detect_color_outliers, repair_texture  # noqa: E402


def main() -> int:
    h, w = 512, 512
    # Base canvas: left half = blue denim (lum ~118), right half = orange fur (lum ~132)
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    rgb[:, :256] = (45, 115, 210)
    rgb[:, 256:] = (225, 110, 35)

    # UV island mask: leave a 20px border around edges and an inner cutout
    uv_mask = np.zeros((h, w), dtype=np.uint8)
    uv_mask[20:492, 20:492] = 255

    # 1. Defect A: compact orange dot on blue fabric (same-ish luminance -> hue outlier!)
    cv2.circle(rgb, (110, 120), 4, (225, 115, 35), -1)
    # 2. Defect B: compact dark speck inside orange fur
    cv2.circle(rgb, (360, 140), 4, (25, 20, 18), -1)
    # 3. Legitimate seam: elongated light-blue stitch line on blue fabric (60x3 px -> aspect 20)
    rgb[260:263, 70:130] = (230, 210, 120)
    # 4. Legitimate teeth inside dark mouth cavity (bright-in-dark)
    cv2.rectangle(rgb, (300, 310), (420, 390), (20, 18, 22), -1)  # dark mouth
    rgb[345:355, 345:365] = (242, 240, 235)  # compact bright tooth (20x10 = 200px, bright in dark)
    # 5. UV border dot: orange dot touching >30% of perimeter on UV mask border (x=20..25, y=400..412 -> 12/30=40%)
    rgb[400:412, 20:25] = (230, 100, 20)

    pr_cfg = json.loads((Path(__file__).resolve().parent / "defaults.json").read_text(encoding="utf-8"))["patch_repair"]
    pr_cfg["vlm_triage_enabled"] = False  # deterministic offline conservative test

    mask, info = detect_color_outliers(rgb, pr_cfg, uv_mask=uv_mask, allow_vlm=False)

    # Assertions
    assert mask[120, 110] == 255, "FAIL: compact orange dot on blue fabric was NOT detected!"
    assert mask[140, 360] == 255, "FAIL: compact dark dot on orange fur was NOT detected!"
    assert mask[261, 100] == 0, "FAIL: elongated seam line was WRONGLY flagged!"
    assert mask[350, 355] == 0, "FAIL: bright tooth inside dark mouth was WRONGLY flagged!"
    assert mask[406, 22] == 0, "FAIL: UV-border dot was WRONGLY flagged!"
    assert info["vlm_deferred_count"] >= 1, f"FAIL: tooth should be in vlm_deferred, got {info}"
    assert info["rejected_shape_elongated"] >= 1, f"FAIL: seam should be rejected by shape, got {info}"
    assert info["rejected_uv_border"] >= 1, f"FAIL: border dot should be rejected by uv_border, got {info}"

    repaired, stats = repair_texture(rgb, pr_cfg, uv_mask=uv_mask, allow_vlm=False)
    # Verify orange dot on blue is now blue-ish (B > R)
    px_dot_a = repaired[120, 110]
    assert int(px_dot_a[2]) > int(px_dot_a[0]) + 50, f"FAIL: dot A not repaired to blue: {px_dot_a}"
    # Verify seam & tooth survived intact
    assert np.allclose(repaired[261, 100], (230, 210, 120), atol=5), f"FAIL: seam damaged: {repaired[261, 100]}"
    assert np.allclose(repaired[350, 355], (242, 240, 235), atol=5), f"FAIL: tooth damaged: {repaired[350, 355]}"

    print("UNIT_TEST_PATCH_REPAIR_V2_PASS")
    print(json.dumps({
        "before": stats["color_outliers_before"],
        "after": stats["color_outliers_after"],
        "vlm_deferred_count": stats["vlm_triage"]["deferred_count"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
