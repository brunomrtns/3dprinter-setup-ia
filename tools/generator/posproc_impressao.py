#!/usr/bin/env python3
"""Pós-processamento para impressão (receita validada no caso anubis, 2026-11-18).

Malha crua de gerador (não-watertight, com ilhas) → peça imprimível:
  1. descarta fragmentos-ilha (mantém maior componente)
  2. reparo manifold3d (watertight por construção)
  3. escala p/ maior dimensão = --target-mm (default 200)
  4. suavização Taubin 5 it (pymeshlab)
  5. decimação p/ --target-faces (default 200k)
  6. espessura (raycast)
  7. oco: parede --wall-mm (3) + dreno --drain-mm (4.5) no eixo mais fino
  8. corte transversal do oco (metade) p/ inspeção interna

Uso:
  tools/setup/py.sh tools/generator/posproc_impressao.py --input mesh.obj --outdir posproc/ [--target-mm 200] [--label carro_front]
Saídas: <outdir>/{solido.obj,solido.stl,oco_dreno.obj,oco_dreno.stl,oco_corte.obj,posproc_report.json}
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time

import numpy as np


def t() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def stats(m) -> dict:
    return {
        "verts": int(len(m.vertices)),
        "faces": int(len(m.faces)),
        "watertight": bool(m.is_watertight),
        "winding": bool(m.is_winding_consistent),
        "is_volume": bool(m.is_volume),
        "components": int(len(m.split(only_watertight=False))),
        "volume": round(float(m.volume) if m.is_watertight else 0.0, 2),
        "bbox": [round(float(v), 3) for v in m.bounding_box.extents],
    }


def to_manifold(m):
    from manifold3d import Manifold, Mesh

    return Manifold(
        Mesh(
            vert_properties=np.asarray(m.vertices, dtype=np.float32),
            tri_verts=np.asarray(m.faces, dtype=np.uint32),
        )
    )


def from_manifold(man) -> "trimesh.Trimesh":
    import trimesh

    out = man.to_mesh()
    return trimesh.Trimesh(
        vertices=np.asarray(out.vert_properties[:, :3], dtype=np.float64),
        faces=np.asarray(out.tri_verts, dtype=np.int64),
        process=False,
    )


def taubin_decimate(mesh, taubin_iters: int, target_faces: int):
    import pymeshlab

    ms = pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(mesh.vertices, mesh.faces))
    if taubin_iters > 0:
        ms.apply_filter("taubin_smoothing", stepsmoothnum=taubin_iters)
    if len(mesh.faces) > target_faces:
        ms.apply_filter(
            "meshing_decimation_quadric_edge_collapse", targetfacenum=target_faces
        )
    out = ms.current_mesh()
    import trimesh

    return trimesh.Trimesh(
        vertices=np.asarray(out.vertex_matrix(), dtype=np.float64),
        faces=np.asarray(out.face_matrix(), dtype=np.int64),
        process=False,
    )


def espessura_mm(mesh, n=1500, seed=42) -> dict:
    import trimesh

    pts, fidx = trimesh.sample.sample_surface(mesh, n, seed=seed)
    normals = mesh.face_normals[fidx]
    try:
        import open3d as o3d

        scene = o3d.t.geometry.RaycastingScene()
        scene.add_triangles(
            o3d.core.Tensor(np.asarray(mesh.vertices, dtype=np.float32)),
            o3d.core.Tensor(np.asarray(mesh.faces, dtype=np.uint32)),
        )
        rays = np.hstack([pts, -normals]).astype(np.float32)
        t_hit = scene.cast_rays(o3d.core.Tensor(rays))["t_hit"].numpy()
        valid = t_hit[np.isfinite(t_hit) & (t_hit > 1e-3)]
        if len(valid) == 0:
            return {"erro": "sem raios validos"}
        return {
            "min_mm": round(float(valid.min()), 3),
            "pct5_mm": round(float(np.percentile(valid, 5)), 3),
            "pct10_mm": round(float(np.percentile(valid, 10)), 3),
            "median_mm": round(float(np.median(valid)), 3),
            "valid_rays": int(len(valid)),
            "total_rays": int(len(pts)),
        }
    except ImportError:
        return {"erro": "open3d ausente"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--label", default="posproc")
    ap.add_argument("--target-mm", type=float, default=200.0)
    ap.add_argument("--target-faces", type=int, default=200_000)
    ap.add_argument("--wall-mm", type=float, default=3.0)
    ap.add_argument("--drain-mm", type=float, default=4.5)
    args = ap.parse_args()

    import trimesh

    os.makedirs(args.outdir, exist_ok=True)
    report = {
        "input": os.path.abspath(args.input),
        "label": args.label,
        "target_mm": args.target_mm,
        "ts_start": t(),
        "stages": {},
    }
    T0 = time.time()

    raw = trimesh.load(args.input, force="mesh", process=False)
    report["stages"]["0_raw"] = stats(raw)

    # 1. maior componente (descarta ilhas)
    comps = raw.split(only_watertight=False)
    top = max(comps, key=lambda c: len(c.faces))
    report["stages"]["1_maior_componente"] = {
        **stats(top),
        "dropped_fragments": len(comps) - 1,
    }

    # 2. reparo watertight: PyMeshFix (caminho canônico da Forja) + roundtrip manifold3d
    t_fix = time.time()
    import pymeshfix

    fixer = pymeshfix.MeshFix(np.asarray(top.vertices), np.asarray(top.faces))
    fixer.repair()
    fixed = trimesh.Trimesh(
        vertices=np.asarray(fixer.points, dtype=np.float64),
        faces=np.asarray(fixer.faces, dtype=np.int64),
        process=False,
    )
    fixed.fix_normals()
    man = to_manifold(fixed)
    if str(man.status()) != "Error.NoError":
        raise RuntimeError(f"manifold3d rejeitou pós-pymeshfix: {man.status()}")
    rep = from_manifold(man)
    # 3. escala p/ maior dimensão = target_mm
    scale = args.target_mm / max(rep.bounding_box.extents)
    rep.apply_scale(scale)
    report["stages"]["2_reparo_pymeshfix_manifold_200mm"] = {
        **stats(rep),
        "scale_factor": round(float(scale), 5),
        "time_s": round(time.time() - t_fix, 2),
    }
    rep.export(os.path.join(args.outdir, "01_reparado.obj"))

    # 4+5. Taubin + decimação
    t1 = time.time()
    smooth = taubin_decimate(rep, taubin_iters=5, target_faces=args.target_faces)
    report["stages"]["3_taubin5_decimacao"] = {
        **stats(smooth),
        "time_s": round(time.time() - t1, 2),
    }
    solido_path = os.path.join(args.outdir, "solido.obj")
    smooth.export(solido_path)
    smooth.export(os.path.join(args.outdir, "solido.stl"))

    # 6. espessura
    report["stages"]["4_espessura"] = espessura_mm(smooth)

    # 7. oco + dreno (manifold3d): interno = offset negativo; furo no eixo mais fino
    t2 = time.time()
    hollow_info = {"skipped": True}
    try:
        solid_man = to_manifold(smooth)
        inner = solid_man.offset(-args.wall_mm)
        hollow_man = solid_man - inner  # casca

        # dreno: eixo de menor extensão = provável eixo vertical do carro
        ext = smooth.bounding_box.extents
        axis = int(np.argmin(ext))
        center = smooth.bounding_box.centroid
        r = args.drain_mm / 2.0
        import trimesh.creation

        cyl_len = float(ext[axis]) + 10.0
        cyl = trimesh.creation.cylinder(radius=r, height=cyl_len, sections=64)
        shift = np.zeros(3)
        shift[axis] = -cyl_len / 2.0 + ext[axis] / 2.0  # atravessa de ponta a ponta
        T = np.eye(4)
        T[:3, 3] = center + shift
        cyl.apply_transform(T)
        # cilindro atravessa o modelo no eixo fino — o furo sai dos dois lados
        hole = to_manifold(cyl)
        hollow_man = hollow_man - hole

        hollow = from_manifold(hollow_man)
        hollow.export(os.path.join(args.outdir, "oco_dreno.obj"))
        hollow.export(os.path.join(args.outdir, "oco_dreno.stl"))
        hollow_info = {
            **stats(hollow),
            "wall_mm": args.wall_mm,
            "drain_diam_mm": args.drain_mm,
            "drain_axis": ["x", "y", "z"][axis],
            "volume_solido_cm3": round(float(smooth.volume) / 1000.0, 2),
            "volume_oco_cm3": round(float(hollow.volume) / 1000.0, 2),
            "resina_economizada_pct": round(
                100.0 * (1.0 - hollow.volume / max(smooth.volume, 1e-9)), 1
            ),
            "time_s": round(time.time() - t2, 2),
        }

        # 8. corte transversal (metade da casca) p/ inspeção interna
        t3 = time.time()
        big = np.max(ext) * 3.0
        box = trimesh.creation.box(extents=[big, big, big])
        cut_center = np.array(center, dtype=float)
        cut_center[axis] = 0.0  # reposiciona depois
        # metade "negativa" no eixo do comprimento (maior extensão)
        long_axis = int(np.argmax(ext))
        box_center = np.zeros(3)
        box_center[long_axis] = -big / 2.0 + smooth.bounding_box.bounds[0][long_axis]
        T2 = np.eye(4)
        T2[:3, 3] = box_center
        box.apply_transform(T2)
        corte = from_manifold(hollow_man - to_manifold(box))
        corte.export(os.path.join(args.outdir, "oco_corte.obj"))
        hollow_info["corte_time_s"] = round(time.time() - t3, 2)
        hollow_info["corte"] = stats(corte)
    except Exception as e:  # noqa: BLE001
        hollow_info = {"erro": f"{type(e).__name__}: {e}"}

    report["stages"]["5_oco_dreno_corte"] = hollow_info
    report["outputs"] = {
        "solido_obj": solido_path,
        "solido_stl": os.path.join(args.outdir, "solido.stl"),
    }
    report["total_time_s"] = round(time.time() - T0, 2)
    report["ts_end"] = t()
    with open(os.path.join(args.outdir, "posproc_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("POSPROC_OK=" + json.dumps({k: report["stages"][k] for k in list(report["stages"])[:3]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
