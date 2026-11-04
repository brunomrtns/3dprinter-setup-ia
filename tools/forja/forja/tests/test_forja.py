#!/usr/bin/env python3
"""Testes sintéticos — malhas quebradas de propósito + asserts.

Roda: python -m forja.tests.test_forja
"""
import os
import tempfile

import numpy as np
import trimesh

from forja import pipeline


def esfera_com_furo() -> trimesh.Trimesh:
    m = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    mascara = np.ones(len(m.faces), dtype=bool)
    mascara[:30] = False  # abre um buraco
    return trimesh.Trimesh(vertices=m.vertices, faces=m.faces[mascara], process=False)


def cubo_com_face_invertida() -> trimesh.Trimesh:
    m = trimesh.creation.box(extents=(1, 1, 1))
    f = m.faces.copy()
    f[0] = f[0][::-1]  # inverte winding de uma face
    return trimesh.Trimesh(vertices=m.vertices, faces=f, process=False)


def dois_componentes_com_lixo() -> trimesh.Trimesh:
    bola = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    lixo = trimesh.creation.icosphere(subdivisions=1, radius=0.05)
    lixo.apply_translation([5, 5, 5])
    return trimesh.util.concatenate([bola, lixo])


def run(nome: str, malha: trimesh.Trimesh, checks) -> None:
    with tempfile.TemporaryDirectory() as td:
        inp = os.path.join(td, "in.obj")
        out = os.path.join(td, "out.stl")
        malha.export(inp)
        rel = pipeline.reparar(inp, out, target_height_mm=100)
        verif = trimesh.load(out, force="mesh")
        for desc, fn in checks:
            ok, info = fn(verif, rel)
            status = "PASS" if ok else "FAIL"
            print(f"  [{status}] {nome}: {desc} {info}")
            assert ok, f"{nome}: {desc} falhou"
    print(f"TESTE {nome}: OK")


def main() -> int:
    print("== forja: testes sintéticos ==")
    run(
        "esfera_com_furo",
        esfera_com_furo(),
        [
            ("watertight", lambda v, r: (v.is_watertight, "")),
            ("is_volume", lambda v, r: (v.is_volume, "")),
            ("escala 100mm", lambda v, r: (abs(max(v.extents) - 100) < 1.0, f"bbox={v.extents}")),
        ],
    )
    run(
        "cubo_face_invertida",
        cubo_com_face_invertida(),
        [
            ("winding_consistent", lambda v, r: (v.is_winding_consistent, "")),
            ("volume positivo", lambda v, r: (v.volume > 0, f"vol={v.volume:.2f}")),
        ],
    )
    run(
        "dois_componentes",
        dois_componentes_com_lixo(),
        [
            ("watertight", lambda v, r: (v.is_watertight, "")),
            ("um componente", lambda v, r: (len(v.split(only_watertight=False)) == 1, "")),
            ("lixo descartado", lambda v, r: (abs(max(v.extents) - 100) < 1.0, f"bbox={v.extents}")),
        ],
    )
    print("== todos os testes passaram ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
