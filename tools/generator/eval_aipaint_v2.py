#!/usr/bin/env python3
"""ETAPA E — Avaliação v2 (cor certa, por região + crops lado a lado BEFORE vs FINAL)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_and_region_diag import crop_to_tight, eval_regions, hsv_sat_stats, load_rgba_render

REPO = Path("/mnt/c/Users/Bruno/OneDrive/Documentos/Default Project/3dprinter-setup-ia")
WORK = Path("/home/bruno/printer3d-work/carro/fox_fullrun")
EVID = REPO / "evidence" / "rtx3060-12gb" / "fox_aipaint"
RENDERS_BEFORE = EVID / "renders" / "before"
RENDERS_FINAL = EVID / "renders" / "final"
RENDERS_CROPS = EVID / "renders" / "crops"
RENDERS_FINAL.mkdir(parents=True, exist_ok=True)
RENDERS_CROPS.mkdir(parents=True, exist_ok=True)


def make_side_by_side_crop(
    before_path: Path,
    final_path: Path,
    box_norm: tuple[float, float, float, float],
    out_path: Path,
    label: str,
) -> None:
    """Recorta box_norm=(x0,y0,x1,y1) da bbox tight (512x512) de before e final e salva lado a lado."""
    b_rgb, b_m = load_rgba_render(before_path)
    f_rgb, f_m = load_rgba_render(final_path)
    bt, _ = crop_to_tight(b_rgb, b_m, 512)
    ft, _ = crop_to_tight(f_rgb, f_m, 512)

    x0, y0, x1, y1 = [int(round(v * 512)) for v in box_norm]
    cb = cv2.resize(bt[y0:y1, x0:x1], (256, 256), interpolation=cv2.INTER_NEAREST)
    cf = cv2.resize(ft[y0:y1, x0:x1], (256, 256), interpolation=cv2.INTER_NEAREST)

    canvas = Image.new("RGB", (512 + 8, 256 + 26), (24, 24, 28))
    canvas.paste(Image.fromarray(cb), (0, 26))
    canvas.paste(Image.fromarray(cf), (256 + 8, 26))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 6), f"{label} — BEFORE", fill=(230, 230, 230))
    draw.text((264 + 8, 6), f"{label} — FINAL", fill=(140, 255, 160))
    canvas.save(out_path)


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

    before_diag = json.loads((EVID / "region_diag.json").read_text(encoding="utf-8"))
    out = {"meshes": {}}

    for tag in ("mv_a", "mv_b"):
        tex_p = WORK / tag / "bake2048.png"
        cmd = [
            "blender", "-b", "-P", str(REPO / "tools" / "generator" / "eval_paint_4views.py"), "--",
            "--obj", str(WORK / tag / "uv.obj"),
            "--texture", str(tex_p),
            "--outdir", str(RENDERS_FINAL),
            "--prefix", f"{tag}_final",
            "--res", "512",
        ]
        p = subprocess.run(cmd, text=True, capture_output=True)
        if p.returncode != 0:
            print(p.stderr, file=sys.stderr)
            return p.returncode

        ev_global = {}
        for line in p.stdout.splitlines():
            if line.startswith("EVAL_JSON="):
                ev_global = json.loads(line.split("EVAL_JSON=", 1)[1])

        final_diag = eval_regions(RENDERS_FINAL, f"{tag}_final", gt_sets[tag])

        # Saturação da textura final vs fotos GT
        tex_rgb = np.asarray(Image.open(tex_p).convert("RGB"), dtype=np.uint8)
        tex_sat = hsv_sat_stats(tex_rgb)
        photo_sats = []
        for vp in gt_sets[tag].values():
            prgb = np.asarray(Image.open(vp).convert("RGB"), dtype=np.uint8)
            pfg = (prgb < 247).any(axis=-1)
            photo_sats.append(hsv_sat_stats(prgb, pfg)["sat_mean_pct"])
        gt_sat_mean = round(float(np.mean(photo_sats)), 2)

        # Avaliação específica de rodas (perfil left)
        rodas_left = final_diag.get("left", {}).get("rodas", {})
        rodas_dark = rodas_left.get("dark_lt80_pct", 0.0)
        rodas_lum = rodas_left.get("lum_mean", 255.0)
        rodas_ok = (rodas_dark >= 28.0) and (rodas_lum <= 145.0)

        # Gera crops lado a lado: rodas (left), farois (front), grade (front)
        make_side_by_side_crop(
            RENDERS_BEFORE / f"{tag}_before_left.png",
            RENDERS_FINAL / f"{tag}_final_left.png",
            (0.04, 0.56, 0.96, 1.00),
            RENDERS_CROPS / f"{tag}_crop_rodas.png",
            f"{tag} RODAS",
        )
        make_side_by_side_crop(
            RENDERS_BEFORE / f"{tag}_before_front.png",
            RENDERS_FINAL / f"{tag}_final_front.png",
            (0.06, 0.44, 0.94, 0.72),
            RENDERS_CROPS / f"{tag}_crop_farois.png",
            f"{tag} FAROIS",
        )
        make_side_by_side_crop(
            RENDERS_BEFORE / f"{tag}_before_front.png",
            RENDERS_FINAL / f"{tag}_final_front.png",
            (0.10, 0.54, 0.90, 0.92),
            RENDERS_CROPS / f"{tag}_crop_grade.png",
            f"{tag} GRADE",
        )

        out["meshes"][tag] = {
            "texture_sat_pct": tex_sat["sat_mean_pct"],
            "gt_photos_sat_pct": gt_sat_mean,
            "sat_delta_pct": round(tex_sat["sat_mean_pct"] - gt_sat_mean, 2),
            "rodas_eval_ok": rodas_ok,
            "rodas_left_metrics": rodas_left,
            "global_4views": ev_global.get("views", {}),
            "regions_before": before_diag.get(tag, {}),
            "regions_final": final_diag,
        }

    (EVID / "eval_v2.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("EVAL_V2_OK")
    for tag in ("mv_a", "mv_b"):
        m = out["meshes"][tag]
        print(
            f"[{tag}] tex_sat={m['texture_sat_pct']}% vs gt={m['gt_photos_sat_pct']}% "
            f"| rodas_ok={m['rodas_eval_ok']} (dark={m['rodas_left_metrics'].get('dark_lt80_pct')}%, "
            f"lum={m['rodas_left_metrics'].get('lum_mean')})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
