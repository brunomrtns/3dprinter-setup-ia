#!/usr/bin/env python3
"""FASE 0 da esteira Tripo-local (2026-11-19) — prep A/B do Fox no RTX 3060.

Linha A: painéis canônicos da grade 2x2 do dono (Nano Banana Pro, Downloads/fox-h).
Linha B: as 5 fotos reais (Downloads/fox/no-windows).

Passos (100% CPU, sem GPU — regra da esteira):
  1. valida a grade por métrica (4 quadrantes; % não-branco 15-60% por quadrante;
     brilho dos 4 cantos com variação < 5%); falha → PARA e reporta quadrante;
  2. corta no ponto médio → panels/P1_front..P4_diag (resolução nativa do quadrante);
  3. prep padrão: rembg u2net → fundo branco → bbox do objeto c/ margem 8% →
     canvas 518x518; conferência de vidros claros → tint grafite quando detectado;
  4. mesmo prep nas 5 fotos reais → prep_real/R1_front..R5_extra;
  5. 9 "cards" GLB (plano texturizado) no viewer, case carro_foxh (A=painéis, B=reais);
  6. report em evidence/rtx3060-12gb/carro-foxh/report.json.

Uso: ~/.venvs/printer3d-ia/bin/python tools/generator/prep_foxh.py
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys

import numpy as np
from PIL import Image

CAR_DIR = os.path.expanduser("~/printer3d-work")
FOXH = "/mnt/c/Users/Bruno/Downloads/fox-h"
PANELS = os.path.join(FOXH, "panels")
PANELS_PREP = os.path.join(PANELS, "prep")
FOX_REAL = "/mnt/c/Users/Bruno/Downloads/fox/no-windows"
PREP_REAL = "/mnt/c/Users/Bruno/Downloads/fox/prep_real"
MODELS_DIR = os.path.join(CAR_DIR, "modelos3d-site/models")
REPORT = None  # set via argv[1]

CANVAS = 518
MARGIN = 0.08
GRAPHITE = (62, 64, 68)

REAL_MAP = {
    "R1_front": "frente.jpg",
    "R2_side": "lado.jpg",
    "R3_back": "traseira.jpg",
    "R4_diag": "frente-e-lado-diagonal.jpg",
    "R5_extra": "de-fora-pegando-interna.jpg",
}
PANEL_TAGS = ["P1_front", "P2_side", "P3_back", "P4_diag"]


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def find_grade() -> str:
    cands = []
    for f in sorted(os.listdir(FOXH)):
        low = f.lower()
        if os.path.isfile(os.path.join(FOXH, f)) and low.endswith((".png", ".jpg", ".jpeg", ".webp")):
            cands.append(f)
    pref = [f for f in cands if "contact" in f.lower()]
    grade = pref[0] if pref else cands[-1]
    return os.path.join(FOXH, grade)


def validate_grade(img: Image.Image) -> dict:
    a = np.asarray(img.convert("RGB")).astype(np.int16)
    H, W = a.shape[:2]
    corners = []
    k = 32
    for y0, x0 in ((0, 0), (0, W - k), (H - k, 0), (H - k, W - k)):
        patch = a[y0 : y0 + k, x0 : x0 + k]
        corners.append(round(float(patch.mean()), 2))
    var = (max(corners) - min(corners)) / max(min(corners), 1.0)
    quads = {}
    ok = True
    for qi, (y0, x0) in enumerate(((0, 0), (0, W // 2), (H // 2, 0), (H // 2, W // 2))):
        q = a[y0 : y0 + H // 2, x0 : x0 + W // 2]
        nonwhite = float((q.min(axis=-1) < 245).mean())
        tag = PANEL_TAGS[qi]
        quads[tag] = {"pct_nao_branco": round(100 * nonwhite, 1), "dims": [int(q.shape[1]), int(q.shape[0])]}
        if not (0.15 <= nonwhite <= 0.60):
            ok = False
            quads[tag]["falha"] = "fora da faixa 15-60% de pixels não-brancos"
    if var >= 0.05:
        ok = False
    return {
        "ok": ok,
        "img_dims": [W, H],
        "cantos_brilho_medio": corners,
        "variacao_cantos_pct": round(100 * var, 2),
        "limite_variacao_pct": 5.0,
        "quadrantes": quads,
    }


def window_tint(rgb: np.ndarray, alpha: np.ndarray) -> tuple[np.ndarray, dict]:
    """Detecta vidros na banda da cabine e aplica grafite. Carro BRANCO exige
    excluir a cor da pintura: vidro = pixel da banda que se DESVIA >45 da cor
    dominante clara do carro (mediana dos pixels claros da silhueta), claro o
    suficiente e pouco saturado (grade/para-choque escuros ficam de fora)."""
    ys, xs = np.nonzero(alpha > 128)
    if len(ys) == 0:
        return rgb, {"janela_px": 0, "tint_aplicado": False, "motivo": "silhueta vazia"}
    car = rgb[alpha > 128].astype(int)
    bright = car[car.mean(axis=1) > 150]
    dom = np.median(bright, axis=0) if len(bright) > 50 else np.array([255, 255, 255])
    y0, y1 = ys.min(), ys.max()
    x0, x1 = xs.min(), xs.max()
    h = y1 - y0
    band = np.zeros_like(alpha, dtype=bool)
    band[int(y0 + 0.18 * h) : int(y0 + 0.62 * h), int(x0 + 0.12 * (x1 - x0)) : int(x0 + 0.88 * (x1 - x0))] = True
    r, g, b = rgb[..., 0].astype(int), rgb[..., 1].astype(int), rgb[..., 2].astype(int)
    lum = (r + g + b) / 3.0
    sat = np.max(rgb, axis=-1).astype(int) - np.min(rgb, axis=-1).astype(int)
    dist_dom = np.abs(rgb.astype(int) - dom).sum(axis=-1)
    glassy = band & (alpha > 128) & (dist_dom > 45) & (lum > 140) & (sat < 50)
    n = int(glassy.sum())
    meta = {"janela_px": n, "pct_da_silhueta": round(100 * n / max(len(ys), 1), 2),
            "cor_dominante_carro": [int(v) for v in dom]}
    if n < 0.004 * len(ys):  # < 0,4% da silhueta → não é vidro de verdade
        meta["tint_aplicado"] = False
        meta["motivo"] = "poucos pixels desviantes na banda da cabine"
        return rgb, meta
    out = rgb.copy()
    out[glassy] = GRAPHITE
    meta["tint_aplicado"] = True
    meta["cor_tint"] = list(GRAPHITE)
    return out, meta


def prep_one(src: str, dst: str, tag: str, src_label: str) -> dict:
    from rembg import remove, new_session

    session = new_session("u2net")
    im = Image.open(src).convert("RGBA")
    cut = remove(im, session=session)
    a = np.asarray(cut)
    alpha = a[..., 3]
    ys, xs = np.nonzero(alpha > 16)
    entry = {"tag": tag, "src": src, "size_original": list(im.size)}
    if len(ys) == 0:
        raise RuntimeError(f"rembg vazia em {src}")
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    crop = a[y0 : y1 + 1, x0 : x1 + 1]
    # margem 8% de cada lado: objeto ocupa 84% do canvas na maior dimensão
    side = int(max(crop.shape[0], crop.shape[1]) / (1.0 - 2 * MARGIN))
    canvas = Image.new("RGBA", (side, side), (255, 255, 255, 0))
    oy, ox = (side - crop.shape[0]) // 2, (side - crop.shape[1]) // 2
    canvas.paste(Image.fromarray(crop), (ox, oy))
    canvas = canvas.resize((CANVAS, CANVAS), Image.LANCZOS)
    arr = np.asarray(canvas)
    rgb, al = arr[..., :3].copy(), arr[..., 3]
    rgb, tint_meta = window_tint(rgb, al)
    final = np.dstack([rgb, al])
    out = Image.fromarray(final, mode="RGBA")
    base = Image.new("RGB", out.size, (255, 255, 255))
    base.paste(out, mask=out.split()[3])
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    base.save(dst, "PNG")
    entry.update({
        "out": dst, "size_final": [CANVAS, CANVAS],
        "tint": tint_meta,
        "hash_original": sha256_file(src),
        "fonte": src_label,
    })
    sidecar = {
        "id": f"foxh-{tag}",
        "source": {"url": src, "author": "dono (grade Nano Banana Pro)" if src_label == "grade" else "dono (fotos reais)", "license": "uso pessoal", "triage": "amarelo", "retrieved_at": datetime.date.today().isoformat()},
        "hash_original": entry["hash_original"],
        "transform_log": [{"op": "esteira_tripo.fase0", "tool": "prep_foxh.py (rembg u2net, PIL)", "params": {"canvas": CANVAS, "margem": MARGIN, "tint": tint_meta}, "ts": datetime.datetime.now().isoformat(timespec="seconds")}],
    }
    with open(os.path.splitext(dst)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump(sidecar, f, ensure_ascii=False, indent=1)
    return entry


def glb_card(png_path: str, glb_path: str):
    import trimesh

    img = Image.open(png_path).convert("RGB")
    w, h = img.size
    quad_v = np.array([[-0.5, -0.5, 0], [0.5, -0.5, 0], [0.5, 0.5, 0], [-0.5, 0.5, 0]], dtype=np.float64)
    quad_v[:, 1] *= h / w
    faces = np.array([[0, 2, 1], [0, 3, 2], [0, 1, 2], [0, 2, 3]], dtype=np.int64)
    uv = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float64)
    m = trimesh.Trimesh(vertices=quad_v, faces=faces, process=False)
    m.visual = trimesh.visual.TextureVisuals(uv=np.vstack([uv, uv]), image=img)
    m.export(glb_path, file_type="glb")


def main() -> int:
    global REPORT
    REPORT = sys.argv[1] if len(sys.argv) > 1 else "report.json"
    rep = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), "fase": 0}

    grade = find_grade()
    rep["grade"] = {"arquivo": grade, "hash": sha256_file(grade)}
    img = Image.open(grade)
    val = validate_grade(img)
    rep["validacao_grade"] = val
    if not val["ok"]:
        print("GRADE_REPROVADA=" + json.dumps(val, ensure_ascii=False))
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=1)
        return 2

    a = np.asarray(img.convert("RGB"))
    H, W = a.shape[:2]
    os.makedirs(PANELS, exist_ok=True)
    os.makedirs(PANELS_PREP, exist_ok=True)
    quadrants = [
        (0, 0, "P1_front"), (0, W // 2, "P2_side"),
        (H // 2, 0, "P3_back"), (H // 2, W // 2, "P4_diag"),
    ]
    prep_entries = []
    for y0, x0, tag in quadrants:
        q = Image.fromarray(a[y0 : y0 + H // 2, x0 : x0 + W // 2])
        ppath = os.path.join(PANELS, f"{tag}.png")
        q.save(ppath)
        prep_entries.append(prep_one(ppath, os.path.join(PANELS_PREP, f"{tag}.png"), tag, "grade"))
    for tag, fname in REAL_MAP.items():
        prep_entries.append(prep_one(os.path.join(FOX_REAL, fname), os.path.join(PREP_REAL, f"{tag}.png"), tag, "real"))
    rep["prep"] = prep_entries

    cards = {}
    for e in prep_entries:
        mode = e["tag"].replace("P", "a").replace("R", "b").lower()
        glb = os.path.join(MODELS_DIR, f"carro_foxh__{mode}.glb")
        glb_card(e["out"], glb)
        cards[mode] = {"glb": "models/" + os.path.basename(glb), "img": e["out"], "tint": e["tint"]}
    rep["cards"] = cards

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print("FASE0_OK cards=" + str(len(cards)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
