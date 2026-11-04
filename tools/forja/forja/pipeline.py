#!/usr/bin/env python3
"""Pipeline de reparo — cada etapa mede métricas antes/depois."""
from __future__ import annotations

import datetime
import os
import tempfile

import numpy as np
import pymeshfix
import trimesh

FORJA_DIR = os.path.dirname(os.path.abspath(__file__))


def agora() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def metricas(m: trimesh.Trimesh) -> dict:
    try:
        vol = float(m.volume)
    except Exception:  # noqa: BLE001
        vol = None
    try:
        n_comp = len(m.split(only_watertight=False))
    except Exception:  # noqa: BLE001
        n_comp = None
    return {
        "vertices": int(len(m.vertices)),
        "triangulos": int(len(m.faces)),
        "watertight": bool(m.is_watertight),
        "winding_consistent": bool(m.is_winding_consistent),
        "volume": vol,
        "componentes": n_comp,
        "bbox": [round(float(x), 4) for x in m.extents],
    }


def _faces_duplicadas(m: trimesh.Trimesh) -> int:
    # Proxy barato de autointerseção: faces exatamente duplicadas.
    vistos = set()
    dup = 0
    for f in m.faces:
        k = tuple(sorted(f.tolist()))
        if k in vistos:
            dup += 1
        vistos.add(k)
    return dup


def carregar(caminho: str) -> trimesh.Trimesh:
    cena = trimesh.load(caminho, force="mesh", process=False)
    return cena


def etapa(msg: str) -> None:
    print(f"[forja] {msg}", flush=True)


def reparar(
    entrada: str,
    saida_stl: str,
    target_height_mm: float | None = None,
    smooth_iter: int = 0,
    voxel: float | None = None,
    max_tris: int | None = None,
    keep_all_components: bool = False,
    min_component_tris: int = 50,
) -> dict:
    rel = {
        "entrada": entrada,
        "saida": saida_stl,
        "ts": agora(),
        "etapas": [],
        "avisos": [],
        "parametros": {
            "target_height_mm": target_height_mm,
            "smooth": smooth_iter,
            "voxel": voxel,
            "max_tris": max_tris,
            "keep_all_components": keep_all_components,
            "min_component_tris": min_component_tris,
        },
    }

    # 1. Load + limpeza
    m = carregar(entrada)
    antes = metricas(m)
    etapa(f"1.limpeza: {antes['vertices']}v/{antes['triangulos']}t, wt={antes['watertight']}")
    m.update_faces(m.nondegenerate_faces(height=1e-8))
    comps = m.split(only_watertight=False)
    if not comps:
        raise RuntimeError("malha vazia após limpeza")
    if keep_all_components:
        keep = [c for c in comps if len(c.faces) >= min_component_tris]
        perdidos = len(comps) - len(keep)
        if perdidos:
            rel["avisos"].append(f"{perdidos} componente(s) removidos (< {min_component_tris} tris)")
    else:
        keep = [max(comps, key=lambda c: len(c.faces))]
        if len(comps) > 1:
            rel["avisos"].append(f"{len(comps) - 1} componente(s) descartados (mantido o maior)")
    m = trimesh.util.concatenate(keep) if len(keep) > 1 else keep[0]
    m.merge_vertices()
    rel["etapas"].append({"nome": "limpeza", "antes": antes, "depois": metricas(m)})

    # 2. Normais
    antes = metricas(m)
    m.fix_normals()
    m.remove_unreferenced_vertices()
    rel["etapas"].append({"nome": "normais", "antes": antes, "depois": metricas(m)})

    # 3. Furos e não-manifold (PyMeshFix)
    antes = metricas(m)
    mf = pymeshfix.MeshFix(np.asarray(m.vertices, dtype=np.float64),
                           np.asarray(m.faces, dtype=np.int32))
    mf.repair()
    m = trimesh.Trimesh(vertices=np.asarray(mf.points), faces=np.asarray(mf.faces), process=False)
    rel["etapas"].append({"nome": "pymeshfix", "antes": antes, "depois": metricas(m)})
    if not m.is_watertight:
        rel["avisos"].append("watertight=False mesmo após PyMeshFix (caso muito degradado)")

    # 4. Suavização opcional
    if smooth_iter > 0:
        antes = metricas(m)
        for _ in range(smooth_iter):
            m = trimesh.smoothing.filter_laplacian(m, iterations=1, volume_constraint=True)
        rel["etapas"].append({"nome": "smooth", "params": {"iteracoes": smooth_iter},
                              "antes": antes, "depois": metricas(m)})

    # 5. Remesh voxel opcional (Blender headless, CPU)
    if voxel is not None:
        antes = metricas(m)
        m = _blender_mod(m, voxel=voxel)
        rel["etapas"].append({"nome": "voxel_remesh", "params": {"voxel": voxel},
                              "antes": antes, "depois": metricas(m)})

    # 6. Decimação opcional
    if max_tris is not None and len(m.faces) > max_tris:
        antes = metricas(m)
        m = _blender_mod(m, max_tris=max_tris)
        rel["etapas"].append({"nome": "decimate", "params": {"max_tris": max_tris},
                              "antes": antes, "depois": metricas(m)})

    # Autointerseção (proxy: faces duplicadas exatas; checagem completa = limitação)
    dup = _faces_duplicadas(m)
    if dup:
        rel["avisos"].append(f"faces duplicadas (proxy de autointerseção): {dup}")
    rel["avisos"].append(
        "checagem completa de autointerseção não implementada (limitação conhecida desta fase)"
    )

    # 7. Escala
    ext_antes = [round(float(x), 4) for x in m.extents]
    if target_height_mm is not None:
        maior = float(max(m.extents))
        s = target_height_mm / maior
        m.apply_scale(s)
        rel["etapas"].append({
            "nome": "escala",
            "params": {"target_height_mm": target_height_mm, "fator": round(s, 6),
                       "criterio": "maior dimensão da bbox (malha de gerador não tem orientação canônica)"},
            "antes": {"bbox": ext_antes}, "depois": {"bbox": [round(float(x), 3) for x in m.extents]},
        })
    else:
        rel["avisos"].append("sem --target-height: escala UNITÁRIA (bbox reportada em unidades de malha)")

    # 8. Export
    os.makedirs(os.path.dirname(os.path.abspath(saida_stl)), exist_ok=True)
    m.export(saida_stl, file_type="stl")
    m.export(saida_stl.replace(".stl", ".obj"), file_type="obj")
    verif = trimesh.load(saida_stl, force="mesh")
    rel["final"] = metricas(verif)
    rel["final"]["arquivo"] = saida_stl
    rel["final"]["bbox_mm"] = [round(float(x), 3) for x in verif.extents]
    etapa(f"8.export: {rel['final']['triangulos']}t wt={rel['final']['watertight']} "
          f"vol={rel['final']['volume']:.1f} bbox_mm={rel['final']['bbox_mm']}")
    return rel


def _blender_mod(m: trimesh.Trimesh, voxel: float | None = None,
                 max_tris: int | None = None) -> trimesh.Trimesh:
    import subprocess

    with tempfile.TemporaryDirectory() as td:
        inp = os.path.join(td, "in.obj")
        out = os.path.join(td, "out.obj")
        m.export(inp)
        cmd = ["blender", "-b", "-P", os.path.join(FORJA_DIR, "blender_mod.py"), "--",
               "--input", inp, "--output", out]
        if voxel is not None:
            cmd += ["--voxel", str(voxel)]
        if max_tris is not None:
            cmd += ["--max-tris", str(max_tris)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
        if not os.path.isfile(out):
            raise RuntimeError(f"blender_mod falhou: {r.stdout[-500:]} {r.stderr[-500:]}")
        return trimesh.load(out, force="mesh", process=False)
