#!/usr/bin/env bash
set -euo pipefail

REPO="/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia"
GAME="/mnt/c/Users/Bruno/workspace/game-concerto"
EV="$REPO/evidence/missing_assets"
WORK="$REPO/work/missing_assets"
UNIRIG_VENV="$HOME/.venvs/unirig"
export TRIPOSG_HOME="$HOME/tools/TripoSG"

mkdir -p "$EV" "$WORK"

echo "=== [1/3] Gerando 5 concepts 2D em fundo branco puro (SDXL-Turbo local) ==="
~/.venvs/triposg/bin/python - <<PY
import torch
from diffusers import AutoPipelineForText2Image

pipe = AutoPipelineForText2Image.from_pretrained(
    "stabilityai/sdxl-turbo", torch_dtype=torch.float16, variant="fp16"
).to("cuda")

prompts = {
    "part_condensador_fluxo": "3D game prop render of a compact stylized steampunk brass flux capacitor module with twin copper coils, riveted dark steel housing, and a glowing cyan energy prism core, Ratchet and Clank style, centered on pure solid white background, studio lighting, no shadow, no text",
    "part_estabilizador_orbital": "3D game prop render of a compact stylized clockwork bronze orbital stabilizer gyroscope with three brass rings and a glowing turquoise crystal orb in the center, Ratchet and Clank style, centered on pure solid white background, studio lighting, no shadow, no text",
    "prop_fragmento_nucleo": "3D game prop render of a stylized sci-fi crystalline energy core shard encased in ornate dark bronze clockwork filigree with bright glowing cyan and gold veins, hero relic artifact, Ratchet and Clank style, centered on pure solid white background, studio lighting, no shadow, no text",
    "prop_celula_energia": "3D game prop render of a compact stylized sci-fi hexagonal energy battery canister with dark gunmetal brass endcaps and a bright glowing cyan plasma cylinder core, pickup item, Ratchet and Clank style, centered on pure solid white background, studio lighting, no shadow, no text",
    "prop_estacao_parry": "3D game prop render of a stylized steampunk bronze combat training totem pedestal with an octagonal brass shield emitter disc and glowing cyan energy rings on top, Ratchet and Clank style, centered on pure solid white background, studio lighting, no shadow, no text",
}

for slug, prompt in prompts.items():
    out = f"$EV/{slug}.png"
    gen = torch.Generator("cuda").manual_seed(1125)
    img = pipe(prompt=prompt, num_inference_steps=4, guidance_scale=0.0, generator=gen).images[0]
    img.save(out)
    print(f"CONCEPT_OK: {out}")

del pipe
torch.cuda.empty_cache()
PY

echo "=== [2/3] Gerando 5 modelos 3D EXCLUSIVAMENTE via TripoSG + PBR 4K + FBX ==="
declare -A OUT_SUBDIRS=(
  ["part_condensador_fluxo"]="parts"
  ["part_estabilizador_orbital"]="parts"
  ["prop_fragmento_nucleo"]="epicenter"
  ["prop_celula_energia"]="props"
  ["prop_estacao_parry"]="props"
)

for SLUG in part_condensador_fluxo part_estabilizador_orbital prop_fragmento_nucleo prop_celula_energia prop_estacao_parry; do
  echo "=== [MISSING ASSETS FACTORY] $SLUG (TripoSG + PBR 4K) ==="
  W="$WORK/$SLUG"
  mkdir -p "$W"
  IMG="$EV/${SLUG}.png"
  CFG="$REPO/assets/${SLUG}.json"
  GLB="$W/pbr_out/staged_models/${SLUG}__pbr_4k.glb"
  SUBDIR="${OUT_SUBDIRS[$SLUG]}"

  if [ ! -f "$W/mesh.obj" ]; then
    ~/.venvs/triposg/bin/python "$REPO/tools/generator/triposg_runner.py" \
      --image "$IMG" --output-dir "$W" --seed 1125
  fi

  if [ ! -f "$W/mesh_30k.obj" ]; then
    "$UNIRIG_VENV/bin/python" - <<PY || true
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath="$W/mesh.obj")
obj = [o for o in bpy.data.objects if o.type == "MESH"][0]
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
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
  "notes": "Asset 3D faltante ($SLUG) — EXCLUSIVAMENTE TripoSG."
}
JSON

  if [ ! -f "$GLB" ]; then
    cd "$REPO"
    /home/bruno/.venvs/hunyuan/bin/python pipeline/run_asset.py \
      --config "$CFG" --out "$W/pbr_out"
  fi

  "$UNIRIG_VENV/bin/python" - <<PY || true
import os, json, struct, io, bpy, numpy as np
from PIL import Image
from mathutils import Vector

slug = "$SLUG"
glb_path = "$GLB"
out_art = "$GAME/unity/Assets/Game/Art/Generated/$SUBDIR"
out_mat = "$GAME/unity/Assets/Game/Materials/Fab3D"
os.makedirs(out_art, exist_ok=True)
os.makedirs(out_mat, exist_ok=True)

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
    cs = np.clip((np.minimum(g, b) - r * 1.20 - 0.25) / 0.25, 0.0, 1.0)
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
if len(obj.data.polygons) > 4000:
    dec = obj.modifiers.new(name="DecSolid", type="DECIMATE")
    dec.ratio = 4000.0 / float(len(obj.data.polygons))
    bpy.ops.object.modifier_apply(modifier=dec.name)
bpy.ops.object.shade_smooth()
pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
obj.location.x -= (mn.x + mx.x) * 0.5
obj.location.y -= (mn.y + mx.y) * 0.5
obj.location.z -= (mn.z + mx.z) * 0.5
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
fbx_out = os.path.join(out_art, f"{slug}.fbx")
bpy.ops.export_scene.fbx(filepath=fbx_out, use_selection=False, bake_anim=False, path_mode="AUTO")
print(f"ASSET_FBX_OK {slug}: polys={len(obj.data.polygons)} -> {fbx_out}")
PY
done

echo "ALL_5_MISSING_ASSETS_TRIPOSG_READY"
