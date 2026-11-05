#!/usr/bin/env python3
"""Seleção objetiva dos 2 melhores candidatos (sem olho humano):
fundo uniforme, objeto único centralizado, cobertura adequada. Sidecars de procedência.
"""
import datetime
import json
import os

import numpy as np
from PIL import Image

SD = os.path.expanduser("~/printer3d-work/jubarte/sd")


def metricas(caminho: str) -> dict:
    im = np.asarray(Image.open(caminho).convert("RGB"), dtype=np.float32)
    h, w, _ = im.shape
    # fundo: moldura de 8% das bordas
    m = max(8, int(min(h, w) * 0.08))
    borda = np.concatenate([im[:m].reshape(-1, 3), im[-m:].reshape(-1, 3),
                            im[:, :m].reshape(-1, 3), im[:, -m:].reshape(-1, 3)])
    bg_media = borda.mean(axis=0)
    bg_std = float(borda.std())
    # objeto: diferença do fundo (sem rembg — determinístico e leve)
    dist = np.abs(im - bg_media).sum(axis=2)
    mask = dist > (dist.max() * 0.25)
    if mask.sum() == 0:
        return {"bg_std": bg_std, "cobertura": 0.0, "descentramento": 1.0, "componentes": 99}
    ys, xs = np.where(mask)
    # componentes conexos via flood fill simples em binário downsampled
    small = mask[::4, ::4]
    comp = _componentes(small)
    from scipy import ndimage  # type: ignore

    lbl, n = ndimage.label(small)
    tamanhos = np.bincount(lbl.ravel())[1:]
    n_grandes = int((tamanhos >= tamanhos.max() * 0.05).sum())
    cy, cx = ys.mean() / h, xs.mean() / w
    desc = float(np.hypot(cy - 0.5, cx - 0.5))
    return {
        "bg_std": round(bg_std, 1),
        "cobertura": round(float(mask.mean()), 3),
        "descentramento": round(desc, 3),
        "componentes": n_grandes,
    }


def _componentes(_):
    return None


def nota(m):
    n = 0.0
    n += max(0.0, 30 - m["bg_std"]) / 30 * 40          # fundo limpo
    n += max(0.0, 0.25 - m["descentramento"]) / 0.25 * 30  # centralizado
    cob = m["cobertura"]
    n += (1 - abs(cob - 0.38) / 0.38) * 20 if 0.10 <= cob <= 0.75 else 0  # cobertura típica
    if m["componentes"] > 3:
        n *= 0.6  # objetos soltos demais
    return round(n, 1)


def main():
    cands = []
    for f in sorted(os.listdir(SD)):
        if not f.startswith("cand_") or not f.endswith(".png"):
            continue
        m = metricas(os.path.join(SD, f))
        m["nota"] = nota(m)
        m["arquivo"] = f
        cands.append(m)
        print(f"{f}: nota={m['nota']} bg_std={m['bg_std']} cob={m['cobertura']} "
              f"desc={m['descentramento']} comps={m['componentes']}")
    cands.sort(key=lambda c: -c["nota"])
    escolhidos = cands[:2]
    sel = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
           "criterio": "bg_std (fundo uniforme) + descentramento + cobertura ~0.38 + poucos componentes",
           "ranking": cands, "escolhidos": [c["arquivo"] for c in escolhidos]}
    with open(os.path.join(SD, "selecao.json"), "w") as f:
        json.dump(sel, f, indent=1, ensure_ascii=False)
    # sidecar de procedência (ADR-003) para todos os candidatos
    for c in cands:
        seed = c["arquivo"].replace("cand_", "").replace(".png", "")
        proc = {
            "id": f"jubarte_sd_{seed}",
            "arquivo": c["arquivo"],
            "origem": {
                "url": "gerado-localmente (Stable Diffusion v1.4, diffusers fp16)",
                "modelo": "CompVis/stable-diffusion-v1-4",
                "licenca": "CreativeML OpenRAIL-M 1.0",
                "triage": "verde",
                "prompt": "stylized sculpture of a humpback whale diving through a circular wave ring...",
                "seed": int(seed),
                "gerado_em": sel["ts"],
                "nota": "SD2.1 gated no HF — fallback v1-4 público",
            },
        }
        with open(os.path.join(SD, f"procedencia_cand_{seed}.json"), "w") as f:
            json.dump(proc, f, indent=1, ensure_ascii=False)
    print("ESCOLHIDOS:", [c["arquivo"] for c in escolhidos])


if __name__ == "__main__":
    main()
