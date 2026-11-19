#!/usr/bin/env python3
"""FASE 0 da esteira Tripo-local (2026-11-19, r2 pós-1º gate) — prep A/B do Fox.

Correções do gate reprovado (2026-11-19):
  G1: linha A (painéis da grade) SEM tint — vidros já vêm fumê do Nano Banana;
  G2: linha B tint CONSERVADOR: máscara da pintura (distância de cor à dominante
      + dilatação morfológica) é zona PROIBIDA; tinta só em componentes
      conectados à banda dos vidros (acima da linha de cintura); cap ≤15%;
  G3: placa (RLA9E43) inpintada nos reais com a cor vizinha da lataria;
  G4: b5_extra marcado DESCARTADO para o mv (interior, não é vista);
  G5: report com % tint por painel e placa tratada.

Validação da grade + corte + prep padrão: rembg u2net → fundo branco → margem
8% → canvas 518×518. 100% CPU. Cards GLB para o viewer (case carro_foxh).

Uso: ~/.venvs/printer3d-ia/bin/python tools/generator/prep_foxh.py <report.json>
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation, label as cclabel

CAR_DIR = os.path.expanduser("~/printer3d-work")
FOXH = "/mnt/c/Users/Bruno/Downloads/fox-h"
PANELS = os.path.join(FOXH, "panels")
PANELS_PREP = os.path.join(PANELS, "prep")
FOX_REAL = "/mnt/c/Users/Bruno/Downloads/fox/no-windows"
PREP_REAL = "/mnt/c/Users/Bruno/Downloads/fox/prep_real"
MODELS_DIR = os.path.join(CAR_DIR, "modelos3d-site/models")

CANVAS = 518
MARGIN = 0.08
GRAPHITE = (62, 64, 68)
TINT_CAP_PCT = 15.0

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
        "ok": ok, "img_dims": [W, H], "cantos_brilho_medio": corners,
        "variacao_cantos_pct": round(100 * var, 2), "limite_variacao_pct": 5.0,
        "quadrantes": quads,
    }


def dominant_paint(rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    car = rgb[alpha > 128].astype(int)
    bright = car[car.mean(axis=1) > 150]
    if len(bright) > 50:
        return np.median(bright, axis=0)
    return np.array([255.0, 255.0, 255.0])


def cabin_bands(alpha: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """banda NÚCLEO dos vidros (cintura→teto) e banda AMPLA (p/ componentes)."""
    ys, xs = np.nonzero(alpha > 128)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    h = y1 - y0
    core = np.zeros_like(alpha, dtype=bool)
    wide = np.zeros_like(alpha, dtype=bool)
    core[int(y0 + 0.18 * h) : int(y0 + 0.62 * h), int(x0 + 0.12 * (x1 - x0)) : int(x0 + 0.88 * (x1 - x0))] = True
    wide[int(y0 + 0.10 * h) : int(y0 + 0.70 * h), int(x0 + 0.08 * (x1 - x0)) : int(x0 + 0.92 * (x1 - x0))] = True
    return core, wide


def tint_conservador(rgb: np.ndarray, alpha: np.ndarray) -> tuple[np.ndarray, dict]:
    """G2: pintura (cor dominante ±30, dilatada 15×15) é zona PROIBIDA; candidatos
    = banda ampla ∩ claro ∩ pouco saturado ∩ ∉ proibida; só entram componentes
    conectados que tocam a banda núcleo dos vidros; cap de 15% da silhueta."""
    sil = alpha > 128
    n_sil = int(sil.sum())
    dom = dominant_paint(rgb, alpha)
    dist = np.abs(rgb.astype(int) - dom).sum(axis=-1)
    paint = sil & (dist <= 30)
    forbid = binary_dilation(paint, structure=np.ones((15, 15))) | paint
    core, wide = cabin_bands(alpha)
    lum = rgb.astype(int).mean(axis=-1)
    sat = np.max(rgb, axis=-1).astype(int) - np.min(rgb, axis=-1).astype(int)
    cand = wide & sil & ~forbid & (lum > 140) & (sat < 50)
    meta = {"cor_dominante_pintura": [int(v) for v in dom],
            "pintura_px_proibidos": int((paint & sil).sum()), "cap_pct": TINT_CAP_PCT}
    if cand.sum() == 0:
        meta.update({"tint_aplicado": False, "janela_px": 0, "pct_da_silhueta": 0.0,
                     "motivo": "nenhum candidato fora da máscara de pintura"})
        return rgb, meta
    lbl, n = cclabel(cand)
    keep_mask = np.zeros_like(cand)
    comps = []
    for i in range(1, n + 1):
        cm = lbl == i
        if (cm & core).sum() > 0.15 * cm.sum():  # componente conectado à região dos vidros
            comps.append((int(cm.sum()), cm))
    if not comps:
        meta.update({"tint_aplicado": False, "janela_px": 0, "pct_da_silhueta": 0.0,
                     "motivo": "nenhum componente conectado à banda dos vidros"})
        return rgb, meta
    comps.sort(key=lambda t: -t[0])
    total = 0
    cap_px = int(TINT_CAP_PCT / 100.0 * n_sil)
    capped = False
    for size, cm in comps:
        if total + size > cap_px:
            capped = True
            continue
        keep_mask |= cm
        total += size
    n_tint = int(keep_mask.sum())
    meta.update({"janela_px": n_tint, "pct_da_silhueta": round(100 * n_tint / n_sil, 2),
                 "n_componentes": len(comps), "cap_aplicado": capped})
    if n_tint < 0.004 * n_sil:
        meta.update({"tint_aplicado": False, "motivo": "abaixo do piso de 0,4%"})
        return rgb, meta
    out = rgb.copy()
    out[keep_mask] = GRAPHITE
    meta["tint_aplicado"] = True
    meta["cor_tint"] = list(GRAPHITE)
    return out, meta


def inpaint_placa(rgb: np.ndarray, alpha: np.ndarray) -> tuple[np.ndarray, dict]:
    """G3: placa = componente claro/ pouco saturado na banda inferior do carro,
    retangular (w/h 2..7), baixo (≤8% da altura) e COM texto (std de brilho alta
    dentro do bbox). Preenche com a mediana do anel vizinho DENTRO da silhueta."""
    sil = alpha > 128
    ys, xs = np.nonzero(sil)
    y0, y1 = ys.min(), ys.max()
    Hc = y1 - y0
    band = np.zeros_like(sil)
    band[int(y0 + 0.55 * Hc) : int(y0 + 0.95 * Hc), :] = True
    lum = rgb.astype(int).mean(axis=-1)
    sat = np.max(rgb, axis=-1).astype(int) - np.min(rgb, axis=-1).astype(int)
    cand = band & sil & (lum > 165) & (sat < 50)
    lbl, n = cclabel(cand)
    out = rgb.copy()
    plates = []
    for i in range(1, n + 1):
        cm = lbl == i
        cys, cxs = np.nonzero(cm)
        ph, pw = cys.max() - cys.min() + 1, cxs.max() - cxs.min() + 1
        if not (2.0 <= pw / max(ph, 1) <= 7.0) or ph > 0.08 * Hc or cm.sum() < 40:
            continue
        by0, by1, bx0, bx1 = cys.min(), cys.max(), cxs.min(), cxs.max()
        inside = lum[by0 : by1 + 1, bx0 : bx1 + 1]
        if inside.std() < 25:  # sem texto escuro → não é placa
            continue
        ring = np.zeros_like(sil)
        ry0, ry1 = max(0, by0 - int(0.5 * ph)), by1 + int(0.5 * ph) + 1
        rx0, rx1 = max(0, bx0 - int(0.5 * pw)), bx1 + int(0.5 * pw) + 1
        ring[ry0:ry1, rx0:rx1] = True
        ring_vals = rgb[ring & sil & ~cm]
        if len(ring_vals) < 20:
            continue
        fill = np.median(ring_vals.astype(int), axis=0).astype(np.uint8)
        out[cm] = fill
        plates.append({"px": int(cm.sum()), "bbox": [int(bx0), int(by0), int(bx1), int(by1)],
                       "cor_preenchimento": [int(v) for v in fill]})
    return out, {"placas_inpaint": plates, "n_placas": len(plates)}


def prep_one(src: str, dst: str, tag: str, src_label: str) -> dict:
    from rembg import remove, new_session

    session = new_session("u2net")
    im = Image.open(src).convert("RGBA")
    cut = remove(im, session=session)
    a = np.asarray(cut)
    alpha = a[..., 3]
    ys, xs = np.nonzero(alpha > 16)
    entry = {"tag": tag, "src": src, "size_original": list(im.size), "fonte": src_label}
    if len(ys) == 0:
        raise RuntimeError(f"rembg vazia em {src}")
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    crop = a[y0 : y1 + 1, x0 : x1 + 1]
    side = int(max(crop.shape[0], crop.shape[1]) / (1.0 - 2 * MARGIN))
    canvas = Image.new("RGBA", (side, side), (255, 255, 255, 0))
    canvas.paste(Image.fromarray(crop), ((side - crop.shape[1]) // 2, (side - crop.shape[0]) // 2))
    canvas = canvas.resize((CANVAS, CANVAS), Image.LANCZOS)
    arr = np.asarray(canvas)
    rgb, al = arr[..., :3].copy(), arr[..., 3]

    if src_label == "grade":
        tint_meta = {"tint_aplicado": False, "motivo": "G1: linha A sem tint (vidros fumê do Nano Banana)"}
        placa_meta = {"n_placas": 0, "placas_inpaint": [], "motivo": "grade pede 'sem placa' no template"}
    else:
        rgb, placa_meta = inpaint_placa(rgb, al)
        rgb, tint_meta = tint_conservador(rgb, al)

    final = np.dstack([rgb, al])
    out_img = Image.fromarray(final, mode="RGBA")
    base = Image.new("RGB", out_img.size, (255, 255, 255))
    base.paste(out_img, mask=out_img.split()[3])
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    base.save(dst, "PNG")
    entry.update({"out": dst, "size_final": [CANVAS, CANVAS], "tint": tint_meta,
                  "placa": placa_meta, "hash_original": sha256_file(src)})
    sidecar = {
        "id": f"foxh-{tag}",
        "source": {"url": src, "author": "dono (grade Nano Banana Pro)" if src_label == "grade" else "dono (fotos reais)", "license": "uso pessoal", "triage": "amarelo", "retrieved_at": datetime.date.today().isoformat()},
        "hash_original": entry["hash_original"],
        "transform_log": [{"op": "esteira_tripo.fase0_r2", "tool": "prep_foxh.py (rembg u2net, PIL, scipy)", "params": {"canvas": CANVAS, "margem": MARGIN, "tint": tint_meta, "placa": placa_meta}, "ts": datetime.datetime.now().isoformat(timespec="seconds")}],
    }
    with open(os.path.splitext(dst)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump(sidecar, f, ensure_ascii=False, indent=1)
    return entry


def glb_card(png_path: str, glb_path: str):
    """Card GLB: quad 4 vértices + TEXCOORD_0 (convenção glTF: (0,0) = canto
    SUPERIOR esquerdo → V invertido em relação ao y-up do mundo) + textura
    embutida com baseColorFactor [1,1,1,1] (não escurecer a foto).
    Autodiagnóstico: o binário exportado TEM que conter 'TEXCOORD_0'."""
    import trimesh

    img = Image.open(png_path).convert("RGB")
    w, h = img.size
    quad_v = np.array([[-0.5, -0.5, 0], [0.5, -0.5, 0], [0.5, 0.5, 0], [-0.5, 0.5, 0]], dtype=np.float64)
    quad_v[:, 1] *= h / w
    faces = np.array([[0, 2, 1], [0, 3, 2]], dtype=np.int64)  # DoubleSide no viewer cuida do verso
    # v0=(-.5,-.5) fundo-esq no mundo → canto INFERIOR esq da imagem → uv (0,1)
    uv = np.array([[0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]], dtype=np.float64)
    m = trimesh.Trimesh(vertices=quad_v, faces=faces, process=False)
    # textura precisa estar DENTRO do material (baseColorTexture) — image= solto no
    # TextureVisuals não é exportado (medido: images:0 no JSON do GLB). Sem
    # baseColorFactor (trimesh normaliza int 1 → 1/255 ≈ preto — medido).
    mat = trimesh.visual.material.PBRMaterial(
        baseColorTexture=img, metallicFactor=0.0, roughnessFactor=1.0, doubleSided=True
    )
    m.visual = trimesh.visual.TextureVisuals(uv=uv, material=mat)
    m.export(glb_path, file_type="glb")
    with open(glb_path, "rb") as f:
        blob = f.read()
    if b"TEXCOORD_0" not in blob or b'"images"' not in blob:
        raise RuntimeError(f"GLB sem TEXCOORD_0 ou sem images embutida: {glb_path}")
    back = trimesh.load(glb_path, force="mesh", process=False)
    back_img = getattr(getattr(back.visual, "material", None), "baseColorTexture", None)
    if back_img is None:
        raise RuntimeError(f"Textura não sobreviveu ao roundtrip: {glb_path}")


def main() -> int:
    report_path = sys.argv[1] if len(sys.argv) > 1 else "report.json"
    rep = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), "fase": 0, "rev": "r2-gate1"}

    grade = find_grade()
    rep["grade"] = {"arquivo": grade, "hash": sha256_file(grade)}
    img = Image.open(grade)
    val = validate_grade(img)
    rep["validacao_grade"] = val
    if not val["ok"]:
        print("GRADE_REPROVADA=" + json.dumps(val, ensure_ascii=False))
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=1)
        return 2

    a = np.asarray(img.convert("RGB"))
    H, W = a.shape[:2]
    os.makedirs(PANELS, exist_ok=True)
    os.makedirs(PANELS_PREP, exist_ok=True)
    prep_entries = []
    for y0, x0, tag in [
        (0, 0, "P1_front"), (0, W // 2, "P2_side"),
        (H // 2, 0, "P3_back"), (H // 2, W // 2, "P4_diag"),
    ]:
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
        cards[mode] = {"glb": "models/" + os.path.basename(glb), "img": e["out"],
                       "tint_pct": e["tint"].get("pct_da_silhueta", 0.0),
                       "placas_inpaintadas": e["placa"].get("n_placas", 0)}
    rep["cards"] = cards
    rep["mv_runs"] = {
        "A_grade": ["a1_front", "a2_side", "a3_back", "a4_diag"],
        "B_reais": ["b1_front", "b2_side", "b3_back", "b4_diag"],
        "descartados": {"b5_extra": "interior — não é vista (G4)"},
    }

    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print("FASE0_R2_OK cards=" + str(len(cards)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
