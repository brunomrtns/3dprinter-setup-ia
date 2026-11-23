#!/usr/bin/env python3
"""
tools/generator/gate_concept_image.py — Gate Anti-Grade / Sujeito Unico (CPU-only, 0 VRAM).

Principio permanente (RUN mega_v5, 2026-11-23):
  "SUJEITO UNICO, VISTA UNICA" — folha multi-view/grade NUNCA entra no pipeline 3D.

Criterios objetivos:
  1. Segmentacao de primeiro plano em CPU (rembg/BiRefNet-CPU ou fallback de diferenca de fundo de borda).
  2. Componentes conexos: peca grande = area >= 5% da imagem; >= 2 pecas grandes -> REPROVADO (multi-sujeito/grade).
  3. Calhas brancas/uniformes (gutters): linha OU coluna interna (15%..85%) sem primeiro plano separando
     blocos de primeiro plano de ambos os lados -> REPROVADO (grade).
  4. Corte na borda: primeiro plano tocando qualquer borda em > 8% da extensao da borda -> REPROVADO (corte).

Saida: JSON ao lado da imagem (<stem>.gate.json) com {gate_pass, n_componentes, calhas, corte, razao}.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
import numpy as np
from PIL import Image

# Forca CPU-only (zero VRAM)
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["ORT_DISABLE_CUDA"] = "1"


def _segment_foreground(im_rgb: Image.Image, use_birefnet: bool = True) -> tuple[np.ndarray, str]:
    """Retorna mascara booleana (H, W) de primeiro plano e nome do backend usado (CPU-only)."""
    arr = np.asarray(im_rgb, dtype=np.float32)
    h, w, _ = arr.shape

    # Estima cor do fundo pela mediana das 4 bordas (faixa de 4px)
    border = np.concatenate([
        arr[:4, :, :].reshape(-1, 3),
        arr[-4:, :, :].reshape(-1, 3),
        arr[:, :4, :].reshape(-1, 3),
        arr[:, -4:, :].reshape(-1, 3),
    ], axis=0)
    bg_color = np.median(border, axis=0)

    # Tenta BiRefNet / rembg em CPU se solicitado e disponivel
    if use_birefnet:
        try:
            from rembg import new_session, remove
            # Usa BiRefNet se peso ja existir localmente (Lei 8: nunca baixa nada!)
            u2_dir = Path.home() / ".u2net"
            rembg_dir = Path.home() / ".rembg"
            has_biref = any(
                (d / f).exists()
                for d in (u2_dir, rembg_dir)
                for f in ("birefnet-general.onnx", "BiRefNet-general-epoch_244.onnx")
            )
            if has_biref:
                sess = new_session("birefnet-general", providers=["CPUExecutionProvider"])
                rgba = remove(im_rgb, session=sess)
                alpha = np.asarray(rgba.split()[-1], dtype=np.uint8)
                return alpha > 128, "rembg-birefnet-cpu"
        except Exception:
            pass

    # Fallback deterministico CPU-only: distancia cromatica ao fundo + deteccao de divisoria clara/escura
    # Muito preciso para imagens de estudio (fundo branco/cinza claro) e contact sheets!
    dist = np.linalg.norm(arr - bg_color[None, None, :], axis=2)
    # Se o fundo das bordas for escuro (ex.: contact sheet com moldura preta!), trata pixels claros/escuros uniformes como fundo
    is_dark_frame = float(np.mean(bg_color)) < 60.0
    if is_dark_frame:
        # Contact sheet: tudo que difere da moldura escura e foreground (cada celula vira um componente grande!)
        mask = dist > 22.0
        return mask, "cpu-border-bg-darkframe"

    # Fundo claro padrao de estudio: pixels com distancia > 32 do fundo (ignora sombra suave de chao sob objetos flutuantes)
    mask = dist > 32.0
    return mask, "cpu-border-bg-light"


def _connected_components(mask: np.ndarray) -> list[tuple[int, tuple[int, int, int, int]]]:
    """Retorna lista de (area_px, (y0, x0, y1, x1)) para componentes 4-conexos (usa scipy se disponivel, senao numpy/BFS)."""
    try:
        from scipy.ndimage import label as nd_label, find_objects
        labeled, n = nd_label(mask)
        if n == 0:
            return []
        slices = find_objects(labeled)
        out = []
        for idx, sl in enumerate(slices, start=1):
            if sl is None:
                continue
            sub = labeled[sl] == idx
            area = int(sub.sum())
            out.append((area, (sl[0].start, sl[1].start, sl[0].stop, sl[1].stop)))
        out.sort(key=lambda x: x[0], reverse=True)
        return out
    except Exception:
        # BFS puro em downsample 256px para velocidade garantida sem scipy
        h, w = mask.shape
        visited = np.zeros_like(mask, dtype=bool)
        out = []
        ys, xs = np.where(mask)
        for y0, x0 in zip(ys.tolist(), xs.tolist()):
            if visited[y0, x0]:
                continue
            stack = [(y0, x0)]
            visited[y0, x0] = True
            area = 0
            miny = maxy = y0
            minx = maxx = x0
            while stack:
                cy, cx = stack.pop()
                area += 1
                if cy < miny: miny = cy
                if cy > maxy: maxy = cy
                if cx < minx: minx = cx
                if cx > maxx: maxx = cx
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        stack.append((ny, nx))
            out.append((area, (miny, minx, maxy + 1, maxx + 1)))
        out.sort(key=lambda x: x[0], reverse=True)
        return out


def evaluate_image(img_path: Path, write_sidecar: bool = True) -> dict:
    im = Image.open(img_path).convert("RGB")
    # Downsample para max 384px no maior lado (CPU instantaneo < 0.05s, sem perda de geometria global)
    orig_w, orig_h = im.size
    scale = min(1.0, 384.0 / max(orig_w, orig_h))
    if scale < 1.0:
        im_small = im.resize((max(1, int(orig_w * scale)), max(1, int(orig_h * scale))), Image.BILINEAR)
    else:
        im_small = im

    mask, backend = _segment_foreground(im_small, use_birefnet=True)
    h, w = mask.shape
    total_px = float(h * w)

    # 1. Componentes conexos: peca grande >= 5% da tela
    comps = _connected_components(mask)
    big_comps = [c for c in comps if (c[0] / total_px) >= 0.05]
    n_comp = len(big_comps)
    big_areas_pct = [round(100.0 * c[0] / total_px, 2) for c in big_comps]

    # 2. Calhas (linhas ou colunas internas 15%..85% completamente sem foreground separando foreground significativo de ambos os lados)
    row_fg = mask.sum(axis=1) / float(w)
    col_fg = mask.sum(axis=0) / float(h)

    y_lo, y_hi = int(h * 0.15), int(h * 0.85)
    x_lo, x_hi = int(w * 0.15), int(w * 0.85)

    calha_h = False
    for y in range(y_lo, y_hi):
        if row_fg[y] <= 0.005:
            above = mask[:y, :].sum() / total_px
            below = mask[y + 1:, :].sum() / total_px
            if above >= 0.04 and below >= 0.04:
                calha_h = True
                break

    calha_v = False
    for x in range(x_lo, x_hi):
        if col_fg[x] <= 0.005:
            left = mask[:, :x].sum() / total_px
            right = mask[:, x + 1:].sum() / total_px
            if left >= 0.04 and right >= 0.04:
                calha_v = True
                break

    calhas = calha_h or calha_v

    # 3. Corte na borda (> 8% de qualquer borda ocupada por foreground)
    top_ratio = float(mask[0, :].mean())
    bot_ratio = float(mask[-1, :].mean())
    left_ratio = float(mask[:, 0].mean())
    right_ratio = float(mask[:, -1].mean())
    max_border = max(top_ratio, bot_ratio, left_ratio, right_ratio)
    corte = max_border > 0.08

    reasons = []
    if n_comp == 0:
        reasons.append("sem_sujeito_detectado")
    elif n_comp >= 2:
        reasons.append(f"multi_sujeito_ou_grade({n_comp}_componentes>=5%)")
    if calhas:
        kind = []
        if calha_h: kind.append("H")
        if calha_v: kind.append("V")
        reasons.append(f"calha_branca_grade({'+'.join(kind)})")
    if corte:
        reasons.append(f"corte_borda(max={round(max_border*100,1)}%)")

    gate_pass = len(reasons) == 0
    result = {
        "gate_pass": gate_pass,
        "n_componentes": n_comp,
        "areas_componentes_pct": big_areas_pct,
        "calhas": calhas,
        "corte": corte,
        "max_border_touch_pct": round(max_border * 100.0, 2),
        "razao": "OK (sujeito unico, vista unica)" if gate_pass else "; ".join(reasons),
        "backend": backend,
        "image": str(img_path),
        "size": [orig_w, orig_h],
    }

    if write_sidecar:
        out_json = img_path.with_suffix(".gate.json")
        out_json.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Gate Anti-Grade / Sujeito Unico (CPU-only)")
    ap.add_argument("images", nargs="+", help="PNG(s) para avaliar")
    ap.add_argument("--no-sidecar", action="store_true")
    args = ap.parse_args()

    all_ok = True
    results = []
    for p in args.images:
        res = evaluate_image(Path(p), write_sidecar=not args.no_sidecar)
        results.append(res)
        tag = "PASS" if res["gate_pass"] else "FAIL"
        print(f"[gate_concept] {tag} | {Path(p).name} | comps={res['n_componentes']} calhas={res['calhas']} corte={res['corte']} | {res['razao']}")
        if not res["gate_pass"]:
            all_ok = False

    print("GATE_JSON:" + json.dumps(results[0] if len(results) == 1 else results, ensure_ascii=False))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
