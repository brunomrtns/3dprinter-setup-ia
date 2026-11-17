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
# alloc conf espelha pipeline_worker.py do fork (garbage_collection_threshold)
# + app.py (max_split_size_mb) + expandable_segments — sem isso o decode OOM em 12GB
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True,garbage_collection_threshold:0.65,max_split_size_mb:128"
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
    ap.add_argument("--res", type=int, choices=[512, 1024], default=512,
                    help="512 = single-stage (cabe em 12GB); 1024 = cascade 512→1024 (pesado)")
    ap.add_argument("--max-tokens", type=int, default=49152,
                    help="teto de tokens do estágio HR do cascade (default oficial)")
    args = ap.parse_args()

    erros = []
    report = {}

    from trellis2.pipelines import Trellis2ImageTo3DPipeline

    t0 = time.time()
    pipeline = Trellis2ImageTo3DPipeline.from_pretrained("microsoft/TRELLIS.2-4B")
    pipeline.cuda()  # low_vram: só define _device='cuda', modelos ficam em CPU até uso
    # decoder SparseUnetVae tem flag low_vram própria (offload por bloco no upsample);
    # o pipeline não a propaga — sem isso o upsample 512→HR estoura VRAM
    pipeline.models["shape_slat_decoder"].low_vram = True
    report["tempo_load_s"] = round(time.time() - t0, 2)

    img = pipeline.preprocess_image(Image.open(args.image))

    # O pipeline oficial roda tudo sob @torch.no_grad() (run()). Sem isso, o
    # decoder/sampler montam grafo de autograd e retêm ~450MB de ativações por
    # conv — causa real do OOM no decode/upsample, não os pesos.
    torch.set_grad_enabled(False)
    torch.manual_seed(args.seed)
    t1 = time.time()
    if pipeline.low_vram:
        pipeline.image_cond_model.to("cuda")
    cond_512 = pipeline._cast_cond(pipeline.get_cond([img], 512))
    if pipeline.low_vram:
        pipeline.image_cond_model.cpu()
        torch.cuda.empty_cache()

    coords = pipeline.sample_sparse_structure(cond_512, 32, 1, {})
    if args.res == 512:
        shape_slat = pipeline.sample_shape_slat(
            cond_512, pipeline.models["shape_slat_flow_model_512"], coords, {}
        )
        res = 512
    else:
        if pipeline.low_vram:
            pipeline.image_cond_model.to("cuda")
        cond_1024 = pipeline._cast_cond(pipeline.get_cond([img], 1024))
        if pipeline.low_vram:
            pipeline.image_cond_model.cpu()
            torch.cuda.empty_cache()
        shape_slat, res = pipeline.sample_shape_slat_cascade(
            cond_512, cond_1024,
            pipeline.models["shape_slat_flow_model_512"],
            pipeline.models["shape_slat_flow_model_1024"],
            512, 1024,
            coords, {},
            args.max_tokens,
        )
    del cond_512
    if args.res == 1024:
        del cond_1024
    shape_slat._spatial_cache = {}
    torch.cuda.empty_cache()

    # decode_shape_slat é helper de baixo nível: quem chama decode_latent faz este
    # setup (low_vram + from_latent/output_layer na GPU). Sem isso from_latent fica
    # em CPU e o forward falha com mismatch de device.
    _dec = pipeline.models["shape_slat_decoder"]
    _dec.low_vram = True
    _dec.from_latent.to(pipeline.device)
    _dec.output_layer.to(pipeline.device)
    # decode_shape_slat não tem decorator own — sem no_grad o autograd reteve
    # ~450MB de ativações por conv (era a causa real do OOM, não os pesos)
    with torch.no_grad():
        meshes, _subs = pipeline.decode_shape_slat(shape_slat, res)
    report["tempo_run_s"] = round(time.time() - t1, 2)
    report["resolucao"] = res
    report["res_mode"] = args.res
    report["max_tokens"] = args.max_tokens

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
