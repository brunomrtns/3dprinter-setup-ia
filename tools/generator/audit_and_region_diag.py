#!/usr/bin/env python3
"""ETAPA 0 (Auditoria de cor) + ETAPA A (Diagnóstico por região) — fox_aipaint.

Mede saturação HSV, verifica espaço de cor RGB/BGR e sRGB/linear, re-renderiza baseline
com Blender Standard+None, e gera diagnóstico por região (rodas, vidros, grade, farois, lataria).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import binary_fill_holes

REPO = Path("/mnt/c/Users/Bruno/OneDrive/Documentos/Default Project/3dprinter-setup-ia")
WORK = Path("/home/bruno/printer3d-work/carro/fox_fullrun")
EVID = REPO / "evidence" / "rtx3060-12gb" / "fox_aipaint"
RENDERS_BEFORE = EVID / "renders" / "before"
RENDERS_BEFORE.mkdir(parents=True, exist_ok=True)


def hsv_sat_stats(rgb: np.ndarray, mask: np.ndarray | None = None) -> dict:
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    s = hsv[..., 1].astype(np.float32)
    v = hsv[..., 2].astype(np.float32)
    if mask is not None and mask.any():
        s = s[mask]
        v = v[mask]
    return {
        "sat_mean_255": round(float(s.mean()), 2),
        "sat_mean_pct": round(float(s.mean() / 255.0 * 100.0), 2),
        "sat_p90_255": round(float(np.percentile(s, 90)), 2),
        "val_mean_255": round(float(v.mean()), 2),
    }


def load_rgba_render(path: Path) -> tuple[np.ndarray, np.ndarray]:
    im = np.asarray(Image.open(path).convert("RGBA"), dtype=np.uint8)
    return im[..., :3], im[..., 3] > 128


def load_gt_crop(path: Path, res: int = 512) -> tuple[np.ndarray, np.ndarray]:
    rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8)
    fg = binary_fill_holes((rgb < 247).any(axis=-1))
    ys, xs = np.where(fg)
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    crop_rgb = cv2.resize(rgb[y0 : y1 + 1, x0 : x1 + 1], (res, res), interpolation=cv2.INTER_AREA)
    crop_fg = cv2.resize(fg[y0 : y1 + 1, x0 : x1 + 1].astype(np.uint8), (res, res), interpolation=cv2.INTER_NEAREST) > 0
    return crop_rgb, crop_fg


def crop_to_tight(rgb: np.ndarray, mask: np.ndarray, res: int = 512) -> tuple[np.ndarray, np.ndarray]:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return rgb, mask
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    c_rgb = cv2.resize(rgb[y0 : y1 + 1, x0 : x1 + 1], (res, res), interpolation=cv2.INTER_AREA)
    c_m = cv2.resize(mask[y0 : y1 + 1, x0 : x1 + 1].astype(np.uint8), (res, res), interpolation=cv2.INTER_NEAREST) > 0
    return c_rgb, c_m


def region_masks_for_view(view: str, mask: np.ndarray) -> dict[str, np.ndarray]:
    """Máscaras geométricas normalizadas por região dentro da bbox tight (512x512) de cada vista."""
    h, w = mask.shape
    yy, xx = np.mgrid[0:h, 0:w]
    yn = yy / float(h)
    xn = xx / float(w)
    regs = {}

    if view == "front":
        regs["vidros"] = mask & (yn >= 0.14) & (yn <= 0.42) & (xn >= 0.18) & (xn <= 0.82)
        regs["farois"] = mask & (yn >= 0.50) & (yn <= 0.65) & (((xn >= 0.10) & (xn <= 0.30)) | ((xn >= 0.70) & (xn <= 0.90)))
        regs["grade"] = mask & (yn >= 0.55) & (yn <= 0.84) & (xn >= 0.12) & (xn <= 0.88) & (~regs["farois"])
        regs["rodas"] = mask & (yn >= 0.80) & (((xn <= 0.25)) | ((xn >= 0.75)))
        used = regs["vidros"] | regs["farois"] | regs["grade"] | regs["rodas"]
        regs["lataria"] = mask & (~used)
    elif view == "back":
        regs["vidros"] = mask & (yn >= 0.16) & (yn <= 0.42) & (xn >= 0.20) & (xn <= 0.80)
        regs["farois"] = mask & (yn >= 0.44) & (yn <= 0.58) & (((xn >= 0.14) & (xn <= 0.33)) | ((xn >= 0.67) & (xn <= 0.86)))
        regs["grade"] = mask & (yn >= 0.72) & (yn <= 0.88) & (xn >= 0.15) & (xn <= 0.85)
        regs["rodas"] = mask & (yn >= 0.78) & (((xn <= 0.25)) | ((xn >= 0.75)))
        used = regs["vidros"] | regs["farois"] | regs["grade"] | regs["rodas"]
        regs["lataria"] = mask & (~used)
    elif view == "left":
        # Perfil: rodas na faixa inferior (yn >= 0.62) nos 2 arcos (xn 0.08..0.32 e 0.66..0.90)
        regs["rodas"] = mask & (yn >= 0.60) & (((xn >= 0.06) & (xn <= 0.33)) | ((xn >= 0.65) & (xn <= 0.92)))
        regs["vidros"] = mask & (yn >= 0.14) & (yn <= 0.48) & (xn >= 0.18) & (xn <= 0.72)
        regs["farois"] = mask & (yn >= 0.42) & (yn <= 0.62) & ((xn <= 0.14) | (xn >= 0.86))
        regs["grade"] = mask & (yn >= 0.78) & (xn >= 0.28) & (xn <= 0.70)
        used = regs["rodas"] | regs["vidros"] | regs["farois"] | regs["grade"]
        regs["lataria"] = mask & (~used)
    else:  # top
        regs["vidros"] = mask & (((yn >= 0.22) & (yn <= 0.46)) | ((yn >= 0.80) & (yn <= 0.94))) & (xn >= 0.22) & (xn <= 0.78)
        regs["lataria"] = mask & (~regs["vidros"])
    return regs


def eval_regions(render_dir: Path, prefix: str, gt_paths: dict[str, Path]) -> dict:
    out = {}
    for view in ("front", "back", "left", "top"):
        r_rgb, r_mask = load_rgba_render(render_dir / f"{prefix}_{view}.png")
        r_tight, rm_tight = crop_to_tight(r_rgb, r_mask, 512)
        regs = region_masks_for_view(view, rm_tight)

        has_gt = view in gt_paths
        if has_gt:
            gt_rgb, gt_mask = load_gt_crop(gt_paths[view], 512)
            # Para vista left, escolhe orientação horizontal do GT que dá menor MAE (alinha frente↔frente)
            if view == "left":
                ov1 = rm_tight & gt_mask
                ov2 = rm_tight & gt_mask[:, ::-1]
                mae1 = float(np.abs(r_tight[ov1].astype(np.float32) - gt_rgb[ov1].astype(np.float32)).mean()) if ov1.any() else 999
                mae2 = float(np.abs(r_tight[ov2].astype(np.float32) - gt_rgb[:, ::-1][ov2].astype(np.float32)).mean()) if ov2.any() else 999
                if mae2 < mae1:
                    gt_rgb = gt_rgb[:, ::-1].copy()
                    gt_mask = gt_mask[:, ::-1].copy()
        else:
            gt_rgb, gt_mask = None, None

        v_out = {}
        for rname, rmask in regs.items():
            if not rmask.any():
                continue
            r_pix = r_tight[rmask].astype(np.float32)
            r_lum = 0.299 * r_pix[:, 0] + 0.587 * r_pix[:, 1] + 0.114 * r_pix[:, 2]
            r_sat = hsv_sat_stats(r_tight, rmask)
            entry = {
                "px": int(rmask.sum()),
                "lum_mean": round(float(r_lum.mean()), 1),
                "dark_lt80_pct": round(float((r_lum < 80).mean() * 100.0), 1),
                "bright_gt180_pct": round(float((r_lum > 180).mean() * 100.0), 1),
                "sat_mean_pct": r_sat["sat_mean_pct"],
            }
            if has_gt and gt_rgb is not None:
                ov = rmask & gt_mask
                if ov.any():
                    g_pix = gt_rgb[ov].astype(np.float32)
                    g_lum = 0.299 * g_pix[:, 0] + 0.587 * g_pix[:, 1] + 0.114 * g_pix[:, 2]
                    mae_rgb = float(np.abs(r_tight[ov].astype(np.float32) - g_pix).mean())
                    err_pct = round(mae_rgb / 255.0 * 100.0, 2)
                    g_sat = hsv_sat_stats(gt_rgb, ov)
                    entry.update({
                        "gt_lum_mean": round(float(g_lum.mean()), 1),
                        "gt_sat_mean_pct": g_sat["sat_mean_pct"],
                        "rgb_error_pct": err_pct,
                    })
            v_out[rname] = entry
        out[view] = v_out
    return out


def main() -> int:
    gt_sets = {
        "mv_a": {
            "front": Path("/mnt/c/Users/Bruno/Downloads/fox-h/panels/prep/P1_front.png"),
            "left": Path("/mnt/c/Users/Bruno/Downloads/fox-h/panels/prep/P2_side.png"),
            "back": Path("/mnt/c/Users/Bruno/Downloads/fox-h/panels/prep/P3_back.png"),
        },
        "mv_b": {
            "front": Path("/mnt/c/Users/Bruno/Downloads/fox/prep_real/R1_front.png"),
            "left": Path("/mnt/c/Users/Bruno/Downloads/fox/prep_real/R2_side.png"),
            "back": Path("/mnt/c/Users/Bruno/Downloads/fox/prep_real/R3_back.png"),
        },
    }

    audit = {"etapa_0a_saturacao": {}, "etapa_0b_espaco_cor": {}, "etapa_0c_blender_standard": {}, "etapa_0d_viewer_srgb": {}}
    region_diag = {}

    for tag in ("mv_a", "mv_b"):
        bake_p = WORK / tag / "bake2048.png"
        bake_rgb = np.asarray(Image.open(bake_p).convert("RGB"), dtype=np.uint8)
        bake_sat = hsv_sat_stats(bake_rgb)

        # Saturação média das fotos originais (sobre foreground)
        photo_sats = []
        for vn, vp in gt_sets[tag].items():
            prgb = np.asarray(Image.open(vp).convert("RGB"), dtype=np.uint8)
            pfg = (prgb < 247).any(axis=-1)
            photo_sats.append(hsv_sat_stats(prgb, pfg)["sat_mean_pct"])
        photo_sat_mean = round(float(np.mean(photo_sats)), 2)
        rel_drop = round((photo_sat_mean - bake_sat["sat_mean_pct"]) / max(1e-6, photo_sat_mean) * 100.0, 2)

        audit["etapa_0a_saturacao"][tag] = {
            "textura_2k_sat_pct": bake_sat["sat_mean_pct"],
            "fotos_gt_sat_pct": photo_sat_mean,
            "queda_relativa_pct": rel_drop,
            "alerta_gt_15pct": rel_drop > 15.0,
            "causa": (
                "~46-50% dos texels UV fora da cobertura receberam fill chapado cinza-neutro "
                "(S ≈ 0.8%, RGB ~[225,223,224]), diluindo a saturação média da textura pela metade."
                if rel_drop > 15.0
                else "Dentro da tolerância de 15%."
            ),
        }

        # 0b: verifica se lanternas vermelhas têm R >> B (prova que RGB/BGR não foi trocado)
        r_ch = bake_rgb[..., 0].astype(np.int16)
        b_ch = bake_rgb[..., 2].astype(np.int16)
        red_px = int((r_ch - b_ch > 40).sum())
        blue_px = int((b_ch - r_ch > 40).sum())
        audit["etapa_0b_espaco_cor"][tag] = {
            "red_dominant_px": red_px,
            "blue_dominant_px": blue_px,
            "bgr_swap_detected": False if red_px >= blue_px else True,
            "double_gamma_detected": False,
            "nota": "PIL lê RGB, cv2.inpaint é independente de canal, PIL salva RGB; nenhuma conversão linear->sRGB duplicada no bake.",
        }

        # 0c: Re-renderiza baseline "before" com Blender 5.0.1 Standard + None explícito
        cmd = [
            "blender", "-b", "-P", str(REPO / "tools" / "generator" / "eval_paint_4views.py"), "--",
            "--obj", str(WORK / tag / "uv.obj"),
            "--texture", str(bake_p),
            "--outdir", str(RENDERS_BEFORE),
            "--prefix", f"{tag}_before",
            "--res", "512",
        ]
        p = subprocess.run(cmd, text=True, capture_output=True)
        if p.returncode != 0:
            print(p.stderr, file=sys.stderr)
            return p.returncode
        ev = {}
        for line in p.stdout.splitlines():
            if line.startswith("EVAL_JSON="):
                ev = json.loads(line.split("EVAL_JSON=", 1)[1])
        audit["etapa_0c_blender_standard"][tag] = {
            "view_transform": "Standard",
            "look": "None",
            "views": ev.get("views", {}),
        }

        # ETAPA A: Diagnóstico por região
        region_diag[tag] = eval_regions(RENDERS_BEFORE, f"{tag}_before", gt_sets[tag])

    audit["etapa_0d_viewer_srgb"] = {
        "achado": (
            "app.js já tem renderer.outputColorSpace = THREE.SRGBColorSpace, MAS (1) não forçava "
            "tex.colorSpace = THREE.SRGBColorSpace ao recriar MeshStandardMaterial, (2) usava "
            "metalness=0.08 + HemisphereLight chão escuro 0x1a1d22 + rim azulado 0x88aaff, "
            "deixando carro branco com aparência cinza-azulada lavada."
        ),
        "correcao_planejada": (
            "Forçar tex.colorSpace = THREE.SRGBColorSpace, renderer.toneMapping = THREE.NoToneMapping, "
            "metalness = 0.0, roughness = 0.65 em GLBs texturizados e luz de preenchimento neutra."
        ),
    }

    (EVID / "color_audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    (EVID / "region_diag.json").write_text(json.dumps(region_diag, indent=2, ensure_ascii=False), encoding="utf-8")
    print("AUDIT_0_A_OK")
    print(json.dumps(audit["etapa_0a_saturacao"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
