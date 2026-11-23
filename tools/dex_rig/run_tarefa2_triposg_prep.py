#!/usr/bin/env python3
"""Gate de simetria + render 4 vistas + decimate 40k no mesh.obj do TripoSG (ordem do dono: TripoSG oficial)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
import trimesh

sys.path.insert(0, "/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia/tools/dex_rig")
from run_tarefa2_gate_and_render import eval_symmetry_and_topology, render_4views_wire_clay


def main() -> None:
    repo = Path("/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia")
    obj_a = repo / "work/dex_rig/cand_a_triposg/mesh.obj"
    ev = repo / "evidence/dex_rig"
    ev.mkdir(parents=True, exist_ok=True)

    rep_a = eval_symmetry_and_topology(obj_a, "A_TripoSG_front_official")
    rep_a["note_b_skipped"] = "Candidato B (Hunyuan3D-2mv multi-vista) pulado por ordem explícita do dono (2026-11-23): usar TripoSG + pipeline oficial 3dprinter-setup-ia."
    (ev / "simetria_a.json").write_text(json.dumps(rep_a, indent=2), encoding="utf-8")

    title = (
        f"TripoSG Official (front) | mirror={rep_a['mirror_distance_mean_pct_bbox']}% "
        f"| p95={rep_a['mirror_distance_p95_pct_bbox']}% | faces={rep_a['faces']} | wt={rep_a['watertight_after_repair']}"
    )
    render_4views_wire_clay(obj_a, ev / "render_a_triposg.png", title)
    print("SIMETRIA_A:", json.dumps(rep_a))

    mesh = trimesh.load(str(obj_a), force="mesh")
    m40 = mesh.simplify_quadric_decimation(face_count=40000)
    out40 = repo / "work/dex_rig/cand_a_triposg/mesh_40k.obj"
    m40.export(str(out40))
    print("DECIMATE_40K_OK:", len(m40.faces), "->", out40)


if __name__ == "__main__":
    main()
