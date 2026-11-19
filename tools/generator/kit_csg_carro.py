#!/usr/bin/env python3
"""Kit de Montagem CSG (C7-A, 2026-11-18) — carroceria oca + janelas booleanas
2D→3D + banheira interna + roda mestre instanciada 4x.

Spec: docs/knowledge/modelagem-hard-surface-e-veiculos.md (Opção 1 / Módulo 2A-2C).
Entradas (malhas e máscaras que JÁ EXISTEM do C6):
  - carroceria: ~/printer3d-work/carro/hunyuan_mv_triposf512_posproc/mesh_posproc.obj
    (die-cast fechado, frente/traseira fiéis) → deskew + blueprint + simetria
    (refino_automotivo) → casca oca (EDT voxel shell + PyMeshFix -> Manifold) → recortes;
  - banheira: ~/printer3d-work/carro/nowin_triposf512_posproc/mesh_posproc.obj
    (cabine interna completa) → mesmas transformações → ∩ núcleo interno (inner) ∩ habitáculo;
  - máscaras de vidro: no_windows_rgba/<vista>_{solid,open}.png (janela =
    solid − open, fotos do dono em Downloads/fox/no-windows, prep C6);
  - roda mestre: ~/printer3d-work/carro/c7_roda_mestre/mesh.obj (TripoSG seed 42
    no close 1024px da roda na foto lado) → regularização cilíndrica 360° → 4 instâncias
    (com espelhamento X nas rodas direitas para a calota apontar sempre para fora).

Uso:
  tools/setup/py.sh tools/generator/kit_csg_carro.py --report <repo>/evidence/rtx3060-12gb/carro-csg/report.json
Saídas: models/carro_csg__{kit,casca,interna,kit_corte}.glb + OBJs em ~/printer3d-work/carro/c7_kit/
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time

import numpy as np
import pymeshfix
import pymeshlab
import trimesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refino_automotivo as ra  # noqa: E402

from scipy.ndimage import (  # noqa: E402
    binary_closing,
    binary_fill_holes,
    binary_opening,
    distance_transform_edt,
    gaussian_filter,
)
from PIL import Image  # noqa: E402

CAR_DIR = os.path.expanduser("~/printer3d-work/carro")
MODELS_DIR = os.path.expanduser("~/printer3d-work/modelos3d-site/models")
RGBA = os.path.join(CAR_DIR, "no_windows_rgba")

# Medidos da foto lado (2026-11-18): posições dos eixos no gabarito Blueprint z∈[-1,1]
AXLE_FRONT_Z = 0.626
AXLE_REAR_Z = -0.734
WHEEL_R = 0.173  # ⌀ ≈ 34,6mm na escala 200mm
WHEEL_X = 0.336
WHEEL_Y = -0.401 + WHEEL_R
ARCH_R = WHEEL_R * 1.12
BELTLINE_Y = -0.338
WIN_Z = (-0.828, 0.707)


def t() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def to_man(m):
    from manifold3d import Manifold, Mesh

    return Manifold(
        Mesh(
            vert_properties=np.asarray(m.vertices, dtype=np.float32),
            tri_verts=np.asarray(m.faces, dtype=np.uint32),
        )
    )


def from_man(man) -> trimesh.Trimesh:
    out = man.to_mesh()
    return trimesh.Trimesh(
        vertices=np.asarray(out.vert_properties[:, :3], dtype=np.float64),
        faces=np.asarray(out.tri_verts, dtype=np.int64),
        process=True,
    )


def repair_to_man(m: trimesh.Trimesh):
    """Garante malha 100% manifold via PyMeshFix antes de converter para Manifold3D."""
    mf = pymeshfix.MeshFix(np.asarray(m.vertices, dtype=np.float64), np.asarray(m.faces, dtype=np.int32))
    mf.repair()
    fixed = trimesh.Trimesh(vertices=mf.points, faces=mf.faces, process=True)
    trimesh.repair.fix_normals(fixed)
    return to_man(fixed), fixed


def erode_core(body: trimesh.Trimesh, wall: float) -> tuple[trimesh.Trimesh, float, float]:
    """Gera o núcleo interno erodido por `wall` (3mm = 0.03 na escala 2.0):
    1. Voxeliza a superfície da carroceria e preenche o interior 3D via binary_fill_holes;
    2. Calcula a Transformada de Distância Euclidiana (EDT) exata em 3D;
    3. Extrai a isosuperfície (dist >= wall) via cubos RLE no manifold3d + suavização Taubin + PyMeshFix."""
    from manifold3d import Manifold, OpType

    pitch = 0.012  # 1,2 mm na escala 200mm (grade ~80 x 70 x 170 -> rápido e preciso)
    vg = body.voxelized(pitch=pitch)
    surf_mat = vg.matrix
    # Fecha eventuais frestas de 1 voxel na casca e preenche todo o interior 3D
    closed_surf = binary_closing(surf_mat, structure=np.ones((3, 3, 3), dtype=bool))
    filled = binary_fill_holes(closed_surf)

    dist = distance_transform_edt(filled, sampling=(pitch, pitch, pitch))
    core_vox = filled & (dist >= wall)
    if not core_vox.any():
        raise RuntimeError("erode_core: núcleo vazio")

    origin = vg.translation
    nx, ny, nz = core_vox.shape
    cubes = []
    for i in range(nx):
        for j in range(ny):
            col = core_vox[i, j]
            if not col.any():
                continue
            d = np.diff(np.pad(col.astype(int), 1))
            starts, ends = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
            for s, e in zip(starts, ends):
                size = (pitch, pitch, (e - s) * pitch)
                pos = (
                    float(origin[0] + (i - 0.5) * pitch),
                    float(origin[1] + (j - 0.5) * pitch),
                    float(origin[2] + (s - 0.5) * pitch),
                )
                cubes.append(Manifold.cube(size=size, center=False).translate(pos))

    level = cubes
    while len(level) > 1:
        level = [
            Manifold.batch_boolean(level[i : i + 256], OpType.Add)
            for i in range(0, len(level), 256)
        ]
    raw_core = from_man(level[0])
    # Suaviza os degraus do RLE no núcleo interno com Taubin 6it para parede interna lisa
    ms = pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(raw_core.vertices, raw_core.faces))
    ms.apply_coord_taubin_smoothing(lambda_=0.48, mu=-0.50, stepsmoothnum=6)
    cur = ms.current_mesh()
    smooth_core = trimesh.Trimesh(vertices=cur.vertex_matrix(), faces=cur.face_matrix(), process=True)
    _, clean_core = repair_to_man(smooth_core)
    vol_body = float(filled.sum()) * (pitch ** 3)
    vol_core = float(core_vox.sum()) * (pitch ** 3)
    return clean_core, round(vol_body, 4), round(vol_core, 4)


def stats(m) -> dict:
    return {
        "verts": int(len(m.vertices)),
        "faces": int(len(m.faces)),
        "watertight": bool(m.is_watertight),
        "components": int(len(m.split(only_watertight=False))),
        "volume": round(float(m.volume), 4) if m.is_watertight else None,
        "bbox": [round(float(v), 3) for v in m.bounding_box.extents],
    }


def load_mask(name: str, kind: str) -> np.ndarray:
    return np.asarray(Image.open(os.path.join(RGBA, f"{name}_{kind}.png")))[..., 3] >= 128


def window_mask(name: str, min_px: int = 150) -> tuple[np.ndarray, dict]:
    """janela = solid − open, limpa de ruído; devolve máscara bool + bbox do solid."""
    solid = load_mask(name, "solid")
    open_ = load_mask(name, "open")
    win = solid & ~open_
    win = binary_opening(win, structure=np.ones((3, 3)))
    win = binary_closing(win, structure=np.ones((9, 9)))
    sy, sx = np.nonzero(solid)
    meta = {"solid_bbox": [int(sx.min()), int(sx.max()), int(sy.min()), int(sy.max())]}
    if win.sum() < min_px:
        raise RuntimeError(f"máscara de janela vazia p/ {name}: {win.sum()} px")
    meta["win_px"] = int(win.sum())
    return win, meta


def mask_prism_man(mask: np.ndarray, u_to_a, v_to_b, depth: tuple[float, float], axis: int):
    """Extruda a máscara 2D em prisma CSG diretamente no manifold3d (Manifold.cube center=False
    + batch_boolean OpType.Add), garantindo centragem exata e malha 100% watertight."""
    from manifold3d import Manifold, OpType

    H, W = mask.shape
    smooth = gaussian_filter(mask.astype(np.float32), 2.0) > 0.5
    a, b = sorted({0, 1, 2} - {axis})
    cubes = []
    for r in range(H):
        row = smooth[r]
        if not row.any():
            continue
        d = np.diff(np.concatenate([[0], row.astype(int), [0]]))
        starts, ends = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
        ya, yb = sorted([v_to_b(r), v_to_b(min(r + 1, H - 1))])
        for s, e in zip(starts, ends):
            xa, xb = sorted([u_to_a(s), u_to_a(e - 1)])
            ext = [0.0, 0.0, 0.0]
            ext[a] = float(xb - xa + 2e-4)
            ext[b] = float(yb - ya + 2e-4)
            ext[axis] = float(depth[1] - depth[0])
            pos = [0.0, 0.0, 0.0]
            pos[a] = float(xa - 1e-4)
            pos[b] = float(ya - 1e-4)
            pos[axis] = float(depth[0])
            cubes.append(Manifold.cube(size=tuple(ext), center=False).translate(tuple(pos)))
    if not cubes:
        raise RuntimeError("máscara de janela vazia após suavização")
    level = cubes
    while len(level) > 1:
        level = [
            Manifold.batch_boolean(level[i : i + 256], OpType.Add)
            for i in range(0, len(level), 256)
        ]
    return level[0]


def regularize_wheel(mesh_path: str, r_target: float, width_cap: float = 0.13) -> trimesh.Trimesh:
    """Roda mestre 360° circular:
    1. Seleciona o componente circular da roda (comp 1: 1.0006 x 1.0042 x 0.3543);
    2. Decima e repara com PyMeshFix para não perder faces no CSG;
    3. Alinha o eixo fino ao eixo X e centraliza pelo CENTRO DA BOUNDING BOX (não pelo centroide
       de massa, que deslocava a roda e cortava metade no cilindro!);
    4. Encamisa num pneu cilíndrico perfeito de raio `r_target` (diametro Y == diametro Z == 2*r_target)."""
    w_all = trimesh.load(mesh_path, force="mesh", process=False)
    comps = sorted(w_all.split(only_watertight=False), key=lambda c: len(c.faces), reverse=True)
    wheel = None
    for c in comps[:6]:
        e = np.sort(c.bounding_box.extents)
        if len(c.faces) >= 20_000 and e[2] / e[1] <= 1.15 and e[1] / e[0] >= 2.2:
            wheel = c
            break
    if wheel is None:
        wheel = comps[0]
    w = wheel

    ms = pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(w.vertices, w.faces))
    if len(w.faces) > 80_000:
        ms.meshing_decimation_quadric_edge_collapse(targetfacenum=80_000)
    ms.apply_coord_taubin_smoothing(lambda_=0.45, mu=-0.47, stepsmoothnum=4)
    cur = ms.current_mesh()
    w = trimesh.Trimesh(vertices=cur.vertex_matrix(), faces=cur.face_matrix(), process=True)

    # Identifica o eixo mais fino da bounding box (no comp 1 é Z=0.354 vs X=1.00, Y=1.00)
    ext0 = w.bounds[1] - w.bounds[0]
    thin_axis = int(np.argmin(ext0))
    if thin_axis == 2:
        # Rotaciona Z -> X (90 graus em torno de Y)
        w.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    elif thin_axis == 1:
        # Rotaciona Y -> X (90 graus em torno de Z)
        w.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 0, 1]))

    # Centraliza pelo CENTRO GEOMÉTRICO DA BOUNDING BOX (garante círculo 360° centrado em Y=0, Z=0)
    bbox_center = 0.5 * (w.bounds[0] + w.bounds[1])
    w.vertices -= bbox_center

    ext = w.bounds[1] - w.bounds[0]
    scale_x = width_cap / max(float(ext[0]), 1e-4)
    scale_y = (2.0 * r_target) / max(float(ext[1]), 1e-4)
    scale_z = (2.0 * r_target) / max(float(ext[2]), 1e-4)
    w.vertices *= np.array([scale_x, scale_y, scale_z], dtype=np.float64)

    # Repara via PyMeshFix antes de CSG no manifold3d
    w_man, _ = repair_to_man(w)

    # Cilindro externo de encamisamento (corta qualquer rebarba fora de r_target)
    outer_cyl = trimesh.creation.cylinder(radius=r_target, height=width_cap * 1.05, sections=96)
    outer_cyl.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))

    # Anel toroidal/cilíndrico de banda de rodagem + cubo interno para garantir pneu 100% fechado 360°
    tire_outer = trimesh.creation.cylinder(radius=r_target, height=width_cap * 0.88, sections=96)
    tire_outer.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    tire_inner = trimesh.creation.cylinder(radius=r_target * 0.68, height=width_cap * 1.2, sections=96)
    tire_inner.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    hub_disc = trimesh.creation.cylinder(radius=r_target * 0.72, height=width_cap * 0.45, sections=96)
    hub_disc.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))

    tire_ring_man = (to_man(tire_outer) - to_man(tire_inner)) + to_man(hub_disc)
    final_wheel_man = (w_man + tire_ring_man) ^ to_man(outer_cyl)
    out = from_man(final_wheel_man)
    trimesh.repair.fix_normals(out)
    return out


def decimate(m, target: int) -> trimesh.Trimesh:
    if len(m.faces) <= target:
        return m
    ms = pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(m.vertices, m.faces))
    ms.meshing_decimation_quadric_edge_collapse(
        targetfacenum=target, preservetopology=True, preserveboundary=True
    )
    cur = ms.current_mesh()
    out = trimesh.Trimesh(vertices=cur.vertex_matrix(), faces=cur.face_matrix(), process=True)
    trimesh.repair.fix_normals(out)
    return out


def export_glb(m, name: str, meta: dict):
    _ = m.vertex_normals
    path = os.path.join(MODELS_DIR, name)
    m.export(path, file_type="glb", include_normals=True)
    meta[name] = {
        "verts": int(len(m.vertices)),
        "faces": int(len(m.faces)),
        "watertight": bool(m.is_watertight),
    }
    print(f"[OK] {name}: {meta[name]}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--wall-mm", type=float, default=3.0)
    args = ap.parse_args()
    T0 = time.time()
    wall = args.wall_mm / 100.0  # 3mm na escala 200mm (comprimento 2.0 = 200mm)

    rep = {"ts_start": t(), "wall_mm": args.wall_mm, "stages": {}}

    # ── 1. carroceria: die-cast fechado → deskew + blueprint + simetria + PyMeshFix ──
    print("== [1] carroceria hunyuan_mv_sf512 → blueprint + simetria + repair ==", flush=True)
    body = trimesh.load(
        os.path.join(CAR_DIR, "hunyuan_mv_triposf512_posproc", "mesh_posproc.obj"),
        force="mesh",
        process=False,
    )
    body = ra.deskew_longitudinal(body)
    body = ra.apply_fox_blueprint(body, target_length_norm=2.0)
    body = ra.symmetrize_bilateral(
        body, best_side="neg_x", preserve_driver_wheel_only=False, preserve_wipers=True
    )
    man_body, body = repair_to_man(body)
    rep["stages"]["1_carroceria"] = stats(body)
    print("   1_carroceria:", rep["stages"]["1_carroceria"], flush=True)

    # ── 2. casca oca real (binary_fill_holes + EDT >= wall + Taubin + PyMeshFix) ──
    print("== [2] casca oca (parede %.2fmm, EDT voxel shell) ==" % args.wall_mm, flush=True)
    t2 = time.time()
    inner, vol_body_est, vol_core_est = erode_core(body, wall)
    man_inner = to_man(inner)
    casca_man = man_body - man_inner
    casca_oca_tm = from_man(casca_man)
    rep["stages"]["2_casca_oca"] = {
        **stats(casca_oca_tm),
        "vol_solido": round(float(body.volume), 4),
        "vol_nucleo_subtraido": round(float(inner.volume), 4),
        "vol_casca_final": round(float(casca_oca_tm.volume), 4),
        "reducao_volume_pct": round(100.0 * (1.0 - float(casca_oca_tm.volume) / max(float(body.volume), 1e-6)), 1),
        "metodo": "voxel_fill_holes+EDT+RLE_manifold+taubin6+pymeshfix",
        "time_s": round(time.time() - t2, 2),
    }
    print("   2_casca_oca:", rep["stages"]["2_casca_oca"], flush=True)

    # ── 3. vãos de vidro por booleana 2D→3D (centrados e 100% Manifold) ──
    print("== [3] corte booleano das janelas (máscaras 2D→3D) ==", flush=True)
    t3 = time.time()

    win_lado, meta_lado = window_mask("lado")
    u0, u1, v0, v1 = meta_lado["solid_bbox"]
    zmin, zmax, ymin, ymax = -1.0, 1.0, -0.401, 0.401
    u_to_z = lambda u: zmax - (u - u0) / (u1 - u0) * (zmax - zmin)  # noqa: E731
    v_to_y = lambda v: ymax - (v - v0) / (v1 - v0) * (ymax - ymin)  # noqa: E731
    prism_side_man = mask_prism_man(win_lado, u_to_z, v_to_y, depth=(-1.2, 1.2), axis=0)
    casca_man = casca_man - prism_side_man

    for name, depth in (("frente", (0.15, 0.85)), ("traseira", (-1.05, -0.55))):
        win, meta = window_mask(name)
        fu0, fu1, fv0, fv1 = meta["solid_bbox"]
        xmin, xmax = -0.46, 0.46
        u_to_x = lambda u, a=fu0, b=fu1: xmin + (u - a) / (b - a) * (xmax - xmin)  # noqa: E731
        v_to_y2 = lambda v, a=fv0, b=fv1: ymax - (v - a) / (b - a) * (ymax - ymin)  # noqa: E731
        prism_man = mask_prism_man(win, u_to_x, v_to_y2, depth=depth, axis=2)
        casca_man = casca_man - prism_man

    # ── 4. caixas de roda (4 cilindros no eixo X) ──
    print("== [4] caixas de roda (cilindros booleanos) ==", flush=True)
    for z in (AXLE_FRONT_Z, AXLE_REAR_Z):
        cyl = trimesh.creation.cylinder(radius=ARCH_R, height=2.4, sections=96)
        cyl.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
        cyl.apply_translation([0.0, WHEEL_Y, z])
        casca_man = casca_man - to_man(cyl)

    casca_raw = from_man(casca_man)
    # Mantém componentes principais da casca (>= 500 faces) e garante normais consistentes
    c_comps = sorted(casca_raw.split(only_watertight=False), key=lambda c: len(c.faces), reverse=True)
    casca = trimesh.util.concatenate([c for c in c_comps if len(c.faces) >= 500] or [c_comps[0]])
    _, casca = repair_to_man(casca)
    rep["stages"]["3_janelas_e_arcos"] = {**stats(casca), "time_s": round(time.time() - t3, 2)}
    print("   3_janelas_e_arcos:", rep["stages"]["3_janelas_e_arcos"], flush=True)

    # ── 5. banheira interna (contida 100% dentro do núcleo interno da carroceria!) ──
    print("== [5] banheira interna (∩ núcleo interno ∩ habitáculo) ==", flush=True)
    t5 = time.time()
    tub = trimesh.load(
        os.path.join(CAR_DIR, "nowin_triposf512_posproc", "mesh_posproc.obj"),
        force="mesh",
        process=False,
    )
    tub = ra.deskew_longitudinal(tub)
    tub = ra.apply_fox_blueprint(tub, target_length_norm=2.0)
    tub = ra.symmetrize_bilateral(
        tub, best_side="pos_x", preserve_driver_wheel_only=True, preserve_wipers=False
    )
    man_tub, _ = repair_to_man(tub)
    # Caixa do habitáculo (bancos, painel, volante e assoalho, abaixo do teto para não tampar as janelas)
    cabin = trimesh.creation.box(extents=[0.76, 0.44, 1.18])
    cabin.apply_translation([0.0, -0.07, -0.06])
    # Interseciona com man_inner (núcleo interno da carroceria) para NUNCA vazar para fora das portas!
    tub_man = (man_tub ^ man_inner) ^ to_man(cabin)
    tub_raw = from_man(tub_man)
    t_comps = sorted(tub_raw.split(only_watertight=False), key=lambda c: len(c.faces), reverse=True)
    tub = trimesh.util.concatenate([c for c in t_comps if len(c.faces) >= 300] or [t_comps[0]])
    _, tub = repair_to_man(tub)
    rep["stages"]["5_banheira"] = {**stats(tub), "time_s": round(time.time() - t5, 2)}
    print("   5_banheira:", rep["stages"]["5_banheira"], flush=True)

    # ── 6. roda mestre 360° circular + 4 instâncias (espelhadas Dir/Esq) ──
    print("== [6] roda mestre (regularização cilíndrica 360°) + 4 instâncias ==", flush=True)
    t6 = time.time()
    roda = regularize_wheel(
        os.path.join(CAR_DIR, "c7_roda_mestre", "mesh.obj"),
        r_target=WHEEL_R,
        width_cap=0.13,
    )
    roda_w = float(roda.bounding_box.extents[0])
    wheel_x = max(0.42 - roda_w / 2.0, 0.28)
    rep["stages"]["6_roda_mestre"] = {
        **stats(roda),
        "r_target": WHEEL_R,
        "largura": round(roda_w, 4),
        "x_instancia": round(wheel_x, 4),
        "time_s": round(time.time() - t6, 2),
    }
    print("   6_roda_mestre:", rep["stages"]["6_roda_mestre"], flush=True)

    # ── 7. decimações + exports ──
    print("== [7] decimação + GLBs ==", flush=True)
    out_dir = os.path.join(CAR_DIR, "c7_kit")
    os.makedirs(out_dir, exist_ok=True)
    casca_d = decimate(casca, 160_000)
    tub_d = decimate(tub, 100_000)
    roda_d = decimate(roda, 30_000)

    # Cria versão espelhada em X da roda para o lado oposto (calota sempre voltada para fora!)
    roda_mir = roda_d.copy()
    roda_mir.vertices[:, 0] *= -1.0
    roda_mir.faces = roda_mir.faces[:, ::-1].copy()
    trimesh.repair.fix_normals(roda_mir)

    rodas_list = []
    for sx in (1.0, -1.0):
        base_w = roda_d if sx > 0 else roda_mir
        for z in (AXLE_FRONT_Z, AXLE_REAR_Z):
            inst = base_w.copy()
            inst.apply_translation([sx * wheel_x, WHEEL_Y, z])
            rodas_list.append(inst)
    rodas4 = trimesh.util.concatenate(rodas_list)

    kit = trimesh.util.concatenate([casca_d, tub_d, rodas4])
    interna = trimesh.util.concatenate([tub_d, rodas4])

    big = trimesh.creation.box(extents=[4.0, 4.0, 4.0])
    big.apply_translation([2.0 + 0.02, 0.0, 0.0])  # remove x > +0.02 (metade +x)
    man_casca_d, _ = repair_to_man(casca_d)
    casca_corte = from_man(man_casca_d - to_man(big))
    kit_corte = trimesh.util.concatenate([casca_corte, tub_d, rodas4])

    glbs = {}
    export_glb(kit, "carro_csg__kit.glb", glbs)
    export_glb(casca_d, "carro_csg__casca.glb", glbs)
    export_glb(interna, "carro_csg__interna.glb", glbs)
    export_glb(kit_corte, "carro_csg__kit_corte.glb", glbs)

    casca_d.export(os.path.join(out_dir, "casca.obj"))
    tub_d.export(os.path.join(out_dir, "banheira.obj"))
    roda_d.export(os.path.join(out_dir, "roda_mestre.obj"))
    kit.export(os.path.join(out_dir, "kit_completo.obj"))

    job_json = os.path.join(CAR_DIR, "c7_roda_mestre_job.json")
    if os.path.isfile(job_json):
        with open(job_json) as f:
            rep["stages"]["6_roda_mestre"]["gpu_job"] = json.load(f)

    rep["stages"]["7_glbs"] = glbs
    rep["medidas_foto"] = {
        "eixo_dianteiro_z": AXLE_FRONT_Z,
        "eixo_traseiro_z": -0.734,
        "raio_roda": WHEEL_R,
        "bitrena_x": WHEEL_X,
        "beltline_y": BELTLINE_Y,
        "fonte": "máscaras da foto lado (fox/no-windows), detecção de arcos",
    }
    rep["total_time_s"] = round(time.time() - T0, 2)
    rep["ts_end"] = t()
    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print("KIT_CSG_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
