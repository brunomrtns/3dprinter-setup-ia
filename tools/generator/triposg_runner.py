#!/usr/bin/env python3
"""Runner TripoSG (Fase C/C3) — executa no venv ~.venvs/triposg.

Espelha o contrato dos runners do benchmark Fase 1: recebe --image e
--output-dir, salva mesh.obj e imprime REPORT_JSON=... na última linha.
"""
import argparse
import json
import os
import sys
import time

TRIPOSG_HOME = os.environ["TRIPOSG_HOME"]
sys.path.insert(0, TRIPOSG_HOME)
sys.path.insert(0, os.path.join(TRIPOSG_HOME, "scripts"))

import numpy as np  # noqa: E402
import torch  # noqa: E402
import trimesh  # noqa: E402
from PIL import Image  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    erros = []
    report = {}

    from triposg.pipelines.pipeline_triposg import TripoSGPipeline
    from image_process import prepare_image

    t0 = time.time()
    device = "cuda"
    dtype = torch.float16

    # RMBG-1.4 (remoção de fundo do próprio TripoSG) via cache HF; fallback:
    # entrada já pré-processada (fundo branco) → seguir sem rmbg, documentado.
    rmbg_net = None
    try:
        from briarmbg import BriaRMBG
        from huggingface_hub import snapshot_download

        rmbg_dir = snapshot_download("briaai/RMBG-1.4")
        rmbg_net = BriaRMBG.from_pretrained(rmbg_dir).to(device)
        rmbg_net.eval()
    except Exception as e:  # noqa: BLE001
        erros.append(f"rmbg_indisponivel_seguiu_sem: {type(e).__name__}: {str(e)[:200]}")

    from huggingface_hub import snapshot_download

    local = snapshot_download("VAST-AI/TripoSG")
    pipe = TripoSGPipeline.from_pretrained(local, trust_remote_code=True).to(device, dtype)
    report["tempo_load_s"] = round(time.time() - t0, 2)

    image = Image.open(args.image).convert("RGB")
    if rmbg_net is not None:
        img_pil = prepare_image(args.image, bg_color=np.array([1.0, 1.0, 1.0]), rmbg_net=rmbg_net)
    else:
        # fallback documentado: entrada já padronizada pelo preprocess_input.py (C2)
        img_pil = image.resize((518, 518), Image.LANCZOS)

    t1 = time.time()
    with torch.no_grad():
        outputs = pipe(
            image=img_pil,
            generator=torch.Generator(device=device).manual_seed(args.seed),
            num_inference_steps=50,
            guidance_scale=7.0,
        ).samples[0]
    report["tempo_run_s"] = round(time.time() - t1, 2)

    mesh = trimesh.Trimesh(outputs[0].astype(np.float32), np.ascontiguousarray(outputs[1]))
    out_path = os.path.join(args.output_dir, "mesh.obj")
    os.makedirs(args.output_dir, exist_ok=True)
    mesh.export(out_path)

    report.update(
        vertices=int(len(mesh.vertices)),
        faces=int(len(mesh.faces)),
        bbox=[round(float(v), 4) for v in mesh.bounding_box.extents],
        obj=out_path,
        erros=erros,
    )
    print("REPORT_JSON=" + json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
