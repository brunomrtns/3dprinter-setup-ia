#!/usr/bin/env python3
"""Runner TRELLIS — geração image→3D em subprocesso isolado (filho do plugin).

Uso (dentro do WSL, venv printer3d-ia):
    python trellis_runner.py --image <img.png> --output-dir <dir> [--seed 1]

Emitte na última linha: REPORT_JSON={...} com métricas do GenerationReport.
O mesh é exportado em OBJ (sem textura) e, se possível, GLB texturizado.
"""
import argparse
import json
import os
import sys
import time
import traceback

REPO_TRELLIS = os.environ.get("TRELLIS_HOME", os.path.expanduser("~/tools/TRELLIS"))
CKPTS_DEFAULT = os.path.expanduser("~/ai-models/trellis/TRELLIS-image-large")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--ckpts", default=CKPTS_DEFAULT)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Alocador: segmentos expansíveis + GC agressivo + blocos menores — mitiga
    # OOM real no decode FlexiCubes de casos densos (castelo/caixote/robô) com
    # ~11,9 GB úteis na 3060 12GB (benchmark Fase 1, 2026-11-04).
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = (
        "expandable_segments:True,garbage_collection_threshold:0.8,max_split_size_mb:256"
    )
    os.environ.setdefault("ATTN_BACKEND", "flash-attn")
    os.environ.setdefault("SPCONV_ALGO", "native")

    report = {
        "mode": "trellis",
        "model": "microsoft/TRELLIS-image-large",
        "image": args.image,
        "seed": args.seed,
        "erros": [],
    }

    t_total0 = time.time()

    # Import do repo oficial (clone em ~/tools/TRELLIS)
    sys.path.insert(0, REPO_TRELLIS)
    from PIL import Image

    import trimesh

    t0 = time.time()
    from trellis.pipelines import TrellisImageTo3DPipeline

    pipe = TrellisImageTo3DPipeline.from_pretrained(args.ckpts)
    pipe.cuda()
    report["tempo_load_s"] = round(time.time() - t0, 2)

    image = Image.open(args.image)

    # Formats: mesh é o artefato do benchmark (scoring geométrico). "gaussian"
    # só alimentaria o GLB texturizado (pendência nvdiffrast) e dobra o churn
    # de VRAM — causa do OOM real documentado no smoke test do plugin.
    import inspect

    run_kwargs = {"seed": args.seed}
    try:
        params = inspect.signature(pipe.run).parameters
        if "formats" in params:
            run_kwargs["formats"] = ["mesh"]
    except (TypeError, ValueError):
        pass

    t0 = time.time()
    outputs = pipe.run(image, **run_kwargs)
    report["tempo_run_s"] = round(time.time() - t0, 2)

    # Export OBJ (malha pura — base do scoring objetivo)
    mesh_res = outputs["mesh"][0]
    tm = trimesh.Trimesh(
        vertices=mesh_res.vertices.detach().float().cpu().numpy(),
        faces=mesh_res.faces.detach().cpu().numpy(),
        process=False,
    )
    obj_path = os.path.join(args.output_dir, "mesh.obj")
    tm.export(obj_path)
    report["obj"] = obj_path
    report["vertices"] = int(len(tm.vertices))
    report["faces"] = int(len(tm.faces))
    report["watertight_bruto"] = bool(tm.is_watertight)
    report["winding_consistent"] = bool(tm.is_winding_consistent)
    ext = tm.extents
    report["bbox"] = [round(float(x), 4) for x in ext]

    # GLB texturizado (requer nvdiffrast — pendência documentada; só se houver gaussian)
    glb_path = os.path.join(args.output_dir, "textured.glb")
    if "gaussian" in outputs:
        try:
            from trellis.utils import postprocessing_utils

            glb = postprocessing_utils.to_glb(
                outputs["gaussian"][0], outputs["mesh"][0], simplify=0.95, texture_size=1024
            )
            glb.export(glb_path)
            report["glb"] = glb_path
        except Exception as e:  # noqa: BLE001
            report["glb"] = None
            report["erros"].append(f"glb_texturizado: {type(e).__name__}: {e}")
    else:
        report["glb"] = None

    report["tempo_total_s"] = round(time.time() - t_total0, 2)
    report["cuda_ok"] = True
    print("REPORT_JSON=" + json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        print(
            "REPORT_JSON="
            + json.dumps({"mode": "trellis", "erros": ["fatal: ver traceback acima"]})
        )
        sys.exit(1)
