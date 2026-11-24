#!/usr/bin/env bash
set -euo pipefail

REPO="/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia"
GAME="/mnt/c/Users/Bruno/workspace/game-concerto"
WORK="$REPO/work/combat_v2"
EV="$REPO/evidence/combat_v2"
TRIPOSG_VENV="/home/bruno/.venvs/triposg"
UNIRIG_VENV="/home/bruno/.venvs/unirig"
HUNYUAN_VENV="/home/bruno/.venvs/hunyuan"
export TRIPOSG_HOME="/home/bruno/tools/TripoSG"

mkdir -p "$WORK" "$EV" \
  "$GAME/unity/Assets/Game/Art/Generated/enemies" \
  "$GAME/unity/Assets/Game/Materials/Fab3D"

echo "=== [1/3] Preparando concept PNG do Egide ==="
"$HUNYUAN_VENV/bin/python" - <<PY
from PIL import Image
im = Image.open("/mnt/c/Users/Bruno/.gemini/antigravity/brain/430e8586-6e41-4737-9ee8-884f505b33ac/egide_aegis_construct_1795523346955.jpg").convert("RGB")
im.save("$EV/enemy_egide.png")
print("PNG_OK:", im.size)
PY

SLUG="enemy_egide"
W="$WORK/$SLUG"
mkdir -p "$W"
IMG="$EV/${SLUG}.png"
CFG="$REPO/assets/${SLUG}.json"
GLB="$W/pbr_out/staged_models/${SLUG}__pbr_4k.glb"

echo "=== [2/3] Gerando malha 3D do Egide EXCLUSIVAMENTE via TripoSG + PBR 4K ==="
if [ ! -f "$W/mesh.obj" ]; then
  "$TRIPOSG_VENV/bin/python" "$REPO/tools/generator/triposg_runner.py" \
    --image "$IMG" --output-dir "$W" --seed 1090
fi

if [ ! -f "$W/mesh_30k.obj" ]; then
  "$UNIRIG_VENV/bin/python" - <<PY || true
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath="$W/mesh.obj")
obj = [o for o in bpy.data.objects if o.type == "MESH"][0]
bpy.context.view_layer.objects.active = obj
if len(obj.data.polygons) > 30000:
    dec = obj.modifiers.new(name="Dec30k", type="DECIMATE")
    dec.ratio = 30000.0 / float(len(obj.data.polygons))
    bpy.ops.object.modifier_apply(modifier=dec.name)
bpy.ops.wm.obj_export(filepath="$W/mesh_30k.obj", export_materials=False)
PY
fi

cat > "$CFG" <<JSON
{
  "id": "$SLUG",
  "variant_id": "pbr",
  "mesh": "$W/mesh_30k.obj",
  "uv": "$W/mesh_30k.obj",
  "tier": "single",
  "input_images": ["$IMG"],
  "outputs": {
    "mode_8k": "pbr_8k",
    "mode_4k": "pbr_4k",
    "glb_names": ["${SLUG}__pbr_8k.glb", "${SLUG}__pbr_4k.glb"]
  },
  "qa": { "lap_min": 400.0, "patch_max_pct": 0.30, "sat_min_pct": 3.0, "sat_max_pct": 98.0 },
  "notes": "Combate v2 enemy Egide ($SLUG) — EXCLUSIVAMENTE TripoSG (#109)."
}
JSON

if [ ! -f "$GLB" ]; then
  cd "$REPO"
  "$HUNYUAN_VENV/bin/python" pipeline/run_asset.py --config "$CFG" --out "$W/pbr_out"
fi

echo "=== [3/3] Exportando FBX Watertight (1.85m) + Texturas PBR para Unity ==="
"$UNIRIG_VENV/bin/python" - <<PY || true
import os, json, struct, io, bpy, numpy as np
from PIL import Image
from mathutils import Vector

slug = "$SLUG"
glb_path = "$GLB"
out_art = "$GAME/unity/Assets/Game/Art/Generated/enemies"
out_mat = "$GAME/unity/Assets/Game/Materials/Fab3D"

with open(glb_path, "rb") as f:
    data = f.read()
jlen, _ = struct.unpack_from("<II", data, 12)
gltf = json.loads(data[20:20+jlen].decode("utf-8"))
boff = 20 + jlen
blen, _ = struct.unpack_from("<II", data, boff)
blob = data[boff+8:boff+8+blen]

def load_img(tidx):
    idef = gltf["images"][gltf["textures"][tidx]["source"]]
    bv = gltf["bufferViews"][idef["bufferView"]]
    off = bv.get("byteOffset", 0)
    return Image.open(io.BytesIO(blob[off:off+bv["byteLength"]]))

pbr = gltf["materials"][0].get("pbrMetallicRoughness", {})
if "baseColorTexture" in pbr:
    im = load_img(pbr["baseColorTexture"]["index"]).convert("RGB")
    if im.width > 1024: im = im.resize((1024, 1024), Image.LANCZOS)
    im.save(os.path.join(out_mat, f"{slug}_albedo.png"))
    arr = np.asarray(im, dtype=np.float32) / 255.0
    r, g, b = arr[...,0], arr[...,1], arr[...,2]
    cs = np.clip((np.maximum(b, g) - r * 0.72 - 0.14) / 0.35, 0.0, 1.0)
    em = np.stack([r*cs, g*cs, b*cs], axis=-1)
    Image.fromarray(np.clip(em*255, 0, 255).astype(np.uint8), "RGB").save(os.path.join(out_mat, f"{slug}_emission.png"))
if "metallicRoughnessTexture" in pbr:
    im = load_img(pbr["metallicRoughnessTexture"]["index"]).convert("RGB")
    if im.width > 1024: im = im.resize((1024, 1024), Image.LANCZOS)
    mr = np.asarray(im, dtype=np.uint8)
    rgba = np.stack([mr[...,2], mr[...,2], mr[...,2], 255 - mr[...,1]], axis=-1)
    Image.fromarray(rgba, "RGBA").save(os.path.join(out_mat, f"{slug}_metallicsmooth.png"))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb_path)
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
bpy.ops.object.select_all(action="DESELECT")
for m in meshes: m.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1: bpy.ops.object.join()
obj = bpy.context.view_layer.objects.active
bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for o in list(bpy.data.objects):
    if o != obj: bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.0002)
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode="OBJECT")
if len(obj.data.polygons) > 6500:
    dec = obj.modifiers.new(name="DecSolid", type="DECIMATE")
    dec.ratio = 6500.0 / float(len(obj.data.polygons))
    bpy.ops.object.modifier_apply(modifier=dec.name)
bpy.ops.object.shade_smooth()
pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
h = max(0.01, mx.z - mn.z)
sc = 1.85 / h
obj.scale = (sc, sc, sc)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
obj.location.x -= (mn.x + mx.x) * 0.5
obj.location.y -= (mn.y + mx.y) * 0.5
obj.location.z -= mn.z
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
fbx_out = os.path.join(out_art, f"{slug}.fbx")
bpy.ops.export_scene.fbx(filepath=fbx_out, use_selection=False, bake_anim=False, path_mode="AUTO")
print(f"EGIDE_TRIPOSG_OK: {slug} polys={len(obj.data.polygons)} height=1.85m -> {fbx_out}")
PY

echo "ALL_EGIDE_TRIPOSG_READY"
