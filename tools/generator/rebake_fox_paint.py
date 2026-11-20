#!/usr/bin/env python3
"""ETAPA 1 — Rebake 2048 corrigido por projeção 4-vistas com oclusão Z-buffer,
máscara de cobertura, inpaint de bordas e preenchimento pela cor dominante da pintura.

Reaproveita EXATAMENTE uv.obj existente (sem regenerar malha nem UV). Seed 42.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import trimesh
from PIL import Image
from scipy.ndimage import binary_erosion, binary_fill_holes


def compute_fg_mask(rgb: np.ndarray, thresh: int = 247) -> np.ndarray:
    """Máscara binária do objeto sobre fundo branco (255,255,255)."""
    fg = (rgb < thresh).any(axis=-1)
    fg = binary_fill_holes(fg)
    return fg


def tight_bbox_2d(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return 0, 0, mask.shape[1] - 1, mask.shape[0] - 1
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def rasterize_uv_attributes(
    verts: np.ndarray,
    normals: np.ndarray,
    uvs: np.ndarray,
    faces: np.ndarray,
    size: int = 2048,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Rasteriza posição 3D e normal 3D no espaço UV (size x size) usando triângulos de uv.obj.

    Convenção glTF/OBJ: u in [0,1] -> col [0, size-1], v in [0,1] -> row = (1 - v) * (size - 1).
    """
    pos_map = np.zeros((size, size, 3), dtype=np.float32)
    nrm_map = np.zeros((size, size, 3), dtype=np.float32)
    tri_id_img = np.full((size, size), -1, dtype=np.int32)

    # Coordenadas pixel (x=col, y=row)
    px = uvs[:, 0] * (size - 1)
    py = (1.0 - uvs[:, 1]) * (size - 1)

    # Usa OpenCV fillConvexPoly em batches para preencher tri_id rápido? Não suporta int32 direto.
    # Em vez disso, rasterização baricêntrica vetorizada por chunks de triângulos em NumPy:
    p0x = px[faces[:, 0]]
    p0y = py[faces[:, 0]]
    p1x = px[faces[:, 1]]
    p1y = py[faces[:, 1]]
    p2x = px[faces[:, 2]]
    p2y = py[faces[:, 2]]

    xmin = np.clip(np.floor(np.minimum(np.minimum(p0x, p1x), p2x)).astype(np.int32), 0, size - 1)
    xmax = np.clip(np.ceil(np.maximum(np.maximum(p0x, p1x), p2x)).astype(np.int32), 0, size - 1)
    ymin = np.clip(np.floor(np.minimum(np.minimum(p0y, p1y), p2y)).astype(np.int32), 0, size - 1)
    ymax = np.clip(np.ceil(np.maximum(np.maximum(p0y, p1y), p2y)).astype(np.int32), 0, size - 1)

    # Agrupa por tamanho da bbox para rasterização rápida via PyTorch na GPU!
    device = "cuda" if torch.cuda.is_available() else "cpu"
    v_t = torch.from_numpy(verts.astype(np.float32)).to(device)
    n_t = torch.from_numpy(normals.astype(np.float32)).to(device)
    f_t = torch.from_numpy(faces.astype(np.int64)).to(device)
    px_t = torch.from_numpy(px.astype(np.float32)).to(device)
    py_t = torch.from_numpy(py.astype(np.float32)).to(device)

    pos_flat = torch.zeros((size * size, 3), dtype=torch.float32, device=device)
    nrm_flat = torch.zeros((size * size, 3), dtype=torch.float32, device=device)
    valid_flat = torch.zeros((size * size,), dtype=torch.bool, device=device)

    w_box = xmax - xmin + 1
    h_box = ymax - ymin + 1
    area_box = w_box * h_box

    # Processa triângulos em buckets de área (quase todos são <= 64 pixels)
    order = np.argsort(area_box)
    chunk_max_pixels = 4_000_000
    n_faces = len(faces)
    idx = 0
    while idx < n_faces:
        # Monta um batch com soma de area_box <= chunk_max_pixels
        start = idx
        acc = 0
        while idx < n_faces and (acc + int(area_box[order[idx]]) <= chunk_max_pixels or idx == start):
            acc += int(area_box[order[idx]])
            idx += 1
        batch_ids = order[start:idx]
        if len(batch_ids) == 0:
            break

        # Expande pixels (x, y) de cada bbox em CPU (vetorizado via np.repeat)
        bx0 = xmin[batch_ids]
        by0 = ymin[batch_ids]
        bw = w_box[batch_ids]
        bh = h_box[batch_ids]
        ba = area_box[batch_ids]

        total_px = int(ba.sum())
        if total_px == 0:
            continue

        # Índices locais 0..ba[i]-1 para cada triângulo
        tri_rep = np.repeat(batch_ids, ba)
        offsets = np.cumsum(ba) - ba
        local_idx = np.arange(total_px, dtype=np.int32) - np.repeat(offsets, ba)
        bw_rep = np.repeat(bw, ba)
        gx = np.repeat(bx0, ba) + (local_idx % bw_rep)
        gy = np.repeat(by0, ba) + (local_idx // bw_rep)

        tri_t = torch.from_numpy(tri_rep.astype(np.int64)).to(device)
        gx_t = torch.from_numpy(gx.astype(np.float32)).to(device)
        gy_t = torch.from_numpy(gy.astype(np.float32)).to(device)

        f0 = f_t[tri_t, 0]
        f1 = f_t[tri_t, 1]
        f2 = f_t[tri_t, 2]

        x0, y0 = px_t[f0], py_t[f0]
        x1, y1 = px_t[f1], py_t[f1]
        x2, y2 = px_t[f2], py_t[f2]

        denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        good = denom.abs() > 1e-8
        denom_safe = torch.where(good, denom, torch.ones_like(denom))
        w0 = ((y1 - y2) * (gx_t - x2) + (x2 - x1) * (gy_t - y2)) / denom_safe
        w1 = ((y2 - y0) * (gx_t - x2) + (x0 - x2) * (gy_t - y2)) / denom_safe
        w2 = 1.0 - w0 - w1

        eps = -1e-4
        inside = good & (w0 >= eps) & (w1 >= eps) & (w2 >= eps)
        if not inside.any():
            continue

        f0_i, f1_i, f2_i = f0[inside], f1[inside], f2[inside]
        w0_i = w0[inside].unsqueeze(-1)
        w1_i = w1[inside].unsqueeze(-1)
        w2_i = w2[inside].unsqueeze(-1)

        p_interp = w0_i * v_t[f0_i] + w1_i * v_t[f1_i] + w2_i * v_t[f2_i]
        n_interp = w0_i * n_t[f0_i] + w1_i * n_t[f1_i] + w2_i * n_t[f2_i]
        n_interp = n_interp / (n_interp.norm(dim=-1, keepdim=True).clamp(min=1e-8))

        lin = gy_t[inside].long() * size + gx_t[inside].long()
        pos_flat[lin] = p_interp
        nrm_flat[lin] = n_interp
        valid_flat[lin] = True

    pos_map = pos_flat.view(size, size, 3).cpu().numpy()
    nrm_map = nrm_flat.view(size, size, 3).cpu().numpy()
    valid_map = valid_flat.view(size, size).cpu().numpy()
    del pos_flat, nrm_flat, valid_flat, v_t, n_t, f_t, px_t, py_t
    if device == "cuda":
        torch.cuda.empty_cache()
    return pos_map, nrm_map, valid_map


def build_ortho_depth_buffer(
    verts: np.ndarray,
    faces: np.ndarray,
    u_coords: np.ndarray,
    v_coords: np.ndarray,
    depth_vals: np.ndarray,
    res: int = 1024,
) -> np.ndarray:
    """Constrói Z-buffer ortográfico (maior depth_vals = mais próximo da câmera)."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    px = np.clip(u_coords * (res - 1), 0, res - 1)
    py = np.clip(v_coords * (res - 1), 0, res - 1)

    p0x, p0y = px[faces[:, 0]], py[faces[:, 0]]
    p1x, p1y = px[faces[:, 1]], py[faces[:, 1]]
    p2x, p2y = px[faces[:, 2]], py[faces[:, 2]]

    xmin = np.clip(np.floor(np.minimum(np.minimum(p0x, p1x), p2x)).astype(np.int32), 0, res - 1)
    xmax = np.clip(np.ceil(np.maximum(np.maximum(p0x, p1x), p2x)).astype(np.int32), 0, res - 1)
    ymin = np.clip(np.floor(np.minimum(np.minimum(p0y, p1y), p2y)).astype(np.int32), 0, res - 1)
    ymax = np.clip(np.ceil(np.maximum(np.maximum(p0y, p1y), p2y)).astype(np.int32), 0, res - 1)

    w_box = xmax - xmin + 1
    h_box = ymax - ymin + 1
    area_box = w_box * h_box

    px_t = torch.from_numpy(px.astype(np.float32)).to(device)
    py_t = torch.from_numpy(py.astype(np.float32)).to(device)
    d_t = torch.from_numpy(depth_vals.astype(np.float32)).to(device)
    f_t = torch.from_numpy(faces.astype(np.int64)).to(device)

    zbuf = torch.full((res * res,), -1e9, dtype=torch.float32, device=device)

    order = np.argsort(area_box)
    chunk_max_pixels = 4_000_000
    n_faces = len(faces)
    idx = 0
    while idx < n_faces:
        start = idx
        acc = 0
        while idx < n_faces and (acc + int(area_box[order[idx]]) <= chunk_max_pixels or idx == start):
            acc += int(area_box[order[idx]])
            idx += 1
        batch_ids = order[start:idx]
        bx0, by0 = xmin[batch_ids], ymin[batch_ids]
        bw, ba = w_box[batch_ids], area_box[batch_ids]
        total_px = int(ba.sum())
        if total_px == 0:
            continue

        tri_rep = np.repeat(batch_ids, ba)
        offsets = np.cumsum(ba) - ba
        local_idx = np.arange(total_px, dtype=np.int32) - np.repeat(offsets, ba)
        bw_rep = np.repeat(bw, ba)
        gx = np.repeat(bx0, ba) + (local_idx % bw_rep)
        gy = np.repeat(by0, ba) + (local_idx // bw_rep)

        tri_t = torch.from_numpy(tri_rep.astype(np.int64)).to(device)
        gx_t = torch.from_numpy(gx.astype(np.float32)).to(device)
        gy_t = torch.from_numpy(gy.astype(np.float32)).to(device)

        f0, f1, f2 = f_t[tri_t, 0], f_t[tri_t, 1], f_t[tri_t, 2]
        x0, y0 = px_t[f0], py_t[f0]
        x1, y1 = px_t[f1], py_t[f1]
        x2, y2 = px_t[f2], py_t[f2]

        denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        good = denom.abs() > 1e-8
        denom_safe = torch.where(good, denom, torch.ones_like(denom))
        w0 = ((y1 - y2) * (gx_t - x2) + (x2 - x1) * (gy_t - y2)) / denom_safe
        w1 = ((y2 - y0) * (gx_t - x2) + (x0 - x2) * (gy_t - y2)) / denom_safe
        w2 = 1.0 - w0 - w1

        inside = good & (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
        if not inside.any():
            continue

        z_interp = w0[inside] * d_t[f0[inside]] + w1[inside] * d_t[f1[inside]] + w2[inside] * d_t[f2[inside]]
        lin = gy_t[inside].long() * res + gx_t[inside].long()
        zbuf.scatter_reduce_(0, lin, z_interp, reduce="amax", include_self=True)

    out = zbuf.view(res, res).cpu().numpy()
    del zbuf, px_t, py_t, d_t, f_t
    if device == "cuda":
        torch.cuda.empty_cache()
    return out


def rebake_mesh(
    uv_obj_path: Path,
    views: dict[str, Path],
    out_png_path: Path,
    size: int = 2048,
    cos_thresh: float = 0.35,
    depth_eps: float = 0.025,
    erode_px: int = 2,
    inpaint_radius: int = 6,
) -> dict:
    """Executa o rebake 2048 corrigido com oclusão, máscara de cobertura e fill dominante."""
    t0 = time.time()
    mesh = trimesh.load(str(uv_obj_path), force="mesh", process=False)
    verts = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    uvs = np.asarray(mesh.visual.uv, dtype=np.float32)
    normals = np.asarray(mesh.vertex_normals, dtype=np.float32)

    bmin = verts.min(axis=0)
    bmax = verts.max(axis=0)
    bext = bmax - bmin

    # 1. Rasteriza posição 3D e normal 3D por texel no atlas 2048x2048
    pos_map, nrm_map, uv_valid = rasterize_uv_attributes(verts, normals, uvs, faces, size=size)

    # 2. Configura as 4 vistas ortogonais (+Z=front, -Z=back, -X=left, +X=right; +Y=up)
    # Em cada vista: (view_dir, u_fn(pos), v_fn(pos), depth_fn(pos))
    # Auto-detecta flip horizontal da vista lateral (left) comparando silhueta 2D da malha vs foto!
    def project_view_coords(p: np.ndarray, vname: str, flip_u: bool = False):
        if vname == "front":
            # Olhando de +Z para -Z: esquerda da imagem é +X ou -X? Câmera em +Z olhando -Z -> direita da tela = -X (ou +X).
            # Carro é simétrico em X; X normalizado [-bmin, bmax]
            u = (p[..., 0] - bmin[0]) / bext[0]
            if flip_u:
                u = 1.0 - u
            v = 1.0 - (p[..., 1] - bmin[1]) / bext[1]
            d = p[..., 2]
        elif vname == "back":
            u = 1.0 - (p[..., 0] - bmin[0]) / bext[0]
            if flip_u:
                u = 1.0 - u
            v = 1.0 - (p[..., 1] - bmin[1]) / bext[1]
            d = -p[..., 2]
        elif vname == "left":
            # Câmera em -X olhando +X (perfil esquerdo do carro): +Z (frente) fica à esquerda ou direita?
            u = (p[..., 2] - bmin[2]) / bext[2]
            if flip_u:
                u = 1.0 - u
            v = 1.0 - (p[..., 1] - bmin[1]) / bext[1]
            d = -p[..., 0]
        elif vname == "right":
            u = 1.0 - (p[..., 2] - bmin[2]) / bext[2]
            if flip_u:
                u = 1.0 - u
            v = 1.0 - (p[..., 1] - bmin[1]) / bext[1]
            d = p[..., 0]
        else:
            raise ValueError(vname)
        return u, v, d

    view_dirs = {
        "front": np.array([0.0, 0.0, 1.0], dtype=np.float32),
        "back": np.array([0.0, 0.0, -1.0], dtype=np.float32),
        "left": np.array([-1.0, 0.0, 0.0], dtype=np.float32),
        "right": np.array([1.0, 0.0, 0.0], dtype=np.float32),
    }

    zres = 1024
    accum_rgb = np.zeros((size, size, 3), dtype=np.float32)
    accum_w = np.zeros((size, size), dtype=np.float32)
    view_stats = {}

    for vname, img_path in views.items():
        rgb_img = np.asarray(Image.open(img_path).convert("RGB"), dtype=np.uint8)
        fg_raw = compute_fg_mask(rgb_img, thresh=247)
        x0, y0, x1, y1 = tight_bbox_2d(fg_raw)
        crop_rgb = rgb_img[y0 : y1 + 1, x0 : x1 + 1]
        crop_fg = fg_raw[y0 : y1 + 1, x0 : x1 + 1]
        if erode_px > 0:
            crop_fg_safe = binary_erosion(crop_fg, iterations=erode_px)
        else:
            crop_fg_safe = crop_fg

        # Auto-detecta orientação horizontal da vista lateral (left/right) por IoU de silhueta
        best_flip = False
        best_iou = -1.0
        flip_candidates = [False, True] if vname in ("left", "right") else [False]
        zbuf_best = None
        for fl in flip_candidates:
            uv_v, vv_v, dv_v = project_view_coords(verts, vname, flip_u=fl)
            zb = build_ortho_depth_buffer(verts, faces, uv_v, vv_v, dv_v, res=zres)
            mesh_sil = zb > -1e8
            # Redimensiona crop_fg para (zres, zres) para medir IoU exato
            photo_sil = cv2.resize(crop_fg.astype(np.uint8), (zres, zres), interpolation=cv2.INTER_NEAREST) > 0
            inter = np.logical_and(mesh_sil, photo_sil).sum()
            union = np.logical_or(mesh_sil, photo_sil).sum() + 1e-6
            iou = float(inter / union)
            if iou > best_iou:
                best_iou = iou
                best_flip = fl
                zbuf_best = zb

        # Projeta cada texel válido do UV nessa vista
        vdir = view_dirs[vname]
        ndot = (
            nrm_map[..., 0] * vdir[0]
            + nrm_map[..., 1] * vdir[1]
            + nrm_map[..., 2] * vdir[2]
        )
        u_t, v_t, d_t = project_view_coords(pos_map, vname, flip_u=best_flip)

        # Consulta Z-buffer (oclusão exata)
        zx = np.clip(np.round(u_t * (zres - 1)).astype(np.int32), 0, zres - 1)
        zy = np.clip(np.round(v_t * (zres - 1)).astype(np.int32), 0, zres - 1)
        z_front = zbuf_best[zy, zx]

        # Consulta imagem recortada (dentro do foreground erodido)
        ch, cw = crop_rgb.shape[:2]
        ix = np.clip(np.round(u_t * (cw - 1)).astype(np.int32), 0, cw - 1)
        iy = np.clip(np.round(v_t * (ch - 1)).astype(np.int32), 0, ch - 1)
        in_fg = crop_fg_safe[iy, ix]

        vis = (
            uv_valid
            & (ndot > cos_thresh)
            & (z_front > -1e8)
            & ((z_front - d_t) <= depth_eps)
            & in_fg
        )

        # Peso suave por cosseno elevado à 4ª potência para favorecer a vista mais frontal sem costuras duras
        w = np.where(vis, np.power(np.clip(ndot, 0.0, 1.0), 4.0), 0.0).astype(np.float32)
        sampled = crop_rgb[iy, ix].astype(np.float32)

        accum_rgb += sampled * w[..., None]
        accum_w += w

        view_stats[vname] = {
            "flip_u": best_flip,
            "silhouette_iou": round(best_iou, 4),
            "texels_vis": int(vis.sum()),
        }

    # 3. Máscara de cobertura (texels que receberam cor válida de pelo menos 1 vista)
    coverage_mask = uv_valid & (accum_w > 1e-6)
    bake = np.zeros((size, size, 3), dtype=np.uint8)
    valid_rgb = (accum_rgb[coverage_mask] / accum_w[coverage_mask, None]).clip(0, 255).astype(np.uint8)
    bake[coverage_mask] = valid_rgb

    # 4. Cor dominante da pintura = mediana dos texels válidos CLAROS da lataria (branco puro >210)
    valid_lum = (
        0.299 * valid_rgb[:, 0].astype(np.float32)
        + 0.587 * valid_rgb[:, 1].astype(np.float32)
        + 0.114 * valid_rgb[:, 2].astype(np.float32)
    )
    bright = valid_rgb[valid_lum > 210.0]
    if len(bright) > 100:
        dom_color = np.median(bright, axis=0).round().astype(np.uint8)
    else:
        dom_color = np.array([232, 232, 232], dtype=np.uint8)

    # 5. Bordas da máscara: dilatação/inpaint a partir de vizinhos válidos (raio pequeno)
    #    antes do fill plano com a cor dominante da pintura (evita costura dura e bleed preto!)
    uncovered_uv = uv_valid & (~coverage_mask)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * inpaint_radius + 1, 2 * inpaint_radius + 1))
    near_border = (cv2.dilate(coverage_mask.astype(np.uint8), kernel) > 0) & (~coverage_mask)

    # Preenche primeiro tudo fora de coverage_mask com dom_color (nunca preto/zero!)
    bake[~coverage_mask] = dom_color

    # Aplica Telea inpaint apenas na faixa de borda (near_border) usando exclusivamente vizinhos válidos
    # Para que o inpaint puxe só de coverage_mask (e não de dom_color), fazemos inpaint sobre uma cópia onde
    # apenas near_border é inpainted; fora de coverage_mask | near_border já está dom_color!
    if near_border.any():
        inpaint_mask = near_border.astype(np.uint8) * 255
        bake = cv2.inpaint(bake, inpaint_mask, inpaintRadius=max(3, inpaint_radius // 2), flags=cv2.INPAINT_TELEA)

    # Dilatação extra de 4px fora das ilhas UV para evitar bleeding de mipmap nas costuras UV
    # (como ~uv_valid já está preenchido com dom_color e não preto, já não há bleed preto!)

    out_png_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(bake, mode="RGB").save(out_png_path)

    uv_total = int(uv_valid.sum())
    cov_total = int(coverage_mask.sum())
    cov_pct = round(100.0 * cov_total / max(1, uv_total), 2)
    fill_pct = round(100.0 * int(uncovered_uv.sum()) / max(1, uv_total), 2)

    return {
        "bake_png": str(out_png_path),
        "size": size,
        "uv_texels": uv_total,
        "coverage_texels": cov_total,
        "coverage_pct": cov_pct,
        "filled_dom_pct": fill_pct,
        "dominant_paint_rgb": [int(c) for c in dom_color],
        "cos_thresh": cos_thresh,
        "depth_eps": depth_eps,
        "erode_px": erode_px,
        "inpaint_radius": inpaint_radius,
        "views": view_stats,
        "tempo_s": round(time.time() - t0, 2),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", choices=["mv_a", "mv_b"], required=True)
    ap.add_argument("--cos-thresh", type=float, default=0.35)
    ap.add_argument("--depth-eps", type=float, default=0.025)
    ap.add_argument("--erode-px", type=int, default=2)
    ap.add_argument("--inpaint-radius", type=int, default=6)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    np.random.seed(42)
    torch.manual_seed(42)

    work = Path.home() / "printer3d-work" / "carro" / "fox_fullrun" / args.tag
    uv_obj = work / "uv.obj"
    out_png = Path(args.out) if args.out else (work / "bake2048.png")

    if args.tag == "mv_a":
        vdir = Path("/mnt/c/Users/Bruno/Downloads/fox-h/panels/prep")
        views = {
            "front": vdir / "P1_front.png",
            "left": vdir / "P2_side.png",
            "back": vdir / "P3_back.png",
            "right": vdir / "P2r_right.png",
        }
    else:
        vdir = Path("/mnt/c/Users/Bruno/Downloads/fox/prep_real")
        views = {
            "front": vdir / "R1_front.png",
            "left": vdir / "R2_side.png",
            "back": vdir / "R3_back.png",
            "right": vdir / "R2r_right.png",
        }

    res = rebake_mesh(
        uv_obj_path=uv_obj,
        views=views,
        out_png_path=out_png,
        cos_thresh=args.cos_thresh,
        depth_eps=args.depth_eps,
        erode_px=args.erode_px,
        inpaint_radius=args.inpaint_radius,
    )
    print("REBAKE_JSON=" + json.dumps(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
