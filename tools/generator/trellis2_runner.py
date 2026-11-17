#!/usr/bin/env python3
"""Runner TRELLIS.2 (Fase C/C3) — executa no venv ~.venvs/trellis2.

Fluxo SHAPE-ONLY espelhando o branch '1024_cascade' do pipeline oficial
(sample_sparse_structure → sample_shape_slat_cascade → decode_shape_slat),
PULANDO o estágio de textura (tex_slat) — para impressão 3D só a geometria
importa (mesma postura do TripoSR/TripoSG). Contrato: REPORT_JSON= na stdout.
"""
import argparse
import json
import os
import sys
import time

os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("ATTN_BACKEND", "xformers")  # fallback documentado (sem flash-attn)

TRELLIS2_HOME = os.environ["TRELLIS2_HOME"]
sys.path.insert(0, TRELLIS2_HOME)

import torch  # noqa: E402
from PIL import Image  # noqa: E402

MAX_FACES = 2_000_000  # teto para scoring prático; contagem original registrada


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    erros = []
    report = {}

    from trellis2.pipelines import Trellis2ImageTo3DPipeline

    t0 = time.time()
    pipeline = Trellis2ImageTo3DPipeline.from_pretrained("microsoft/TRELLIS.2-4B")
    # low_vram=True (default do pipeline): modelos migram CPU↔GPU por estágio
    pipeline.preprocess_image(True)
    report["tempo_load_s"] = round(time.time() - t0, 2)

    img = pipeline.preprocess_image(Image.open(args.image))

    torch.manual_seed(args.seed)
    t1 = time.time()
    if pipeline.low_vram:
        pipeline.image_cond_model.to("cuda")
    cond_512 = pipeline._cast_cond(pipeline.get_cond([img], 512))
    cond_1024 = pipeline._cast_cond(pipeline.get_cond([img], 1024))
    if pipeline.low_vram:
        pipeline.image_cond_model.cpu()
        torch.cuda.empty_cache()

    coords = pipeline.sample_sparse_structure(cond_512, 32, 1, {})
    shape_slat, res = pipeline.sample_shape_slat_cascade(
        cond_512, cond_1024,
        pipeline.models["shape_slat_flow_model_512"],
        pipeline.models["shape_slat_flow_model_1024"],
        512, 1024,
        coords, {},
        49152,
    )
    del cond_512, cond_1024
    shape_slat._spatial_cache = {}
    torch.cuda.empty_cache()

    meshes, _subs = pipeline.decode_shape_slat(shape_slat, res)
    report["tempo_run_s"] = round(time.time() - t1, 2)
    report["resolucao"] = res

    m = meshes[0]
    faces_raw = int(len(m.faces))
    if faces_raw > MAX_FACES:
        m.simplify(MAX_FACES)
    verts = m.vertices.float().cpu().numpy()
    faces = m.faces.int().cpu().numpy()

    import trimesh  # noqa: E402

    mesh = trimesh.Trimesh(verts, faces)
    out_path = os.path.join(args.output_dir, "mesh.obj")
    os.makedirs(args.output_dir, exist_ok=True)
    mesh.export(out_path)

    report.update(
        vertices=int(len(mesh.vertices)),
        faces=int(len(mesh.faces)),
        faces_raw_antes_simplify=faces_raw,
        bbox=[round(float(v), 4) for v in mesh.bounding_box.extents],
        obj=out_path,
        erros=erros,
    )
    print("REPORT_JSON=" + json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
