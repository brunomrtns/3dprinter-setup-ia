#!/usr/bin/env python3
"""CLI da Forja.

  python -m forja repair <input.obj> -o out.stl [--target-height 100 ...]
  python -m forja batch benchmark/ -o forja_out/ [--target-height 100] [--glob '*/trellis/*.obj']
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

from . import pipeline, render as forja_render
from .report import salvar


def cmd_repair(a) -> int:
    rel = pipeline.reparar(
        entrada=a.input,
        saida_stl=a.output,
        target_height_mm=a.target_height,
        smooth_iter=a.smooth,
        voxel=a.voxel,
        max_tris=a.max_tris,
        keep_all_components=a.keep_all_components,
        min_component_tris=a.min_component_tris,
    )
    out_dir = os.path.dirname(os.path.abspath(a.output))
    rep_path = os.path.join(out_dir, "forja_report.json")
    salvar(rel, rep_path)
    if not a.no_render:
        res = forja_render.render_par(a.input, rel["saida"], out_dir, "caso")
        rel["renders"] = res
        salvar(rel, rep_path)
    fin = rel["final"]
    print(f"FORJA_OK wt={fin['watertight']} winding={fin['winding_consistent']} "
          f"tris={fin['triangulos']} bbox_mm={fin['bbox_mm']} report={rep_path}")
    return 0


def cmd_batch(a) -> int:
    padrao = os.path.join(a.root, a.glob)
    casos = sorted(glob.glob(padrao))
    if not casos:
        print(f"nenhum caso para {padrao}", file=sys.stderr)
        return 1
    indice = {"raiz": a.root, "padrao": a.glob, "casos": []}
    for caminho in casos:
        caso = os.path.basename(os.path.dirname(os.path.dirname(caminho)))  # benchmark/<caso>/<modo>/mesh.obj
        out_dir = os.path.join(a.out, caso)
        stl = os.path.join(out_dir, "forja.stl")
        print(f"===== {caso} =====", flush=True)
        try:
            rel = pipeline.reparar(
                entrada=caminho, saida_stl=stl,
                target_height_mm=a.target_height, smooth_iter=a.smooth,
                voxel=a.voxel, max_tris=a.max_tris,
                keep_all_components=a.keep_all_components,
                min_component_tris=a.min_component_tris,
            )
            salvar(rel, os.path.join(out_dir, "forja_report.json"))
            if not a.no_render:
                rel["renders"] = forja_render.render_par(caminho, rel["saida"], out_dir, caso)
                salvar(rel, os.path.join(out_dir, "forja_report.json"))
            fin = rel["final"]
            item = {"caso": caso, "ok": True, "antes": rel["etapas"][0]["antes"], "final": fin,
                    "avisos": rel["avisos"], "stl": stl,
                    "renders": rel.get("renders", {})}
        except Exception as e:  # noqa: BLE001
            item = {"caso": caso, "ok": False, "erro": f"{type(e).__name__}: {e}"}
        indice["casos"].append(item)
        print(f"BATCH_ITEM {caso} ok={item['ok']}")
    salvar(indice, os.path.join(a.out, "forja_index.json"))
    ok = sum(1 for c in indice["casos"] if c["ok"])
    print(f"BATCH_FIM {ok}/{len(indice['casos'])} ok — {os.path.join(a.out, 'forja_index.json')}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="forja")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("repair")
    pr.add_argument("input")
    pr.add_argument("-o", "--output", required=True, help="saída .stl")
    pr.add_argument("--target-height", type=float, default=None, help="mm da maior dimensão")
    pr.add_argument("--smooth", type=int, default=0)
    pr.add_argument("--voxel", type=float, default=None, help="remesh voxel (unidades da malha no momento da etapa)")
    pr.add_argument("--max-tris", type=int, default=None)
    pr.add_argument("--keep-all-components", action="store_true")
    pr.add_argument("--min-component-tris", type=int, default=50)
    pr.add_argument("--no-render", action="store_true")
    pr.set_defaults(fn=cmd_repair)

    bt = sub.add_parser("batch")
    bt.add_argument("root")
    bt.add_argument("-o", "--out", required=True)
    bt.add_argument("--glob", default="*/trellis/mesh.obj")
    bt.add_argument("--target-height", type=float, default=None)
    bt.add_argument("--smooth", type=int, default=0)
    bt.add_argument("--voxel", type=float, default=None)
    bt.add_argument("--max-tris", type=int, default=None)
    bt.add_argument("--keep-all-components", action="store_true")
    bt.add_argument("--min-component-tris", type=int, default=50)
    bt.add_argument("--no-render", action="store_true")
    bt.set_defaults(fn=cmd_batch)

    a = p.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
