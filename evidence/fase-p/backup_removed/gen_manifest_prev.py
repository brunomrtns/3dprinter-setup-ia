#!/usr/bin/env python3
"""Gera manifest.json do site modelos3d a partir de results.json + GLBs presentes."""
import json
import os
import sys

results_path, models_dir, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
res = json.load(open(results_path))

cases = {}
order = []
for r in res["resultados"]:
    cid, mode = r["caso"], r["mode"]
    glb = os.path.join(models_dir, f"{cid}__{mode}.glb")
    if r.get("erros") or not os.path.isfile(glb):
        continue
    if cid not in cases:
        cases[cid] = {"id": cid, "category": r.get("categoria", ""), "modes": {}}
        order.append(cid)
    cases[cid]["modes"][mode] = {
        "glb": f"models/{cid}__{mode}.glb",
        "verts": r.get("vertices"),
        "faces": r.get("faces"),
        "tempo_s": r.get("tempo_s"),
        "vram": r.get("vram_pico_mib"),
        "manifold_antes": r.get("manifold_antes"),
        "manifold_depois": r.get("manifold_depois_reparo"),
    }

out = {"cases": [cases[c] for c in order]}
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(f"manifest: {len(out['cases'])} casos, {sum(len(c['modes']) for c in out['cases'])} modelos")
