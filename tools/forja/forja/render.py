#!/usr/bin/env python3
"""Render antes/depois 512px CPU — mesma câmera/luz do benchmark (render_preview.py)."""
import os
import subprocess
import tempfile

FORJA_DIR = os.path.dirname(os.path.abspath(__file__))


def render_par(antes_obj: str, depois_obj: str, out_dir: str, caso: str, res: int = 512) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    antes_png = os.path.join(out_dir, f"{caso}_antes.png")
    depois_png = os.path.join(out_dir, f"{caso}_depois.png")
    script = os.path.join(FORJA_DIR, "render_preview.py")
    resultado = {}
    with tempfile.TemporaryDirectory() as td:
        lixo = os.path.join(td, "descarte.png")
        for inp, out1 in ((antes_obj, antes_png), (depois_obj, depois_png)):
            r = subprocess.run(
                ["blender", "-b", "-P", script, "--", "--input", inp,
                 "--out1", out1, "--out2", lixo, "--res", str(res)],
                capture_output=True, text=True, timeout=1200,
            )
            resultado[out1] = "RENDER_OK" in r.stdout and os.path.isfile(out1)
    return resultado
