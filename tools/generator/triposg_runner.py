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

    raw_im = Image.open(args.image)
    has_explicit_alpha = raw_im.mode == "RGBA" and np.asarray(raw_im)[..., 3].min() < 250

    # RMBG-1.4 (remoção de fundo do próprio TripoSG) via cache HF; se a imagem RGBA já traz
    # máscara alfa explícita (ex.: máscara de carroceria com vidros grafite), usa a máscara direto.
    rmbg_net = None
    if not has_explicit_alpha:
        try:
            from briarmbg import BriaRMBG
            from huggingface_hub import snapshot_download

            rmbg_dir = snapshot_download("briaai/RMBG-1.4")
            rmbg_net = BriaRMBG.from_pretrained(rmbg_dir).to(device)
            rmbg_net.eval()
        except Exception as e:  # noqa: BLE001
            erros.append(f"rmbg_indisponivel_seguiu_sem: {type(e).__name__}: {str(e)[:200]}")

    if has_explicit_alpha:
        arr = np.asarray(raw_im).astype(np.float32)
        alpha = arr[..., 3:4] / 255.0
        ys, xs = np.where(arr[..., 3] > 16)
        rgb = (arr[..., :3] * alpha + 255.0 * (1.0 - alpha)).astype(np.uint8)
        if len(xs) > 0 and len(ys) > 0:
            x0, x1 = int(xs.min()), int(xs.max())
            y0, y1 = int(ys.min()), int(ys.max())
            crop = rgb[y0 : y1 + 1, x0 : x1 + 1]
            h, w = crop.shape[:2]
            side = int(max(h, w) * 1.15)
            canvas = np.full((side, side, 3), 255, dtype=np.uint8)
            oy, ox = (side - h) // 2, (side - w) // 2
            canvas[oy : oy + h, ox : ox + w] = crop
            img_pil = Image.fromarray(canvas, mode="RGB").resize((518, 518), Image.LANCZOS)
        else:
            img_pil = Image.fromarray(rgb, mode="RGB").resize((518, 518), Image.LANCZOS)
    elif rmbg_net is not None:
        img_pil = prepare_image(args.image, bg_color=np.array([1.0, 1.0, 1.0]), rmbg_net=rmbg_net)
        rmbg_net.to("cpu")
        del rmbg_net
        torch.cuda.empty_cache()
    else:
        # fallback documentado: entrada já padronizada pelo preprocess_input.py (C2)
        img_pil = raw_im.convert("RGB").resize((518, 518), Image.LANCZOS)

    from huggingface_hub import snapshot_download

    local = snapshot_download("VAST-AI/TripoSG")
    pipe = TripoSGPipeline.from_pretrained(local, trust_remote_code=True).to(device, dtype)
    report["tempo_load_s"] = round(time.time() - t0, 2)

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
