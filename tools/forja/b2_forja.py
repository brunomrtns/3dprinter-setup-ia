#!/usr/bin/env python3
"""Jubarte B2 — Passo 2: Forja multi-componente (regra dos 2%).

Ordem: limpeza → componentes >2% das faces → PyMeshFix individual → normais →
união manifold3d se sobreposição clara (senão segue separado) → escala 200mm →
espessura com localização → STL + forja_report_<candidato>.json.
"""
import datetime
import json
import os
import sys

import numpy as np
import pymeshfix
import trimesh

sys.path.insert(0, os.path.expanduser("~/printer3d-work"))
from forja.pipeline import espessura_estimada, metricas  # noqa: E402

OUT = os.path.expanduser("~/printer3d-work/jubarte_b2")
FORJA_OUT = os.path.expanduser("~/printer3d-work/forja_out")
os.makedirs(FORJA_OUT, exist_ok=True)

LIMIAR_PCT_FACES = 0.02   # regra dos 2%
TARGET_ALTURA_MM = 200.0
LIMIAR_ESPESSURA_MM = 2.4

try:
    import manifold3d  # noqa: F401

    TEM_MANIFOLD = True
except ImportError:
    TEM_MANIFOLD = False


def log(m):
    print(f"[b2.forja] {m}", flush=True)


def bbox_overlap_vol(a: trimesh.Trimesh, b: trimesh.Trimesh) -> float:
    ba, bb = a.bounds, b.bounds
    lo = np.maximum(ba[0], bb[0])
    hi = np.minimum(ba[1], bb[1])
    e = np.maximum(hi - lo, 0)
    return float(np.prod(e))


def forjar(cand: str, mesh_path: str) -> dict:
    rel = {"candidato": cand, "entrada": mesh_path, "ts": datetime.datetime.now().isoformat(timespec="seconds"),
           "avisos": [], "etapas": [], "uniao_manifold": {"tentada": False, "ok": None},
           "parametros": {"regra_componentes": f"> {LIMIAR_PCT_FACES:.0%} das faces",
                          "target_height_mm": TARGET_ALTURA_MM, "limiar_espessura_mm": LIMIAR_ESPESSURA_MM}}

    # 1. load + limpeza
    m = trimesh.load(mesh_path, force="mesh", process=False)
    antes = metricas(m)
    m.update_faces(m.nondegenerate_faces(height=1e-8))
    m.merge_vertices()
    m.remove_unreferenced_vertices()
    log(f"{cand}: limpeza {antes['vertices']}v/{antes['triangulos']}t wt={antes['watertight']}")

    # 2. componentes > 2% das faces (NÃO apagar baleia/anel)
    comps = m.split(only_watertight=False)
    total_faces = sum(len(c.faces) for c in comps)
    mantidos, descartados = [], []
    for c in comps:
        (mantidos if len(c.faces) > LIMIAR_PCT_FACES * total_faces else descartados).append(c)
    rel["etapas"].append({"nome": "componentes", "antes": antes,
                          "depois": {"componentes_entrada": len(comps),
                                     "mantidos": len(mantidos), "descartados": len(descartados),
                                     "faces_mantidas": sum(len(c.faces) for c in mantidos)}})
    if descartados:
        rel["avisos"].append(f"{len(descartados)} componente(s) descartados pela regra dos 2% "
                             f"(menores que {LIMIAR_PCT_FACES:.0%} das faces)")
    log(f"{cand}: {len(comps)} componentes -> mantidos {len(mantidos)} "
        f"({sum(len(c.faces) for c in mantidos)} faces)")

    # sobreposição clara entre os 2 maiores mantidos?
    mantidos.sort(key=lambda c: -len(c.faces))
    uniao_ok = None
    if len(mantidos) >= 2 and TEM_MANIFOLD:
        a, b = mantidos[0], mantidos[1]
        vol_inter = bbox_overlap_vol(a, b)
        rel["uniao_manifold"]["tentada"] = vol_inter > 0.01 * min(a.volume, b.volume) if a.volume and b.volume else vol_inter > 0
        if rel["uniao_manifold"]["tentada"]:
            try:
                fused = trimesh.boolean.union([a, b], engine="manifold")
                mantidos = [fused] + mantidos[2:]
                uniao_ok = True
                rel["avisos"].append("união manifold3d aplicada entre os 2 maiores componentes (sobreposta)")
            except Exception as e:  # noqa: BLE001
                uniao_ok = False
                rel["avisos"].append(f"união manifold3d falhou ({type(e).__name__}) — componentes seguem separados (fatiável normal)")
        rel["uniao_manifold"]["ok"] = uniao_ok
    elif len(mantidos) >= 2 and not TEM_MANIFOLD:
        rel["uniao_manifold"] = {"tentada": False, "ok": None,
                                 "motivo": "manifold3d não instalado — componentes separados (fatiável normal)"}
    log(f"{cand}: união manifold tentada={rel['uniao_manifold']['tentada']} ok={uniao_ok}")

    # 3+4. PyMeshFix individual por componente + normais para fora
    reparados = []
    for i, c in enumerate(mantidos):
        mf = pymeshfix.MeshFix(np.asarray(c.vertices, dtype=np.float64), np.asarray(c.faces, dtype=np.int32))
        mf.repair()
        r = trimesh.Trimesh(vertices=np.asarray(mf.points), faces=np.asarray(mf.faces), process=False)
        r.fix_normals()
        r.remove_unreferenced_vertices()
        reparados.append(r)
        log(f"{cand}: comp#{i} reparado wt={r.is_watertight} {len(r.faces)}t")

    m = trimesh.util.concatenate(reparados) if len(reparados) > 1 else reparados[0]
    m.fix_normals()
    rel["etapas"].append({"nome": "pymeshfix_individual", "antes": antes, "depois": metricas(m)})
    rel["watertight_pos_reparo"] = bool(m.is_watertight)
    if not m.is_watertight:
        rel["avisos"].append("watertight=False mesmo após reparo individual")

    # 5. escala 200mm (altura total = maior dimensão, convenção documentada)
    ext_antes = [round(float(x), 4) for x in m.extents]
    s = TARGET_ALTURA_MM / float(max(m.extents))
    m.apply_scale(s)
    rel["etapas"].append({"nome": "escala", "fator": round(s, 6),
                          "bbox_antes": ext_antes, "bbox_depois_mm": [round(float(x), 2) for x in m.extents]})

    # 6. espessura com localização (por componente)
    finos = []
    esp_por_comp = []
    for i, c in enumerate(m.split(only_watertight=False)):
        esp = espessura_estimada(c)
        esp_por_comp.append({"componente": i, "faces": int(len(c.faces)),
                             "pct5_mm": esp.get("pct5"), "min_mm": esp.get("min")})
        if esp.get("min") is not None and esp["min"] < LIMIAR_ESPESSURA_MM:
            # localiza as amostras finas: reamostra e registra coords normalizadas
            import open3d as o3d

            pts, fidx = trimesh.sample.sample_surface(c, esp["amostras"], seed=7)
            nrm = c.face_normals[fidx]
            sc = o3d.t.geometry.RaycastingScene()
            sc.add_triangles(o3d.core.Tensor(np.asarray(c.vertices, dtype=np.float32)),
                             o3d.core.Tensor(np.asarray(c.faces, dtype=np.uint32)))
            t = sc.cast_rays(o3d.core.Tensor(np.hstack([pts, -nrm]).astype(np.float32)))["t_hit"].numpy()
            mask = np.isfinite(t) & (t > 1e-3) & (t < LIMIAR_ESPESSURA_MM)
            if mask.any():
                lo, hi = c.bounds
                norm_pts = (pts[mask] - lo) / np.maximum(hi - lo, 1e-9)
                centro = norm_pts.mean(axis=0)
                finos.append({"componente": i, "min_mm": esp["min"],
                              "n_amostras_finas": int(mask.sum()),
                              "localizacao_norm": [round(float(v), 2) for v in centro]})
    rel["espessura_por_componente"] = esp_por_comp
    rel["espessura_minima_mm"] = min((e["min_mm"] for e in esp_por_comp if e["min_mm"] is not None), default=None)
    if finos:
        for f in finos:
            rel["avisos"].append(
                f"ESPRESSURA < {LIMIAR_ESPESSURA_MM}mm no componente {f['componente']} "
                f"(mín {f['min_mm']}mm, {f['n_amostras_finas']} amostras finas, centro aprox. "
                f"x={f['localizacao_norm'][0]} y={f['localizacao_norm'][1]} z={f['localizacao_norm'][2]} "
                f"em coords normalizadas do componente) — risco nos caracóis/pontas")
    else:
        rel["avisos"].append(f"espessura mínima >= {LIMIAR_ESPESSURA_MM}mm em todos os componentes")

    # 8. export
    stl = os.path.join(FORJA_OUT, f"jubarte_{cand}.stl")
    m.export(stl, file_type="stl")
    verif = trimesh.load(stl, force="mesh")
    rel["final"] = metricas(verif)
    rel["final"]["bbox_mm"] = [round(float(x), 2) for x in verif.extents]
    rel["stl"] = stl
    rel["n_avisos"] = len(rel["avisos"])
    log(f"{cand}: export {rel['final']['triangulos']}t wt={rel['final']['watertight']} "
        f"bbox={rel['final']['bbox_mm']} esp_min={rel['espessura_minima_mm']}")
    return rel


def main():
    exp_path = os.path.join(OUT, "experimento_jubarte.json")
    exp = json.load(open(exp_path))
    for r in exp["rodadas"]:
        if not r["mesh_ok"]:
            continue
        cand = r["candidato"]
        rel = forjar(cand, os.path.join(OUT, f"trellis_{r['seed']}", "mesh.obj"))
        with open(os.path.join(FORJA_OUT, f"forja_report_{cand}.json"), "w") as f:
            json.dump(rel, f, indent=1, ensure_ascii=False)
    print("B2_FORJA_FIM")


if __name__ == "__main__":
    main()
