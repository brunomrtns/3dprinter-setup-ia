#!/usr/bin/env python3
"""Reconstrução 3D por fotogrametria feed-forward (VGGT — facebook/VGGT, MIT) — Fase C / C6.

Fluxo:
  1. Carrega N imagens de um diretório (--images-dir)
  2. Executa VGGT (sob guard de VRAM) -> extrai depth/world points + mapa de confiança
  3. Filtra pontos por percentil/limiar de confiança (--conf-pct default 35) e remove outliers (Open3D)
  4. Estima normais orientadas e reconstrói superfície via Poisson (--poisson-depth default 9)
  5. Remove triângulos de baixa densidade nas bordas, limpa ilhas e exporta mesh.obj + mesh.glb + report.json

Uso:
  ~/.venvs/vggt/bin/python tools/generator/vggt_recon.py --images-dir <pasta_fotos> --output-dir <saida>
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gpu_guard import GpuJobContext, VramPoller  # noqa: E402


def collect_images(images_dir: str) -> list[str]:
    exts = ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.JPG", "*.JPEG", "*.PNG")
    files: list[str] = []
    for ext in exts:
        files.extend(glob.glob(os.path.join(images_dir, ext)))
    return sorted(set(files))


def run_vggt_pointcloud(image_paths: list[str], model_id: str, conf_percentile: float):
    import numpy as np
    import torch
    from vggt.models.vggt import VGGT
    from vggt.utils.load_fn import load_and_preprocess_images
    from vggt.utils.pose_enc import pose_encoding_to_extri_intri
    from vggt.utils.geometry import unproject_depth_map_to_point_map

    torch.set_grad_enabled(False)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if (device == "cuda" and torch.cuda.get_device_capability()[0] >= 8) else torch.float16

    t0 = time.time()
    model = VGGT.from_pretrained(model_id).to(device)
    model.eval()
    t_load = round(time.time() - t0, 2)

    t1 = time.time()
    images = load_and_preprocess_images(image_paths).to(device)
    with torch.no_grad(), torch.amp.autocast(device_type="cuda", dtype=dtype):
        predictions = model(images)

    # Usa point_map direto se presente, ou desprojeta depth_map com extrínsecos/intrínsecos
    if "world_points" in predictions:
        pts_map = predictions["world_points"].squeeze(0).float().cpu().numpy()
        conf_map = predictions.get("world_points_conf", predictions.get("depth_conf")).squeeze(0).float().cpu().numpy()
    else:
        extrinsic, intrinsic = pose_encoding_to_extri_intri(predictions["pose_enc"], images.shape[-2:])
        depth_map = predictions["depth"].squeeze(0).float().cpu().numpy()
        conf_map = predictions["depth_conf"].squeeze(0).float().cpu().numpy()
        pts_map = unproject_depth_map_to_point_map(
            depth_map, extrinsic.squeeze(0).float().cpu().numpy(), intrinsic.squeeze(0).float().cpu().numpy()
        )

    imgs_np = images.squeeze(0).permute(0, 2, 3, 1).float().cpu().numpy()
    t_infer = round(time.time() - t1, 2)

    del model, predictions, images
    if device == "cuda":
        torch.cuda.empty_cache()

    pts = pts_map.reshape(-1, 3)
    cols = np.clip(imgs_np.reshape(-1, 3), 0.0, 1.0)
    conf = conf_map.reshape(-1)

    valid = np.isfinite(pts).all(axis=-1) & np.isfinite(conf)
    pts, cols, conf = pts[valid], cols[valid], conf[valid]

    thresh = float(np.percentile(conf, conf_percentile))
    keep = conf >= thresh
    return pts[keep], cols[keep], t_load, t_infer, thresh


def poisson_mesh_from_points(pts, cols, poisson_depth: int, density_trim_quantile: float = 0.04):
    import numpy as np
    import open3d as o3d
    import trimesh

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pts.astype(np.float64))
    pcd.colors = o3d.utility.Vector3dVector(cols.astype(np.float64))

    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=24, std_ratio=1.8)
    pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.05, max_nn=30))
    pcd.orient_normals_consistent_tangent_plane(30)

    mesh_o3d, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=poisson_depth)
    densities = np.asarray(densities)
    if density_trim_quantile > 0:
        mesh_o3d.remove_vertices_by_mask(densities < np.quantile(densities, density_trim_quantile))

    m = trimesh.Trimesh(
        vertices=np.asarray(mesh_o3d.vertices),
        faces=np.asarray(mesh_o3d.triangles),
        process=True,
    )
    comps = m.split(only_watertight=False)
    if comps:
        m = max(comps, key=lambda c: len(c.faces))
    m.fix_normals()
    return m


def main() -> int:
    ap = argparse.ArgumentParser(description="Fotogrametria feed-forward VGGT -> Poisson -> OBJ/GLB")
    ap.add_argument("--images-dir", required=True, help="Diretório com 8 a 40 fotos do objeto")
    ap.add_argument("--output-dir", required=True, help="Diretório de saída")
    ap.add_argument("--model-id", default="facebook/VGGT-1B")
    ap.add_argument("--conf-pct", type=float, default=35.0, help="Percentil de corte de confiança (0..90)")
    ap.add_argument("--poisson-depth", type=int, default=9, help="Profundidade octree Poisson (8..10)")
    ap.add_argument("--vram-min-free-mib", type=int, default=8_500)
    args = ap.parse_args()

    image_paths = collect_images(args.images_dir)
    if len(image_paths) < 3:
        print(f"ERRO: necessárias ao menos 3 imagens em {args.images_dir} (encontradas: {len(image_paths)})", file=sys.stderr)
        return 1

    os.makedirs(args.output_dir, exist_ok=True)
    report: dict = {
        "mode": "vggt",
        "model": args.model_id,
        "num_images": len(image_paths),
        "images_dir": os.path.abspath(args.images_dir),
        "conf_pct": args.conf_pct,
        "poisson_depth": args.poisson_depth,
        "erros": [],
    }

    t0 = time.time()
    with GpuJobContext(min_free_mib=args.vram_min_free_mib, job_name="vggt"):
        poller = VramPoller(interval_s=1.0)
        poller.start()
        pts, cols, t_load, t_infer, conf_thresh = run_vggt_pointcloud(
            image_paths=image_paths,
            model_id=args.model_id,
            conf_percentile=args.conf_pct,
        )
        peak = poller.stop()

    t_mesh0 = time.time()
    mesh = poisson_mesh_from_points(pts, cols, poisson_depth=args.poisson_depth)
    t_mesh = round(time.time() - t_mesh0, 2)

    obj_path = os.path.join(args.output_dir, "mesh.obj")
    glb_path = os.path.join(args.output_dir, "mesh.glb")
    _ = mesh.vertex_normals
    mesh.export(obj_path)
    mesh.export(glb_path, file_type="glb", include_normals=True)

    report.update(
        tempo_s=round(time.time() - t0, 2),
        tempo_load_s=t_load,
        tempo_run_s=t_infer,
        tempo_poisson_s=t_mesh,
        vram_pico_mib=peak.used_mib,
        vram_baseline_mib=peak.baseline_mib,
        pontos_filtrados=int(len(pts)),
        conf_threshold=round(conf_thresh, 4),
        vertices=int(len(mesh.vertices)),
        faces=int(len(mesh.faces)),
        watertight=bool(mesh.is_watertight),
        bbox=[round(float(v), 4) for v in mesh.bounding_box.extents],
        obj=obj_path,
        glb=glb_path,
    )
    Path(args.output_dir, "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("REPORT_JSON=" + json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
