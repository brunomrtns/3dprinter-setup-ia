#!/usr/bin/env python3
"""Refinador Automotivo (tools/generator/refino_automotivo.py) — Fase C / C6:
Transforma malhas brutas/pós-processadas de veículos em malhas com:
  1. Alinhamento longitudinal do eixo central X(Z) (corrige traseira desalinhada / shear);
  2. Simetria bilateral matemática (X = -X) a partir do lado visível de alta definição (X >= 0),
     com preservação assimétrica opcional da zona do volante (apenas no lado do motorista, X > 0);
  3. Fusão booleana opcional da traseira multi-vista (Hunyuan3D-2mv + TripoSF 512, que viu traseira.jpg)
     com a carroceria/interna de alta definição do TripoSG + TripoSF 512;
  4. Calibração dimensional exata pelo Blueprint de fábrica do veículo (default: Volkswagen Fox
     3868 mm C × 1780 mm L c/ retrovisores × 1552 mm A -> 200,0 × 92,0 × 80,2 mm na escala 200mm).
"""
from __future__ import annotations

import os
import manifold3d
import numpy as np
import pymeshlab
import trimesh

CAR_DIR = os.path.expanduser("~/printer3d-work/carro")
MODELS_DIR = os.path.expanduser("~/printer3d-work/modelos3d-site/models")
DL_DIR = "/mnt/c/Users/Bruno/Downloads/fox-posproc"

FOX_LENGTH_MM = 3868.0
FOX_WIDTH_MIRRORS_MM = 1780.0
FOX_HEIGHT_MM = 1552.0


def to_man(m: trimesh.Trimesh) -> manifold3d.Manifold:
    return manifold3d.Manifold(
        manifold3d.Mesh(
            vert_properties=np.asarray(m.vertices, dtype=np.float32),
            tri_verts=np.asarray(m.faces, dtype=np.uint32),
        )
    )


def from_man(man: manifold3d.Manifold) -> trimesh.Trimesh:
    out = man.to_mesh()
    return trimesh.Trimesh(
        vertices=np.asarray(out.vert_properties[:, :3], dtype=np.float64),
        faces=np.asarray(out.tri_verts, dtype=np.int32),
        process=True,
    )


def deskew_longitudinal(m: trimesh.Trimesh) -> trimesh.Trimesh:
    """Endireita o eixo central X(Z) da dianteira até a traseira para eliminar torção/desalinhamento."""
    v = m.vertices.copy()
    z_min, z_max = v[:, 2].min(), v[:, 2].max()
    n_slices = 24
    z_edges = np.linspace(z_min, z_max, n_slices + 1)
    z_centers, x_centers = [], []
    for i in range(n_slices):
        mask = (v[:, 2] >= z_edges[i]) & (v[:, 2] <= z_edges[i + 1])
        if mask.sum() > 100:
            xs = v[mask, 0]
            x_mid = 0.5 * (np.percentile(xs, 2) + np.percentile(xs, 98))
            z_centers.append(0.5 * (z_edges[i] + z_edges[i + 1]))
            x_centers.append(x_mid)
    if len(z_centers) >= 4:
        coeffs = np.polyfit(z_centers, x_centers, deg=2)
        v[:, 0] -= np.polyval(coeffs, v[:, 2])
    m.vertices = v
    return m


def apply_fox_blueprint(m: trimesh.Trimesh, target_length_norm: float = 2.0) -> trimesh.Trimesh:
    """Trava a proporção dos 3 eixos nas dimensões reais do VW Fox (3868 x 1780 x 1552 mm)."""
    bounds = m.bounds
    center = 0.5 * (bounds[0] + bounds[1])
    ext = bounds[1] - bounds[0]
    m.vertices -= center

    target_z = target_length_norm
    target_x = target_length_norm * (FOX_WIDTH_MIRRORS_MM / FOX_LENGTH_MM)
    target_y = target_length_norm * (FOX_HEIGHT_MM / FOX_LENGTH_MM)

    m.vertices *= np.array([target_x / ext[0], target_y / ext[1], target_z / ext[2]], dtype=np.float64)
    return m


def symmetrize_bilateral(
    m: trimesh.Trimesh,
    best_side: str = "pos_x",
    preserve_driver_wheel_only: bool = False,
    preserve_wipers: bool = True,
) -> trimesh.Trimesh:
    """Aplica simetria bilateral matemática X = -X via manifold3d, preservando zonas naturalmente
    assimétricas do veículo (limpador traseiro, limpadores dianteiros e volante do motorista)."""
    man_orig = to_man(m)
    ext = m.bounding_box.extents
    big = float(max(ext)) * 4.0
    cutter = trimesh.creation.box(extents=[big, big, big])
    T = np.eye(4)
    if best_side == "pos_x":
        T[0, 3] = -big / 2.0 - 0.001
    else:
        T[0, 3] = big / 2.0 + 0.001
    cutter.apply_transform(T)
    half_man = man_orig - to_man(cutter)

    half_tm = from_man(half_man)
    mir_v = half_tm.vertices.copy()
    mir_v[:, 0] *= -1.0
    mir_f = half_tm.faces[:, ::-1].copy()
    mir_tm = trimesh.Trimesh(vertices=mir_v, faces=mir_f, process=True)
    mir_man = to_man(mir_tm)

    if preserve_driver_wheel_only:
        # Remove a cópia espelhada do volante no lado do passageiro (X < 0)
        wheel_box = trimesh.creation.box(extents=[0.24, 0.16, 0.18])
        Tw = np.eye(4)
        Tw[:3, 3] = [-0.17, 0.07, 0.24]
        wheel_box.apply_transform(Tw)
        mir_man = mir_man - to_man(wheel_box)

    sym_man = half_man + mir_man

    if preserve_wipers:
        # Preserva a geometria original (não-espelhada) no miolo do vidro traseiro (limpador traseiro único)
        # e na base do para-brisa dianteiro (limpadores dianteiros unidirecionais + contorno do volante)
        rear_wiper_box = trimesh.creation.box(extents=[0.46, 0.26, 0.28])
        Tr = np.eye(4)
        Tr[:3, 3] = [0.0, 0.11, -0.88]
        rear_wiper_box.apply_transform(Tr)

        front_wiper_box = trimesh.creation.box(extents=[0.52, 0.22, 0.34])
        Tf = np.eye(4)
        Tf[:3, 3] = [0.0, 0.08, 0.34]
        front_wiper_box.apply_transform(Tf)

        asym_zones = to_man(rear_wiper_box) + to_man(front_wiper_box)
        sym_man = (sym_man - asym_zones) + (man_orig ^ asym_zones)

    return from_man(sym_man)


def smooth_and_finalize(m: trimesh.Trimesh, target_faces: int = 260000) -> trimesh.Trimesh:
    ms = pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(vertex_matrix=m.vertices, face_matrix=m.faces))
    ms.apply_coord_taubin_smoothing(lambda_=0.45, mu=-0.47, stepsmoothnum=6)
    if len(m.faces) > target_faces:
        ms.meshing_decimation_quadric_edge_collapse(
            targetfacenum=target_faces,
            preservetopology=True,
            preserveboundary=True,
            preservenormal=True,
            optimalplacement=True,
        )
    curr = ms.current_mesh()
    out = trimesh.Trimesh(vertices=curr.vertex_matrix(), faces=curr.face_matrix(), process=True)
    trimesh.repair.fix_normals(out)
    return out


def export_glb_and_stl(m: trimesh.Trimesh, glb_name: str, stl_name: str | None = None):
    _ = m.vertex_normals
    glb_path = os.path.join(MODELS_DIR, glb_name)
    m.export(glb_path, file_type="glb", include_normals=True)
    print(
        f"[OK] {glb_name}: verts={len(m.vertices)}, faces={len(m.faces)}, "
        f"extents={[round(float(x), 4) for x in m.bounding_box.extents]}, watertight={m.is_watertight}",
        flush=True,
    )
    if stl_name:
        os.makedirs(DL_DIR, exist_ok=True)
        m_mm = m.copy()
        m_mm.apply_scale(100.0)  # 2.0 -> 200.0 mm
        stl_path = os.path.join(DL_DIR, stl_name)
        m_mm.export(stl_path)
        print(f"[STL 200mm] {stl_path}: extents_mm={[round(float(x), 2) for x in m_mm.bounding_box.extents]}", flush=True)


def main():
    hmv_sf_path = os.path.join(CAR_DIR, "hunyuan_mv_triposf512_posproc", "mesh_posproc.obj")
    hmv_raw_path = os.path.join(CAR_DIR, "hunyuan_mv_posproc", "mesh_posproc.obj")
    sg_sf_path = os.path.join(CAR_DIR, "nowin_triposf512_posproc", "mesh_posproc.obj")
    sg_raw_path = os.path.join(CAR_DIR, "nowin_triposg_posproc", "mesh_posproc.obj")

    # 1. TripoSG + TripoSF 512 (Sem Vidros + Interna Completa + 4 Rodas + Simetria Bilateral + Blueprint Fox)
    print("=== [1] Refinando TripoSG + TripoSF 512 (Simetria Bilateral + Blueprint Fox + 1 Volante) ===", flush=True)
    m_sgsf = trimesh.load(sg_sf_path, force="mesh")
    m_sgsf = deskew_longitudinal(m_sgsf)
    m_sgsf = apply_fox_blueprint(m_sgsf, target_length_norm=2.0)
    m_sgsf = symmetrize_bilateral(
        m_sgsf, best_side="pos_x", preserve_driver_wheel_only=True, preserve_wipers=False
    )
    m_sgsf = smooth_and_finalize(m_sgsf, target_faces=280000)
    export_glb_and_stl(
        m_sgsf, "carro_nowin__simetrico_interna.glb", "fox_triposf512_simetrico_interna_200mm.stl"
    )

    # 2. Hunyuan3D-2mv (4 vistas) + TripoSF 512 (Simetria Bilateral + Blueprint Fox + Limpadores Originais Únicos)
    print("=== [2] Refinando Hunyuan3D-2mv + TripoSF 512 (Simetria Bilateral + Blueprint Fox + Limpador Único) ===", flush=True)
    m_hmvsf = trimesh.load(hmv_sf_path, force="mesh")
    m_hmvsf = deskew_longitudinal(m_hmvsf)
    m_hmvsf = apply_fox_blueprint(m_hmvsf, target_length_norm=2.0)
    m_hmvsf = symmetrize_bilateral(
        m_hmvsf, best_side="neg_x", preserve_driver_wheel_only=False, preserve_wipers=True
    )
    m_hmvsf = smooth_and_finalize(m_hmvsf, target_faces=280000)
    export_glb_and_stl(
        m_hmvsf, "carro_nowin__simetrico_4vistas.glb", "fox_hunyuan_mv_simetrico_4vistas_200mm.stl"
    )


if __name__ == "__main__":
    main()
