#!/usr/bin/env python3
"""Runner TripoSR — geração image→3D em subprocesso isolado (filho do plugin).

Uso (dentro do WSL, venv printer3d-ia, com PYTHONPATH incluindo o shim torchmcubes):
    python triposr_runner.py --image <img.png> --output-dir <dir>

Espelha run.py oficial do VAST-AI-Research/TripoSR (preprocess rembg + extract_mesh 256).
Emitte na última linha: REPORT_JSON={...}.
"""
import argparse
import json
import os
import sys
import time
import traceback

import numpy as np

TRIPOSR_HOME = os.environ.get("TRIPOSR_HOME", os.path.expanduser("~/tools/TripoSR"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--pretrained", default="stabilityai/TripoSR")
    parser.add_argument("--mc-resolution", type=int, default=256)
    parser.add_argument("--chunk-size", type=int, default=8192)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    report = {
        "mode": "triposr",
        "model": "stabilityai/TripoSR",
        "image": args.image,
        "seed": None,  # reconstrução determinística (sem ruído de difusão)
        "erros": [],
    }
    t_total0 = time.time()

    sys.path.insert(0, TRIPOSR_HOME)
    import rembg
    import torch
    from PIL import Image

    from tsr.system import TSR
    from tsr.utils import remove_background, resize_foreground

    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    t0 = time.time()
    model = TSR.from_pretrained(
        args.pretrained, config_name="config.yaml", weight_name="model.ckpt"
    )
    model.renderer.set_chunk_size(args.chunk_size)
    model.to(device)
    report["tempo_load_s"] = round(time.time() - t0, 2)

    # Preprocessamento canônico do run.py oficial
    t0 = time.time()
    rembg_session = rembg.new_session()
    image = remove_background(Image.open(args.image), rembg_session)
    image = resize_foreground(image, 0.85)
    image = np.array(image).astype(np.float32) / 255.0
    image = image[:, :, :3] * image[:, :, 3:4] + (1 - image[:, :, 3:4]) * 0.5
    image = Image.fromarray((image * 255.0).astype(np.uint8))
    image.save(os.path.join(args.output_dir, "input_preproc.png"))
    report["tempo_preproc_s"] = round(time.time() - t0, 2)

    t0 = time.time()
    with torch.no_grad():
        scene_codes = model([image], device=device)
    report["tempo_run_s"] = round(time.time() - t0, 2)

    t0 = time.time()
    meshes = model.extract_mesh(
        scene_codes, True, resolution=args.mc_resolution
    )
    report["tempo_extract_s"] = round(time.time() - t0, 2)

    tm = meshes[0]
    obj_path = os.path.join(args.output_dir, "mesh.obj")
    tm.export(obj_path)
    report["obj"] = obj_path
    report["vertices"] = int(len(tm.vertices))
    report["faces"] = int(len(tm.faces))
    report["watertight_bruto"] = bool(tm.is_watertight)
    report["winding_consistent"] = bool(tm.is_winding_consistent)
    report["bbox"] = [round(float(x), 4) for x in tm.extents]
    report["device"] = device

    report["tempo_total_s"] = round(time.time() - t_total0, 2)
    report["cuda_ok"] = device.startswith("cuda")
    print("REPORT_JSON=" + json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        print(
            "REPORT_JSON="
            + json.dumps({"mode": "triposr", "erros": ["fatal: ver traceback acima"]})
        )
        sys.exit(1)
