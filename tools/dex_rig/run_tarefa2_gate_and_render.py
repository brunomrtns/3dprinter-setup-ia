#!/usr/bin/env python3
"""
TAREFA 2B — Gate Automático de Simetria + Render A/B (TripoSG vs Hunyuan3D-2mv).
Roda no venv ~/.venvs/hunyuan (trimesh + numpy + PIL) + bpy via ~/.venvs/unirig para render ortogonal.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw

REPO = Path("/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia")
EV_DIR = REPO / "evidence/dex_rig"
OBJ_A = REPO / "work/dex_rig/cand_a_triposg/mesh.obj"
OBJ_B = REPO / "work/dex_rig/cand_b_hy2mv/mesh.obj"


def eval_symmetry_and_topology(obj_path: Path, label: str) -> dict:
    mesh = trimesh.load(str(obj_path), force="mesh")
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(list(mesh.geometry.values()))

    # Componentes conectados
    comps = mesh.split(only_watertight=False)
    comps_sorted = sorted(comps, key=lambda c: len(c.faces), reverse=True)
    main_faces = len(comps_sorted[0].faces) if comps_sorted else 0
    total_faces = len(mesh.faces)
    main_ratio = main_faces / max(1, total_faces)

    # Tenta reparo basico de normais/buracos
    mesh_rep = mesh.copy()
    trimesh.repair.fix_normals(mesh_rep)
    trimesh.repair.fill_holes(mesh_rep)
    watertight_after_repair = bool(mesh_rep.is_watertight)

    # Mede mirror-distance L/R testando eixo X e eixo Z (caso o modelo venha rotacionado 90 deg)
    verts = np.asarray(mesh.vertices, dtype=np.float64)
    # Amostra ate 6000 vertices deterministicos (seed 42) para medicao rapida e precisa
    rng = np.random.default_rng(42)
    if len(verts) > 6000:
        idx = rng.choice(len(verts), size=6000, replace=False)
        sample = verts[idx]
    else:
        sample = verts

    vmin = sample.min(axis=0)
    vmax = sample.max(axis=0)
    bbox = vmax - vmin
    diag = float(np.linalg.norm(bbox))
    center = (vmin + vmax) * 0.5
    s_c = sample - center

    from scipy.spatial import cKDTree
    tree = cKDTree(s_c)

    best_axis = None
    best_mean = 1e9
    best_p95 = 1e9
    for axis_idx, axis_name in [(0, "X"), (2, "Z")]:
        mir = s_c.copy()
        mir[:, axis_idx] *= -1.0
        dists, _ = tree.query(mir, k=1)
        m_pct = float(dists.mean() / max(1e-6, diag) * 100.0)
        p95_pct = float(np.percentile(dists, 95) / max(1e-6, diag) * 100.0)
        if m_pct < best_mean:
            best_mean = m_pct
            best_p95 = p95_pct
            best_axis = axis_name

    return {
        "candidate": label,
        "obj_path": str(obj_path),
        "vertices": int(len(mesh.vertices)),
        "faces": int(total_faces),
        "bbox_extents": [round(float(x), 4) for x in bbox],
        "bbox_diag": round(diag, 4),
        "connected_components": int(len(comps)),
        "main_component_face_ratio": round(float(main_ratio), 4),
        "single_main_body_pass": bool(main_ratio >= 0.90),
        "watertight_raw": bool(mesh.is_watertight),
        "watertight_after_repair": watertight_after_repair,
        "mirror_symmetry_axis": best_axis,
        "mirror_distance_mean_pct_bbox": round(best_mean, 3),
        "mirror_distance_p95_pct_bbox": round(best_p95, 3),
        "symmetry_pass_lt_1pct": bool(best_mean < 1.0),
    }


def render_4views_wire_clay(obj_path: Path, out_png: Path, title: str) -> None:
    """Renderiza 4 vistas limpas (front, right, back, left) usando projecao ortografica shading Lambertian em numpy/PIL."""
    mesh = trimesh.load(str(obj_path), force="mesh")
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(list(mesh.geometry.values()))

    verts = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.int32)
    fnorm = np.asarray(mesh.face_normals, dtype=np.float32)
    # Centraliza e normaliza para caber em [-1, 1]
    vmin, vmax = verts.min(axis=0), verts.max(axis=0)
    center = (vmin + vmax) * 0.5
    scale = float(np.max(vmax - vmin)) * 0.58
    v = (verts - center) / max(1e-6, scale)

    # Identifica eixo vertical (maior extensao ou Y/Z)
    ext = vmax - vmin
    up_is_y = ext[1] >= ext[2]
    if not up_is_y:
        # Converte Z-up para Y-up
        v = np.stack([v[:, 0], v[:, 2], -v[:, 1]], axis=1)
        fnorm = np.stack([fnorm[:, 0], fnorm[:, 2], -fnorm[:, 1]], axis=1)

    sz = 384
    panel = Image.new("RGB", (sz * 4, sz + 36), (26, 28, 34))
    draw = ImageDraw.Draw(panel)
    draw.text((12, 10), title, fill=(245, 200, 110))

    angles = [("0 deg", 0.0), ("90 deg", np.pi * 0.5), ("180 deg", np.pi), ("270 deg", np.pi * 1.5)]
    light_dir = np.array([0.35, 0.55, 0.75], dtype=np.float32)
    light_dir /= np.linalg.norm(light_dir)

    for idx, (lbl, ang) in enumerate(angles):
        c, s = float(np.cos(ang)), float(np.sin(ang))
        rot = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float32)
        vr = v @ rot.T
        nr = fnorm @ rot.T
        # Amostra pontos de face para rasterizacao ultra-rapida com z-buffer por pixel
        fc = (vr[faces[:, 0]] + vr[faces[:, 1]] + vr[faces[:, 2]]) / 3.0
        # Backface culling + ordenacao painter (de tras para frente)
        vis = nr[:, 2] > -0.15
        fc_v = fc[vis]
        nr_v = nr[vis]
        order = np.argsort(fc_v[:, 2])
        fc_v = fc_v[order]
        nr_v = nr_v[order]

        px = np.clip(((fc_v[:, 0] * 0.5 + 0.5) * (sz - 1)).astype(np.int32), 0, sz - 1)
        py = np.clip(((-fc_v[:, 1] * 0.5 + 0.5) * (sz - 1)).astype(np.int32), 0, sz - 1)
        ndotl = np.clip(nr_v @ light_dir, 0.0, 1.0)
        shade = (45 + ndotl * 195).astype(np.uint8)

        buf = np.full((sz, sz, 3), 38, dtype=np.uint8)
        # Splat 2x2 para preencher superficie solida
        for dx in (0, 1):
            for dy in (0, 1):
                px2 = np.clip(px + dx, 0, sz - 1)
                py2 = np.clip(py + dy, 0, sz - 1)
                buf[py2, px2, 0] = np.clip(shade * 1.05, 0, 255).astype(np.uint8)
                buf[py2, px2, 1] = np.clip(shade * 0.88, 0, 255).astype(np.uint8)
                buf[py2, px2, 2] = np.clip(shade * 0.72, 0, 255).astype(np.uint8)

        im = Image.fromarray(buf, mode="RGB")
        panel.paste(im, (idx * sz, 36))
        draw.text((idx * sz + 8, 42), lbl, fill=(220, 220, 220))

    panel.save(out_png)


def main() -> None:
    EV_DIR.mkdir(parents=True, exist_ok=True)
    rep_a = eval_symmetry_and_topology(OBJ_A, "A_TripoSG_front")
    rep_b = eval_symmetry_and_topology(OBJ_B, "B_Hunyuan3D_2mv_4views")
    (EV_DIR / "simetria_a.json").write_text(json.dumps(rep_a, indent=2), encoding="utf-8")
    (EV_DIR / "simetria_b.json").write_text(json.dumps(rep_b, indent=2), encoding="utf-8")

    render_4views_wire_clay(OBJ_A, EV_DIR / "render_a_triposg.png",
                            f"A: TripoSG (front) | mirror={rep_a['mirror_distance_mean_pct_bbox']}% | faces={rep_a['faces']} | wt={rep_a['watertight_after_repair']}")
    render_4views_wire_clay(OBJ_B, EV_DIR / "render_b_hy2mv.png",
                            f"B: Hunyuan3D-2mv (4 views) | mirror={rep_b['mirror_distance_mean_pct_bbox']}% | faces={rep_b['faces']} | wt={rep_b['watertight_after_repair']}")

    # Junta sheet A/B lado a lado (empilhado verticalmente)
    im_a = Image.open(EV_DIR / "render_a_triposg.png")
    im_b = Image.open(EV_DIR / "render_b_hy2mv.png")
    sheet = Image.new("RGB", (max(im_a.width, im_b.width), im_a.height + im_b.height + 8), (16, 16, 20))
    sheet.paste(im_a, (0, 0))
    sheet.paste(im_b, (0, im_a.height + 8))
    sheet.save(EV_DIR / "ab_shapes_sheet.png")

    print("SIMETRIA_A:", json.dumps(rep_a))
    print("SIMETRIA_B:", json.dumps(rep_b))


if __name__ == "__main__":
    main()
