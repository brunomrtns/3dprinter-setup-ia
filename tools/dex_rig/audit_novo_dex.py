#!/usr/bin/env python3
"""Auditoria de simetria do modelo e esqueleto do hero_dex_humanoid.fbx (TAREFA 3)."""
import json
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

fbx = Path("/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Art/Generated/hero_dex/hero_dex_humanoid.fbx")
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=str(fbx))

mesh_obj = [o for o in bpy.data.objects if o.type == "MESH"][0]
arm_obj = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]
has_uv = len(mesh_obj.data.uv_layers) > 0

mw = mesh_obj.matrix_world
verts = np.array([list(mw @ v.co) for v in mesh_obj.data.vertices], dtype=np.float64)
vmin, vmax = verts.min(axis=0), verts.max(axis=0)
bbox = vmax - vmin
diag = float(np.linalg.norm(bbox))
height = float(max(bbox[1], bbox[2]))
cx = float((vmin[0] + vmax[0]) * 0.5)

# Amostra 2000 vertices (seed 42) para calculo em <0.2s
rng = np.random.default_rng(42)
vc = verts.copy()
vc[:, 0] -= cx
idx = rng.choice(len(vc), size=min(2000, len(vc)), replace=False)
sub = vc[idx]
mir = sub.copy()
mir[:, 0] *= -1.0
d2 = np.sum((mir[:, None, :] - sub[None, :, :]) ** 2, axis=2)
dists = np.sqrt(np.min(d2, axis=1))

aw = arm_obj.matrix_world
bpy.context.view_layer.objects.active = arm_obj
bpy.ops.object.mode_set(mode="EDIT")
eb = arm_obj.data.edit_bones
pairs = [
    ("LeftShoulder", "RightShoulder"),
    ("LeftUpperArm", "RightUpperArm"),
    ("LeftLowerArm", "RightLowerArm"),
    ("LeftHand", "RightHand"),
    ("LeftUpperLeg", "RightUpperLeg"),
    ("LeftLowerLeg", "RightLowerLeg"),
    ("LeftFoot", "RightFoot"),
]
skel = {}
max_asym = 0.0
for ln, rn in pairs:
    bl, br = eb.get(ln), eb.get(rn)
    if bl and br:
        pl, pr = aw @ bl.head, aw @ br.head
        err = Vector(((2.0 * cx - pl.x) - pr.x, pl.y - pr.y, pl.z - pr.z)).length / max(1e-6, height) * 100.0
        skel[f"{ln}_vs_{rn}"] = round(float(err), 3)
        max_asym = max(max_asym, float(err))
bpy.ops.object.mode_set(mode="OBJECT")

rep = {
    "model": str(fbx),
    "has_uv_layer": has_uv,
    "bones_total": len(arm_obj.data.bones),
    "mesh_mirror_mean_pct_bbox": round(float(dists.mean() / diag * 100.0), 3),
    "mesh_mirror_p95_pct_bbox": round(float(np.percentile(dists, 95) / diag * 100.0), 3),
    "skeleton_max_pair_asym_pct_height": round(max_asym, 3),
    "skeleton_symmetry_pass_lt_2pct": bool(max_asym < 2.0),
    "skeleton_pairs_pct": skel,
}
out = Path("/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia/evidence/dex_rig/audit_modelo_novo_dex.json")
out.write_text(json.dumps(rep, indent=2), encoding="utf-8")
print("AUDIT_NOVO_DEX:", json.dumps(rep))
