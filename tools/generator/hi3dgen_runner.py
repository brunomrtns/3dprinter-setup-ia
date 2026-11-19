#!/usr/bin/env python3
"""Runner Hi3DGen (Fase C/C7-B) — executa no venv ~/.venvs/hi3dgen.

Recebe --image e --output-dir, seed fixa (default 42), gera mapa de normais via NiRNE
com offload sequencial de VRAM, executa Hi3DGenPipeline (trellis-normal-v0-1),
salva normal.png e mesh.obj, e imprime REPORT_JSON=... na última linha.
"""
import argparse
import json
import os
import sys
import time

HI3DGEN_HOME = os.environ.get("HI3DGEN_HOME", os.path.expanduser("~/tools/Hi3DGen"))
sys.path.insert(0, HI3DGEN_HOME)
sys.path.insert(0, os.path.join(HI3DGEN_HOME, "NiRNE"))

import numpy as np  # noqa: E402
import torch  # noqa: E402
import trimesh  # noqa: E402
from PIL import Image  # noqa: E402


def get_vram_used_mib() -> float:
    if not torch.cuda.is_available():
        return 0.0
    return round(torch.cuda.memory_allocated() / (1024 * 1024), 2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--resolution", type=int, default=1024)
    ap.add_argument("--ss-steps", type=int, default=50)
    ap.add_argument("--ss-cfg", type=float, default=3.0)
    ap.add_argument("--slat-steps", type=int, default=6)
    ap.add_argument("--slat-cfg", type=float, default=3.0)
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    report = {
        "generator": "hi3dgen",
        "seed": args.seed,
        "input_image": args.image,
    }
    erros = []

    t_start = time.time()
    torch.cuda.reset_peak_memory_stats()
    vram_start = get_vram_used_mib()

    # 1. Carrega imagem de entrada
    raw_im = Image.open(args.image)
    if raw_im.mode != "RGBA":
        raw_im = raw_im.convert("RGBA")

    # 2. Fase A: Estimador de Normais NiRNE
    t_phase_a_start = time.time()
    print("[hi3dgen] Fase A: Carregando NiRNE (YOSO Normal)...", flush=True)
    weights_dir = os.path.join(HI3DGEN_HOME, "weights")

    nirne_predictor = torch.hub.load(
        os.path.join(HI3DGEN_HOME, "NiRNE"),
        "NiRNE",
        source="local",
        local_cache_dir=weights_dir,
        yoso_version="yoso-normal-v1-8-1",
    )
    vram_nirne_loaded = get_vram_used_mib()
    print(f"[hi3dgen] NiRNE carregado. VRAM ativa: {vram_nirne_loaded} MiB", flush=True)

    print("[hi3dgen] Fase A: Gerando mapa de normais...", flush=True)
    # Se a imagem tem canal alfa com fundo branco/recortado, passamos direto
    normal_image = nirne_predictor(
        raw_im,
        resolution=768,
        match_input_resolution=True,
        data_type="object",
    )
    t_phase_a = round(time.time() - t_phase_a_start, 2)
    report["tempo_normais_s"] = t_phase_a

    # Se a imagem de entrada traz canal alfa recortado, transfere para a imagem de normais
    if raw_im.mode == "RGBA":
        r, g, b = normal_image.convert("RGB").split()
        a = raw_im.resize(normal_image.size, Image.Resampling.NEAREST).split()[-1]
        normal_image = Image.merge("RGBA", (r, g, b, a))

    # Salva o mapa de normais para conferência visual
    normal_path = os.path.join(args.output_dir, "normal.png")
    normal_image.save(normal_path)
    report["normal_image"] = normal_path
    print(f"[hi3dgen] Mapa de normais salvo em: {normal_path} ({t_phase_a}s)", flush=True)

    # Offload do NiRNE para liberar VRAM antes do estágio 3D
    del nirne_predictor
    torch.cuda.empty_cache()
    print(f"[hi3dgen] NiRNE descarregado da GPU. VRAM: {get_vram_used_mib()} MiB", flush=True)

    # 3. Fase B: Pipeline 3D Hi3DGen
    t_phase_b_start = time.time()
    print("[hi3dgen] Fase B: Carregando Hi3DGenPipeline...", flush=True)
    from hi3dgen.pipelines import Hi3DGenPipeline

    trellis_path = os.path.join(weights_dir, "trellis-normal-v0-1")
    pipeline = Hi3DGenPipeline.from_pretrained(trellis_path)
    pipeline.cuda()
    t_load_pipe = round(time.time() - t_phase_b_start, 2)
    report["tempo_load_pipeline_s"] = t_load_pipe
    print(f"[hi3dgen] Hi3DGenPipeline carregado em {t_load_pipe}s. VRAM: {get_vram_used_mib()} MiB", flush=True)

    # 4. Fase C: Inferência 3D guiada por normais
    t_phase_c_start = time.time()
    print(f"[hi3dgen] Fase C: Inferência 3D (seed {args.seed})...", flush=True)

    # Prepara imagem normal formatada para 1024x1024
    norm_prep = pipeline.preprocess_image(normal_image, resolution=args.resolution)

    with torch.no_grad():
        outputs = pipeline.run(
            norm_prep,
            seed=args.seed,
            formats=["mesh"],
            preprocess_image=False,
            sparse_structure_sampler_params={
                "steps": args.ss_steps,
                "cfg_strength": args.ss_cfg,
            },
            slat_sampler_params={
                "steps": args.slat_steps,
                "cfg_strength": args.slat_cfg,
            },
        )
    t_phase_c = round(time.time() - t_phase_c_start, 2)
    report["tempo_run_3d_s"] = t_phase_c
    print(f"[hi3dgen] Inferência concluída em {t_phase_c}s", flush=True)

    # 5. Exportação da malha trimesh
    generated_mesh = outputs["mesh"][0]
    trimesh_mesh = generated_mesh.to_trimesh(transform_pose=True)

    out_obj = os.path.join(args.output_dir, "mesh.obj")
    trimesh_mesh.export(out_obj)
    print(f"[hi3dgen] Mesh OBJ salvo em: {out_obj}", flush=True)

    # Estatísticas da malha
    num_verts = int(len(trimesh_mesh.vertices))
    num_faces = int(len(trimesh_mesh.faces))
    extents = [round(float(v), 4) for v in trimesh_mesh.bounding_box.extents]

    vram_peak_mib = round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2)
    report["vram_peak_mib"] = vram_peak_mib
    report["tempo_total_s"] = round(time.time() - t_start, 2)
    report.update(
        vertices=num_verts,
        faces=num_faces,
        bbox=extents,
        obj=out_obj,
        erros=erros,
    )

    print(f"[hi3dgen] Concluído! Vértices: {num_verts:,}, Faces: {num_faces:,}, VRAM Pico: {vram_peak_mib} MiB", flush=True)
    print("REPORT_JSON=" + json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
