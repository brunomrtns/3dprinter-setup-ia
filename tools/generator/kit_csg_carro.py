#!/usr/bin/env python3
"""Kit de Montagem CSG (C7-A, 2026-11-18) — carroceria oca + janelas booleanas
2D→3D + banheira interna + roda mestre instanciada 4x.

Spec: docs/knowledge/modelagem-hard-surface-e-veiculos.md (Opção 1 / Módulo 2A-2C).
Entradas (malhas e máscaras que JÁ EXISTEM do C6):
  - carroceria: ~/printer3d-work/carro/hunyuan_mv_triposf512_posproc/mesh_posproc.obj
    (die-cast fechado, frente/traseira fiéis) → deskew + blueprint + simetria
    (refino_automotivo) → casca oca (manifold3d.offset -wall) → recortes;
  - banheira: ~/printer3d-work/carro/nowin_triposf512_posproc/mesh_posproc.obj
    (cabine interna completa) → mesmas transformações → ∩ caixa do habitáculo;
  - máscaras de vidro: no_windows_rgba/<vista>_{solid,open}.png (janela =
    solid − open, fotos do dono em Downloads/fox/no-windows, prep C6);
  - roda mestre: ~/printer3d-work/carro/c7_roda_mestre/mesh.obj (TripoSG seed 42
    no close 1024px da roda na foto lado) → regularização cilíndrica → 4 instâncias.

Mapeamento foto→3D (medido, ver evidence/rtx3060-12gb/carro-csg/):
  - foto lado: flip_u (frente do carro à esquerda) e flip_v padrão, decididos por
    IoU de silhueta + detecção dos arcos das rodas (eixo diant. a 0.813 e tras. a
    0.133 do comprimento desde a traseira — foto = verdade);
  - fotos frente/traseira: v→y padrão; u→x (aprox. simétrico).

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
import trimesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refino_automotivo as ra  # noqa: E402

from scipy.ndimage import binary_closing, binary_opening, gaussian_filter  # noqa: E402
from PIL import Image  # noqa: E402

CAR_DIR = os.path.expanduser("~/printer3d-work/carro")
MODELS_DIR = os.path.expanduser("~/printer3d-work/modelos3d-site/models")
RGBA = os.path.join(CAR_DIR, "no_windows_rgba")

# medidos da foto lado (2026-11-18, ver orient3/probe): posições dos eixos
AXLE_FRONT_Z = 0.626  # 0.813 do comprimento desde a traseira, blueprint z∈[-1,1]
AXLE_REAR_Z = -0.734  # 0.133 desde a traseira
WHEEL_R = 0.173  # ⌀/comprimento 0.174 medido na foto (≈34,8mm na escala 200mm)
WHEEL_X = 0.336  # bitrena do mesh cru (|x|≈0.40 de ±0.5475) → blueprint ±0.46
WHEEL_Y = -0.401 + WHEEL_R  # assenta no chão (ymin = -0.401 no blueprint)
ARCH_R = WHEEL_R * 1.12  # folga do arco (~2mm na escala 200mm)
BELTLINE_Y = -0.338  # base das janelas laterais (máscara lado → 3D)
WIN_Z = (-0.828, 0.707)  # faixa z das janelas laterais (máscara lado → 3D)


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


def from_man(man):
    out = man.to_mesh()
    return trimesh.Trimesh(
        vertices=np.asarray(out.vert_properties[:, :3], dtype=np.float64),
        faces=np.asarray(out.tri_verts, dtype=np.int64),
        process=False,
    )


def erode_core(body: trimesh.Trimesh, wall: float) -> trimesh.Trimesh:
    """Núcleo erodido p/ casca oca SEM manifold3d.offset (removido da API 3.5.5):
    ray-fill open3d ao longo de Z (paridade de cruzamentos) → erosão morfológica
    (distância à superfície >= wall) → união CSG de cubos RLE no manifold3d
    (watertight por construção). Partes < 2×wall ficam sólidas no kit."""
    import open3d as o3d

    pitch = wall / 4.0  # 4 voxels de parede
    lo = body.bounds[0] - 2 * pitch
    hi = body.bounds[1] + 2 * pitch
    n = np.ceil((hi - lo) / pitch).astype(int) + 1
    nx, ny, nz = int(n[0]), int(n[1]), int(n[2])
    fill = np.zeros((nx, ny, nz), dtype=bool)

    scene = o3d.t.geometry.RaycastingScene()
    scene.add_triangles(
        o3d.core.Tensor(np.asarray(body.vertices, dtype=np.float32)),
        o3d.core.Tensor(np.asarray(body.faces, dtype=np.uint32)),
    )
    inf = o3d.core.Tensor(float("inf"))
    xs = lo[0] + np.arange(nx) * pitch
    ys = lo[1] + np.arange(ny) * pitch
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    ox, oy = gx.ravel(), gy.ravel()
    oz = np.full_like(ox, lo[2] - 1.0)
    dir_np = np.broadcast_to(np.array([0, 0, 1], np.float32), (len(ox), 3)).copy()
    origins = np.column_stack([ox, oy, oz]).astype(np.float32)
    k = np.zeros(len(ox), dtype=bool)      # raio terminado
    count = np.zeros(len(ox), dtype=int)   # nº de superfícies cruzadas
    MAX_SEG = 24
    for _ in range(MAX_SEG):
        alive = ~k
        if not alive.any():
            break
        rays = np.hstack([origins[alive], dir_np[alive]]).astype(np.float32)
        res = scene.cast_rays(o3d.core.Tensor(rays))
        th = res["t_hit"].numpy()
        hit = np.isfinite(th)
        idx = np.nonzero(alive)[0]
        hidx = idx[hit]
        count[hidx] += 1
        seg_o = origins[hidx]
        seg_t = th[hit]
        # origem além do hit para a próxima iteração
        origins[hidx, 2] = seg_o[:, 2] + seg_t + 1e-4
        # preenche o segmento [entrada→saída]: só é conhecido no cruzamento PAR
        # (a origem já pulou para logo após a entrada; t vai até a saída)
        inside = (count[hidx] % 2) == 0
        z0 = np.floor((seg_o[inside, 2] - lo[2]) / pitch).astype(int)
        z1 = np.ceil((seg_o[inside, 2] + seg_t[inside] - lo[2]) / pitch).astype(int)
        ix = np.round((seg_o[inside, 0] - lo[0]) / pitch).astype(int)
        iy = np.round((seg_o[inside, 1] - lo[1]) / pitch).astype(int)
        for a, b, i, j in zip(z0, z1, ix, iy):
            if b > a and 0 <= i < nx and 0 <= j < ny:
                fill[i, j, max(a, 0) : min(b, nz)] = True
        # raios sem hit terminam
        done = idx[~hit]
        k[done] = True

    from scipy.ndimage import binary_closing, distance_transform_edt

    dist = distance_transform_edt(fill, sampling=(pitch,) * 3)
    core_vox = binary_closing(fill & (dist >= wall), structure=np.ones((3, 3, 3)))
    if not core_vox.any():
        raise RuntimeError("erode_core: núcleo vazio")

    # núcleo = união CSG de cubos RLE (runs em z) no manifold3d — watertight por
    # construção (sem marching cubes, cujo output non-manifold quebrava a
    # subtração — medido nas 1ªs rodadas, ver report.json)
    from manifold3d import Manifold, OpType

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
                pos = (lo[0] + i * pitch, lo[1] + j * pitch, lo[2] + s * pitch)
                cubes.append(Manifold.cube(size=size).translate(pos))
    level = cubes
    while len(level) > 1:
        level = [
            Manifold.batch_boolean(level[i : i + 256], OpType.Add)
            for i in range(0, len(level), 256)
        ]
    return from_man(level[0])


def stats(m) -> dict:
    return {
        "verts": int(len(m.vertices)),
        "faces": int(len(m.faces)),
        "watertight": bool(m.is_watertight),
        "components": int(len(m.split(only_watertight=False))),
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


def mask_prism(mask: np.ndarray, u_to_a, v_to_b, depth: tuple[float, float],
               axis: int) -> trimesh.Trimesh:
    """Extruda a máscara 2D em prisma ao longo de `axis` (0=x,1=y,2=z), por blocos
    RLE (bordas em degrau de 1px ≈ 0,4mm na escala 200mm — determinístico, sem
    dependência de earcut/shapely). u_to_a/v_to_b: pixel → eixo (a,b) ≠ axis."""
    H, W = mask.shape
    smooth = gaussian_filter(mask.astype(np.float32), 2.0) > 0.5
    a, b = sorted({0, 1, 2} - {axis})
    boxes = []
    for r in range(H):
        row = smooth[r]
        if not row.any():
            continue
        d = np.diff(np.concatenate([[0], row.astype(int), [0]]))
        starts, ends = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
        ya, yb = sorted([v_to_b(r), v_to_b(min(r + 1, H - 1))])
        for s, e in zip(starts, ends):
            xa, xb = sorted([u_to_a(s), u_to_a(e - 1)])
            ext = np.zeros(3)
            ext[a] = xb - xa + 1e-4
            ext[b] = yb - ya + 1e-4
            ext[axis] = depth[1] - depth[0]
            box = trimesh.creation.box(extents=ext)
            c = np.zeros(3)
            c[a] = xa
            c[b] = ya
            c[axis] = depth[0]
            box.apply_translation(c)
            boxes.append(box)
    if not boxes:
        raise RuntimeError("máscara de janela vazia após suavização")
    return trimesh.util.concatenate(boxes)


def regularize_wheel(mesh_path: str, r_target: float, width_cap: float) -> trimesh.Trimesh:
    """Roda mestre: maior componente → eixo por PCA → alinhar a X → escala radial
    → encamisar em cilindro matemático (remove rebarbas fora do pneu)."""
    import pymeshlab

    w = trimesh.load(mesh_path, force="mesh", process=False)
    comps = sorted(w.split(only_watertight=False), key=lambda c: len(c.faces), reverse=True)
    # seleção por assinatura de roda (2 eixos ~iguais + 1 fino), não por tamanho:
    # no close da foto lado o maior componente pode ser a lataria ao redor
    wheel = None
    for c in comps[:6]:
        e = np.sort(c.bounding_box.extents)
        if len(c.faces) >= 20_000 and e[2] / e[1] <= 1.15 and e[1] / e[0] >= 2.2:
            wheel = c
            break
    if wheel is None:
        wheel = comps[0]
    w = wheel
    if len(w.faces) > 250_000:
        ms = pymeshlab.MeshSet()
        ms.add_mesh(pymeshlab.Mesh(w.vertices, w.faces))
        ms.meshing_decimation_quadric_edge_collapse(targetfacenum=250_000)
        cur = ms.current_mesh()
        w = trimesh.Trimesh(vertices=cur.vertex_matrix(), faces=cur.face_matrix(), process=False)
    w.vertices -= w.centroid
    cov = (w.vertices.T @ w.vertices) / len(w.vertices)
    evals, evecs = np.linalg.eigh(cov)
    axis_vec = evecs[:, np.argmin(evals)]  # menor variância = eixo da roda
    # rotaciona axis_vec → X
    v = axis_vec / np.linalg.norm(axis_vec)
    x = np.array([1.0, 0.0, 0.0])
    if np.allclose(v, x, atol=1e-6) or np.allclose(v, -x, atol=1e-6):
        R = np.eye(3)
    else:
        u_ = np.cross(v, x)
        u_ /= np.linalg.norm(u_)
        ang = float(np.arccos(np.clip(np.dot(v, x), -1, 1)))
        R = trimesh.transformations.rotation_matrix(ang, u_)
    w.apply_transform(R)
    w.vertices -= w.centroid
    radial = np.hypot(w.vertices[:, 1], w.vertices[:, 2])
    scale = r_target / float(np.percentile(radial, 99))
    w.apply_scale(scale)
    width = float(w.bounding_box.extents[0])
    if width > width_cap:
        w.apply_scale([width_cap / width, 1.0, 1.0])
        width = width_cap
    clad = trimesh.creation.cylinder(radius=r_target * 1.03, height=width * 1.3, sections=96)
    clad.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 0, 1]))  # eixo Y → X
    man = to_man(w) ^ to_man(clad)  # interseção encamisa o pneu
    out = from_man(man)
    out = trimesh.Trimesh(vertices=out.vertices, faces=out.faces, process=True)
    trimesh.repair.fix_normals(out)
    return out


def decimate(m, target: int) -> trimesh.Trimesh:
    import pymeshlab

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
    meta[name] = {"verts": int(len(m.vertices)), "faces": int(len(m.faces)),
                  "watertight": bool(m.is_watertight)}
    print(f"[OK] {name}: {meta[name]}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--wall-mm", type=float, default=3.0)
    args = ap.parse_args()
    T0 = time.time()
    wall = args.wall_mm / 100.0 * (2.0 / 2.0)  # 3mm na escala 200mm (unidade = 100mm)

    rep = {"ts_start": t(), "wall_mm": args.wall_mm, "stages": {}}

    # ── 1. carroceria: die-cast fechado → deskew + blueprint + simetria (C6) ──
    print("== [1] carroceria hunyuan_mv_sf512 → blueprint + simetria ==", flush=True)
    body = trimesh.load(
        os.path.join(CAR_DIR, "hunyuan_mv_triposf512_posproc", "mesh_posproc.obj"),
        force="mesh", process=False,
    )
    body = ra.deskew_longitudinal(body)
    body = ra.apply_fox_blueprint(body, target_length_norm=2.0)
    body = ra.symmetrize_bilateral(body, best_side="neg_x",
                                   preserve_driver_wheel_only=False, preserve_wipers=True)
    rep["stages"]["1_carroceria"] = stats(body)

    # ── 2. casca oca (voxel erosion — manifold3d 3.5.5 sem .offset) ──
    print("== [2] casca oca (parede %.2fmm, voxel shell) ==" % args.wall_mm, flush=True)
    t2 = time.time()
    man_body = to_man(body)
    inner = erode_core(body, wall)
    casca_man = man_body - to_man(inner)
    rep["stages"]["2_casca_oca"] = {**stats(from_man(casca_man)),
                                    "metodo": "rayfill+erosao+marching_cubes",
                                    "time_s": round(time.time() - t2, 2)}

    # ── 3. vãos de vidro por booleana 2D→3D ──
    print("== [3] corte booleano das janelas (máscaras 2D→3D) ==", flush=True)
    t3 = time.time()

    def lado_map():
        win, meta = window_mask("lado")
        u0, u1, v0, v1 = meta["solid_bbox"]
        zmin, zmax, ymin, ymax = -1.0, 1.0, -0.401, 0.401

        def u_to_z(u):  # flip_u: frente à esquerda
            return zmax - (u - u0) / (u1 - u0) * (zmax - zmin)

        def v_to_y(v):  # flip_v: topo da foto = topo do carro
            return ymax - (v - v0) / (v1 - v0) * (ymax - ymin)

        return win, meta, u_to_z, v_to_y

    win, meta_lado, u_to_z, v_to_y = lado_map()
    prism_side = mask_prism(win, u_to_z, v_to_y, depth=(-2.0, 2.0), axis=0)
    casca_man = casca_man - to_man(prism_side)

    for name, depth in (("frente", (0.65, 1.2)), ("traseira", (-1.2, -0.78))):
        win, meta = window_mask(name)
        u0, u1, v0, v1 = meta["solid_bbox"]
        xmin, xmax, ymin, ymax = -0.46, 0.46, -0.401, 0.401
        u_to_x = lambda u: xmin + (u - u0) / (u1 - u0) * (xmax - xmin)  # noqa: E731
        v_to_y2 = lambda v: ymax - (v - v0) / (v1 - v0) * (ymax - ymin)  # noqa: E731
        prism = mask_prism(win, u_to_x, v_to_y2, depth=depth, axis=2)
        casca_man = casca_man - to_man(prism)

    # ── 4. caixas de roda (4 cilindros no eixo X) ──
    print("== [4] caixas de roda (cilindros booleanos) ==", flush=True)
    for z in (AXLE_FRONT_Z, AXLE_REAR_Z):
        cyl = trimesh.creation.cylinder(radius=ARCH_R, height=2.4, sections=96)
        cyl.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
        cyl.apply_translation([0.0, WHEEL_Y, z])
        casca_man = casca_man - to_man(cyl)
    casca = from_man(casca_man)
    casca = trimesh.Trimesh(vertices=casca.vertices, faces=casca.faces, process=True)
    trimesh.repair.fix_normals(casca)
    rep["stages"]["3_janelas_e_arcos"] = {**stats(casca), "time_s": round(time.time() - t3, 2)}

    # ── 5. banheira interna (nowin: cabine completa) ──
    print("== [5] banheira interna (∩ caixa do habitáculo) ==", flush=True)
    t5 = time.time()
    tub = trimesh.load(
        os.path.join(CAR_DIR, "nowin_triposf512_posproc", "mesh_posproc.obj"),
        force="mesh", process=False,
    )
    tub = ra.deskew_longitudinal(tub)
    tub = ra.apply_fox_blueprint(tub, target_length_norm=2.0)
    tub = ra.symmetrize_bilateral(tub, best_side="pos_x",
                                  preserve_driver_wheel_only=True, preserve_wipers=False)
    cabin = trimesh.creation.box(extents=[0.92, 0.72, WIN_Z[1] - WIN_Z[0] + 0.12])
    cabin.apply_translation([0.0, (-0.36 + 0.30) / 2, (WIN_Z[0] + WIN_Z[1]) / 2])
    tub_man = to_man(tub) ^ to_man(cabin)
    tub = from_man(tub_man)
    tub = trimesh.Trimesh(vertices=tub.vertices, faces=tub.faces, process=True)
    trimesh.repair.fix_normals(tub)
    rep["stages"]["5_banheira"] = {**stats(tub), "time_s": round(time.time() - t5, 2)}

    # ── 6. roda mestre + 4 instâncias ──
    print("== [6] roda mestre (regularização cilíndrica) + 4 instâncias ==", flush=True)
    t6 = time.time()
    roda = regularize_wheel(os.path.join(CAR_DIR, "c7_roda_mestre", "mesh.obj"),
                            r_target=WHEEL_R, width_cap=0.14)
    roda_w = float(roda.bounding_box.extents[0])
    wheel_x = max(0.42 - roda_w / 2.0, 0.25)  # face externa ~rasa com a carroceria
    rep["stages"]["6_roda_mestre"] = {**stats(roda), "r_target": WHEEL_R,
                                      "largura": round(roda_w, 4), "x_instancia": round(wheel_x, 4),
                                      "time_s": round(time.time() - t6, 2)}

    # ── 7. decimações + exports ──
    print("== [7] decimação + GLBs ==", flush=True)
    out_dir = os.path.join(CAR_DIR, "c7_kit")
    os.makedirs(out_dir, exist_ok=True)
    casca_d = decimate(casca, 160_000)
    tub_d = decimate(tub, 100_000)
    roda_d = decimate(roda, 30_000)
    rodas4 = trimesh.util.concatenate(
        [roda_d.copy().apply_translation([sx * wheel_x, WHEEL_Y, z])
         for sx in (1.0, -1.0) for z in (AXLE_FRONT_Z, AXLE_REAR_Z)]
    )

    kit = trimesh.util.concatenate([casca_d, tub_d, rodas4])
    interna = trimesh.util.concatenate([tub_d, rodas4])

    big = trimesh.creation.box(extents=[4.0, 4.0, 4.0])
    big.apply_translation([2.0 + 0.02, 0.0, 0.0])  # remove x > +0.02 (metade +x)
    casca_corte = from_man(to_man(casca_d) - to_man(big))
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

    # telemetria do job GPU da roda mestre (se existir)
    job_json = os.path.join(CAR_DIR, "c7_roda_mestre_job.json")
    if os.path.isfile(job_json):
        with open(job_json) as f:
            rep["stages"]["6_roda_mestre"]["gpu_job"] = json.load(f)

    rep["stages"]["7_glbs"] = glbs
    rep["medidas_foto"] = {
        "eixo_dianteiro_z": AXLE_FRONT_Z, "eixo_traseiro_z": AXLE_REAR_Z,
        "raio_roda": WHEEL_R, "bitrena_x": WHEEL_X, "beltline_y": BELTLINE_Y,
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
