#!/usr/bin/env python3
"""M5 — Assistente de Imagem (detector genérico de entrada fraca + provider abstraído mock/externo)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance


def analyze_input_quality(image_path: str | Path) -> dict[str, Any]:
    """Detects weak input images generically (resolution, luminance, foreground ratio)."""
    im = Image.open(image_path).convert("RGB")
    w, h = im.size
    arr = np.asarray(im, dtype=np.float32)
    lum = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
    fg = (arr < 247).any(axis=-1)
    fg_ratio = float(fg.mean())
    fg_lum = float(lum[fg].mean()) if fg.any() else float(lum.mean())

    issues: list[str] = []
    if min(w, h) < 512:
        issues.append(f"low_resolution ({w}x{h} < 512)")
    if fg_lum < 45.0:
        issues.append(f"too_dark (lum={fg_lum:.1f})")
    elif fg_lum > 245.0:
        issues.append(f"overexposed (lum={fg_lum:.1f})")
    if fg_ratio > 0.96:
        issues.append(f"complex_or_untrimmed_background (fg={fg_ratio*100:.1f}%)")

    return {
        "width": w,
        "height": h,
        "fg_ratio": round(fg_ratio, 3),
        "fg_lum_mean": round(fg_lum, 1),
        "weak_input": len(issues) > 0,
        "issues": issues,
        "offer_external_rerender": len(issues) > 0,
    }


def enhance_image(image_path: str | Path, out_path: str | Path, provider: str | None = None) -> dict[str, Any]:
    """Optional image enhancement. Feature-flag OFF without API key -> falls back cleanly to mock/local."""
    enabled = os.environ.get("EXTERNAL_IMAGE_ENHANCE", "false").lower() == "true"
    prov = (provider or os.environ.get("IMAGE_PROVIDER", "mock")).lower()
    src = Path(image_path)
    dst = Path(out_path)
    dst.parent.mkdir(parents=True, exist_ok=True)

    if prov == "mock" or not enabled or not os.environ.get("GEMINI_API_KEY"):
        # Deterministic mock enhancement: normalized contrast/brightness on neutral canvas
        im = Image.open(src).convert("RGB")
        im = ImageEnhance.Contrast(im).enhance(1.06)
        im = ImageEnhance.Sharpness(im).enhance(1.08)
        im.save(dst)
        return {
            "provider_used": "mock_local",
            "external_enabled": enabled,
            "output_path": str(dst),
            "prompt": "clean product photo of the SAME object, neutral background, even lighting, centered",
        }

    # Placeholder hook for external Gemini/Nano Banana when enabled + GEMINI_API_KEY present in local .env
    im = Image.open(src).convert("RGB")
    im.save(dst)
    return {
        "provider_used": "gemini_configured_stub",
        "external_enabled": True,
        "output_path": str(dst),
    }
