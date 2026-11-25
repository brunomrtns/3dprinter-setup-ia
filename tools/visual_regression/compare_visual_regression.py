import argparse
import json
import os
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFont


def load_font(size: int):
    for candidate in (
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ):
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def compare_directories(baseline_dir: Path, run_dir: Path, pixel_threshold: int = 12, pct_threshold: float = 0.15):
    baseline_imgs = sorted(baseline_dir.glob("*.png"))
    if not baseline_imgs:
        raise FileNotFoundError(f"No baseline PNGs found in {baseline_dir}")

    report_shots = []
    all_region_diffs = []
    grid_cols, grid_rows = 8, 6

    for base_path in baseline_imgs:
        name = base_path.name
        curr_path = run_dir / name
        if not curr_path.exists():
            report_shots.append({"shot": name, "status": "MISSING", "changed_pct": 100.0})
            continue

        img_a = Image.open(base_path).convert("RGB")
        img_b = Image.open(curr_path).convert("RGB")
        if img_a.size != img_b.size:
            img_b = img_b.resize(img_a.size)

        w, h = img_a.size
        diff_rgb = ImageChops.difference(img_a, img_b)
        r_band, g_band, b_band = diff_rgb.split()
        max_band = ImageChops.lighter(ImageChops.lighter(r_band, g_band), b_band)
        mask = max_band.point(lambda p: 255 if p > pixel_threshold else 0)

        hist = mask.histogram()
        changed_px = int(hist[255])
        total_px = w * h
        changed_pct = (changed_px / total_px) * 100.0
        status = "DIFF_DETECTED" if changed_pct > pct_threshold else "PASS"

        # Heatmap overlay (red tint on changed pixels)
        red_img = Image.new("RGB", (w, h), (255, 48, 88))
        heatmap = Image.composite(red_img, img_b, mask)
        draw_h = ImageDraw.Draw(heatmap)

        tw, th = w // grid_cols, h // grid_rows
        changed_regions = []
        for r in range(grid_rows):
            for c in range(grid_cols):
                x0, y0 = c * tw, r * th
                x1, y1 = (w if c == grid_cols - 1 else (c + 1) * tw), (h if r == grid_rows - 1 else (r + 1) * th)
                tile_mask = mask.crop((x0, y0, x1, y1))
                tile_changed = tile_mask.histogram()[255]
                tile_total = (x1 - x0) * (y1 - y0)
                tile_pct = (tile_changed / tile_total) * 100.0

                if tile_pct > pct_threshold:
                    changed_regions.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "changed_pct": round(tile_pct, 2)})
                    draw_h.rectangle([x0, y0, x1 - 1, y1 - 1], outline=(255, 220, 48), width=3)

                all_region_diffs.append((
                    tile_pct,
                    name,
                    (x0, y0, x1, y1),
                    img_a.crop((x0, y0, x1, y1)),
                    img_b.crop((x0, y0, x1, y1)),
                    heatmap.crop((x0, y0, x1, y1)),
                ))

        if status == "DIFF_DETECTED":
            heatmap.save(run_dir / f"diff_heatmap_{name}")

        report_shots.append({
            "shot": name,
            "status": status,
            "changed_pixels": changed_px,
            "changed_pct": round(changed_pct, 4),
            "changed_regions_count": len(changed_regions),
            "changed_regions": changed_regions[:10],
        })

    # GATE 3: Top 10 largest differences side-by-side (ANTES | DEPOIS | DIFF)
    all_region_diffs.sort(key=lambda x: x[0], reverse=True)
    top10 = all_region_diffs[:10]

    row_h = 190
    cw, ch = 260, 150
    sheet_w = 1320
    sheet_h = 84 + len(top10) * row_h
    sheet = Image.new("RGB", (sheet_w, sheet_h), (12, 16, 24))
    ds = ImageDraw.Draw(sheet)
    f_hdr = load_font(26)
    f_lbl = load_font(18)

    ds.rectangle([0, 0, sheet_w, 68], fill=(18, 26, 38))
    ds.text((24, 20), "REGRESSAO VISUAL — TOP 10 MAIORES DIFERENCAS (ANTES | DEPOIS | DIFF)", font=f_hdr, fill=(246, 250, 255))

    for idx, (tpct, sname, box, crop_a, crop_b, crop_d) in enumerate(top10):
        y = 80 + idx * row_h
        color = (255, 92, 92) if tpct > pct_threshold else (86, 240, 162)
        ds.text((20, y + 4), f"#{idx+1:02d}  {sname}  regiao={box}  mudanca={tpct:.2f}%", font=f_lbl, fill=color)
        sheet.paste(crop_a.resize((cw, ch)), (20, y + 32))
        sheet.paste(crop_b.resize((cw, ch)), (310, y + 32))
        sheet.paste(crop_d.resize((cw, ch)), (600, y + 32))
        ds.text((890, y + 60), "ESQ: BASELINE (ANTES)", font=f_lbl, fill=(180, 210, 240))
        ds.text((890, y + 90), "MEIO: BUILD ATUAL (DEPOIS)", font=f_lbl, fill=(255, 224, 140))
        ds.text((890, y + 120), "DIR: HEATMAP DIFF", font=f_lbl, fill=(255, 110, 130))

    top10_path = run_dir / "top10_diferencas_lado_a_lado.png"
    sheet.save(top10_path)

    summary = {
        "baseline_dir": str(baseline_dir),
        "run_dir": str(run_dir),
        "pixel_threshold": pixel_threshold,
        "pct_threshold": pct_threshold,
        "shots": report_shots,
        "top10_image": str(top10_path),
    }
    (run_dir / "relatorio_regressao.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md_lines = [
        "# Relatório de Regressão Visual",
        "",
        f"- **Baseline:** `{baseline_dir}`",
        f"- **Execução:** `{run_dir}`",
        f"- **Limiar por pixel:** `ΔRGB > {pixel_threshold}` | **Limiar de alerta:** `> {pct_threshold}%`",
        f"- **Top 10 diferenças lado a lado:** `top10_diferencas_lado_a_lado.png`",
        "",
        "| Screenshot | Status | Pixels alterados | % Alterado | Regiões alteradas |",
        "|---|---|---:|---:|---:|",
    ]
    for s in report_shots:
        md_lines.append(f"| `{s['shot']}` | **{s['status']}** | `{s.get('changed_pixels', 0)}` | `{s['changed_pct']:.4f}%` | `{s.get('changed_regions_count', 0)}` |")
    (run_dir / "relatorio_regressao.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print("COMPARE_OK:")
    for s in report_shots:
        print(f"  {s['shot']}: {s['status']} ({s['changed_pct']:.4f}%, {s.get('changed_regions_count', 0)} regions)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", required=True)
    p.add_argument("--run", required=True)
    p.add_argument("--pixel-threshold", type=int, default=12)
    p.add_argument("--pct-threshold", type=float, default=0.15)
    args = p.parse_args()
    compare_directories(Path(args.baseline), Path(args.run), args.pixel_threshold, args.pct_threshold)


if __name__ == "__main__":
    main()
