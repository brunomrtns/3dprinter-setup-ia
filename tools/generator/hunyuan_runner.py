#!/usr/bin/env python3
"""Runner Hunyuan3D (Fase C / C6) — executa no venv ~/.venvs/hunyuan.

Suporta dois modos shape-only (sem estágio de pintura 21GB, foco em geometria p/ impressão 3D):
  1. --variant mv  (default quando --left/--back/--right são passados):
     tencent/Hunyuan3D-2mv (subfolder hunyuan3d-dit-v2-mv, DinoImageEncoderMV multi-vista
     com até 4 vistas ortogonais: front, left, back, right).
  2. --variant 2.1 (default single-view):
     tencent/Hunyuan3D-2.1 (subfolder hunyuan3d-dit-v2-1, DiT MoE 4096 latents single-view).

Otimização de VRAM para RTX 3060 12GB:
  - torch.set_grad_enabled(False) + expandable_segments
  - Offload explícito por estágio (conditioner -> CPU após encode; DiT -> CPU antes do decode VAE 384³),
    reduzindo o pico de VRAM em ~3,5 GB sem perda de qualidade.
Contrato: imprime REPORT_JSON=... na última linha do stdout.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

os.environ.setdefault(
    "PYTORCH_CUDA_ALLOC_CONF",
    "expandable_segments:True,garbage_collection_threshold:0.65,max_split_size_mb:128",
)

HUNYUAN21_HOME = os.environ.get("HUNYUAN21_HOME", os.path.expanduser("~/tools/Hunyuan3D-2.1"))
HUNYUAN2_HOME = os.environ.get("HUNYUAN2_HOME", os.path.expanduser("~/tools/Hunyuan3D-2"))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402


def load_rgba(path: str) -> Image.Image:
    """Carrega imagem garantindo canal alfa útil para o ImageProcessorV2.recenter."""
    im = Image.open(path)
    if im.mode == "RGBA":
        a = np.asarray(im)[..., 3]
        # Se a imagem RGBA já tem máscara recortada (ex.: no_windows_rgba), usa direto
        if a.min() < 250:
            return im
    # Se veio RGB com fundo branco do preprocess_input.py (C2), converte fundo branco externo em alpha=0 via flood-fill
    rgb = np.asarray(im.convert("RGB"))
    from scipy.ndimage import binary_erosion, binary_fill_holes

    non_white = (rgb < 248).any(axis=-1)
    solid_mask = binary_fill_holes(non_white)
    if solid_mask.any():
        solid_mask = binary_erosion(solid_mask, iterations=1)
        alpha = (solid_mask.astype(np.uint8)) * 255
    else:
        alpha = np.full(rgb.shape[:2], 255, dtype=np.uint8)
    return Image.fromarray(np.dstack([rgb, alpha]), mode="RGBA")


def run_with_stage_offload(
    pipeline,
    image_input,
    steps: int,
    guidance_scale: float,
    octree_res: int,
    seed: int,
    num_chunks: int = 8000,
):
    """Executa o pipeline FlowMatching com offload conditioner -> model -> vae na 3060 12GB."""
    torch.set_grad_enabled(False)
    gen = torch.Generator(device="cuda").manual_seed(seed)

    # 1. Conditioner na GPU
    pipeline.conditioner.to("cuda", dtype=pipeline.dtype)
    cond_inputs = pipeline.prepare_image(image_input)
    image_tensor = cond_inputs.pop("image")
    do_cfg = guidance_scale >= 0 and not (
        hasattr(pipeline.model, "guidance_embed") and pipeline.model.guidance_embed is True
    )
    cond = pipeline.encode_cond(
        image=image_tensor,
        additional_cond_inputs=cond_inputs,
        do_classifier_free_guidance=do_cfg,
        dual_guidance=False,
    )
    # Libera conditioner da VRAM antes do DiT
    pipeline.conditioner.to("cpu")
    torch.cuda.empty_cache()

    # 2. DiT Flow Matching na GPU
    pipeline.model.to("cuda", dtype=pipeline.dtype)
    batch_size = image_tensor.shape[0]
    sigmas = np.linspace(0, 1, steps)
    pipeline.scheduler.set_timesteps(sigmas=sigmas, device="cuda")
    timesteps = pipeline.scheduler.timesteps
    latents = pipeline.prepare_latents(batch_size, pipeline.dtype, torch.device("cuda"), gen)

    guidance = None
    if hasattr(pipeline.model, "guidance_embed") and pipeline.model.guidance_embed is True:
        guidance = torch.tensor([guidance_scale] * batch_size, device="cuda", dtype=pipeline.dtype)

    for t in timesteps:
        latent_model_input = torch.cat([latents] * 2) if do_cfg else latents
        timestep = t.expand(latent_model_input.shape[0]).to(latents.dtype)
        timestep = timestep / pipeline.scheduler.config.num_train_timesteps
        noise_pred = pipeline.model(latent_model_input, timestep, cond, guidance=guidance)
        if do_cfg:
            noise_pred_cond, noise_pred_uncond = noise_pred.chunk(2)
            noise_pred = noise_pred_uncond + guidance_scale * (noise_pred_cond - noise_pred_uncond)
        latents = pipeline.scheduler.step(noise_pred, t, latents).prev_sample

    # Libera DiT da VRAM antes do Marching Cubes 384³ no VAE
    pipeline.model.to("cpu")
    del cond, image_tensor
    torch.cuda.empty_cache()

    # 3. ShapeVAE decode -> malha trimesh
    pipeline.vae.to("cuda", dtype=pipeline.dtype)
    meshes = pipeline._export(
        latents,
        output_type="trimesh",
        box_v=1.01,
        mc_level=0.0,
        num_chunks=num_chunks,
        octree_resolution=octree_res,
        mc_algo="mc",
        enable_pbar=False,
    )
    pipeline.vae.to("cpu")
    torch.cuda.empty_cache()
    return meshes[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True, help="Imagem frontal (ou única no modo single-view)")
    ap.add_argument("--left", default=None, help="Vista lateral esquerda (para multi-vista)")
    ap.add_argument("--back", default=None, help="Vista traseira (para multi-vista)")
    ap.add_argument("--right", default=None, help="Vista lateral direita (para multi-vista)")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--variant", choices=["auto", "mv", "2.1"], default="auto")
    ap.add_argument("--steps", type=int, default=50)
    ap.add_argument("--octree-res", type=int, default=384)
    ap.add_argument("--guidance-scale", type=float, default=5.0)
    args = ap.parse_args()

    has_extra_views = any([args.left, args.back, args.right])
    variant = args.variant
    if variant == "auto":
        variant = "mv" if has_extra_views else "2.1"

    t0 = time.time()
    torch.set_grad_enabled(False)
    report: dict = {"variant": variant, "erros": []}

    if variant == "mv":
        sys.path.insert(0, HUNYUAN2_HOME)
        from hy3dgen.shapegen.pipelines import Hunyuan3DDiTFlowMatchingPipeline

        pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
            "tencent/Hunyuan3D-2mv",
            subfolder="hunyuan3d-dit-v2-mv",
            use_safetensors=True,
            variant="fp16",
            device="cpu",
            dtype=torch.float16,
        )
        views_dict = {"front": load_rgba(args.image)}
        if args.left:
            views_dict["left"] = load_rgba(args.left)
        if args.back:
            views_dict["back"] = load_rgba(args.back)
        if args.right:
            views_dict["right"] = load_rgba(args.right)
        image_input = views_dict
        report["views_used"] = list(views_dict.keys())
    else:
        sys.path.insert(0, os.path.join(HUNYUAN21_HOME, "hy3dshape"))
        from hy3dshape.pipelines import Hunyuan3DDiTFlowMatchingPipeline

        pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
            "tencent/Hunyuan3D-2.1",
            subfolder="hunyuan3d-dit-v2-1",
            use_safetensors=False,
            variant="fp16",
            device="cpu",
            dtype=torch.float16,
        )
        image_input = load_rgba(args.image)
        report["views_used"] = ["single"]

    report["tempo_load_s"] = round(time.time() - t0, 2)

    t1 = time.time()
    mesh = run_with_stage_offload(
        pipeline=pipeline,
        image_input=image_input,
        steps=args.steps,
        guidance_scale=args.guidance_scale,
        octree_res=args.octree_res,
        seed=args.seed,
    )
    report["tempo_run_s"] = round(time.time() - t1, 2)

    os.makedirs(args.output_dir, exist_ok=True)
    out_path = os.path.join(args.output_dir, "mesh.obj")
    mesh.export(out_path)

    report.update(
        vertices=int(len(mesh.vertices)),
        faces=int(len(mesh.faces)),
        bbox=[round(float(v), 4) for v in mesh.bounding_box.extents],
        octree_resolution=args.octree_res,
        steps=args.steps,
        obj=out_path,
    )
    print("REPORT_JSON=" + json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
