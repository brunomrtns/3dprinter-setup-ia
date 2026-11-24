#!/usr/bin/env bash
set -euo pipefail

REPO="/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia"
GAME="/mnt/c/Users/Bruno/workspace/game-concerto"
WORK="$REPO/work/repair"
EV="$REPO/evidence/repair"
TRIPOSG_VENV="/home/bruno/.venvs/triposg"
UNIRIG_VENV="/home/bruno/.venvs/unirig"
HUNYUAN_VENV="/home/bruno/.venvs/hunyuan"
export TRIPOSG_HOME="/home/bruno/tools/TripoSG"

mkdir -p "$WORK" "$EV" "$GAME/unity/Assets/Game/Art/Generated/repair" "$GAME/unity/Assets/Game/Materials/Fab3D" "$GAME/unity/Assets/Game/Audio/SFX/Repair"

SLUG="dez_repair_tool"
if [ ! -f "$EV/$SLUG.png" ]; then
echo "=== [1/3] Gerando concept 2D da ferramenta de reparo do Dez (SDXL-Turbo local) ==="
"$HUNYUAN_VENV/bin/python" - <<PY
import torch
from diffusers import AutoPipelineForText2Image

pipe = AutoPipelineForText2Image.from_pretrained(
    "stabilityai/sdxl-turbo", torch_dtype=torch.float16, variant="fp16", local_files_only=True
).to("cuda")
gen = torch.Generator("cuda").manual_seed(404)
img = pipe(
    prompt="stylized sci-fi alien brass and copper mechanic omni-wrench welder tool with glowing cyan energy prong tip, Ratchet and Clank game prop style, studio lighting, pure white background, clean silhouette",
    num_inference_steps=4, guidance_scale=0.0, generator=gen, width=512, height=512
).images[0]
out = "$EV/$SLUG.png"
img.save(out)
print("CONCEPT_OK:", out)
PY
fi

echo "=== [2/3] Gerando malha 3D EXCLUSIVAMENTE via TripoSG + PBR 4K ==="
W="$WORK/$SLUG"
mkdir -p "$W"
if [ ! -f "$W/mesh.obj" ]; then
  "$TRIPOSG_VENV/bin/python" "$REPO/tools/generator/triposg_runner.py" \
    --image "$EV/$SLUG.png" --output-dir "$W" --seed 404
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

cat > "$REPO/assets/$SLUG.json" <<JSON
{
  "id": "$SLUG",
  "variant_id": "pbr",
  "mesh": "$W/mesh_30k.obj",
  "uv": "$W/mesh_30k.obj",
  "tier": "single",
  "input_images": ["$EV/$SLUG.png"],
  "outputs": {
    "mode_8k": "pbr_8k",
    "mode_4k": "pbr_4k",
    "glb_names": ["${SLUG}__pbr_8k.glb", "${SLUG}__pbr_4k.glb"]
  },
  "qa": { "lap_min": 400.0, "patch_max_pct": 0.30, "sat_min_pct": 3.0, "sat_max_pct": 98.0 },
  "notes": "Dez alien mechanic repair tool ($SLUG) — EXCLUSIVAMENTE TripoSG."
}
JSON

GLB_OUT="$W/pbr_out/staged_models/${SLUG}__pbr_4k.glb"
if [ ! -f "$GLB_OUT" ]; then
  cd "$REPO"
  "$HUNYUAN_VENV/bin/python" pipeline/run_asset.py \
    --config "$REPO/assets/$SLUG.json" --out "$W/pbr_out"
fi

"$UNIRIG_VENV/bin/python" - <<PY || true
import os, json, struct, io, bpy, numpy as np
from PIL import Image
from mathutils import Vector

slug = "$SLUG"
glb_path = "$GLB_OUT"
out_art = "$GAME/unity/Assets/Game/Art/Generated/repair"
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
    cs = np.clip((np.minimum(g, b) - r * 1.15 - 0.25) / 0.25, 0.0, 1.0)
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
if len(obj.data.polygons) > 4500:
    dec = obj.modifiers.new(name="DecSolid", type="DECIMATE")
    dec.ratio = 4500.0 / float(len(obj.data.polygons))
    bpy.ops.object.modifier_apply(modifier=dec.name)
bpy.ops.object.shade_smooth()
pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
obj.location.x -= (mn.x + mx.x) * 0.5
obj.location.y -= (mn.y + mx.y) * 0.5
obj.location.z -= mn.z
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
fbx_out = os.path.join(out_art, f"{slug}.fbx")
bpy.ops.export_scene.fbx(filepath=fbx_out, use_selection=False, bake_anim=False, path_mode="AUTO")
print(f"REPAIR_TOOL_FBX_OK: polys={len(obj.data.polygons)} -> {fbx_out}")
PY

echo "=== [3/3] Gerando audios TEMP de Reparo e Beat Final do Ato 2 ==="
python3 - <<PY
import os, wave, struct, math, random
out_dir = "$GAME/unity/Assets/Game/Audio/SFX/Repair"
sr = 44100

def save_wav(name, samples):
    path = os.path.join(out_dir, name)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(struct.pack("<" + "h"*len(samples), *samples))
    print("REPAIR_WAV_OK:", name)

# 1. Som de ferramenta canalizando (loop 3.0s: zumbido harmonico mecanico agradavel)
n = int(sr * 3.0)
s1 = []
for i in range(n):
    t = i / sr
    pulse = 0.78 + 0.22 * math.sin(2*math.pi*4.0*t)
    v = (math.sin(2*math.pi*220*t)*0.35 + math.sin(2*math.pi*330*t)*0.22 + math.sin(2*math.pi*660*t)*0.12) * pulse * 0.58
    s1.append(int(max(-0.98, min(0.98, v)) * 32767))
save_wav("repair_tool_channel_TEMP.wav", s1)

# 2. Resolucao musical (1.4s: acorde limpo + motif cristalino de caixinha de musica!)
n = int(sr * 1.4)
s2 = []
chord = [523.25, 659.25, 783.99, 1046.50]
for i in range(n):
    t = i / sr
    v = 0.0
    for idx, f in enumerate(chord):
        dt = t - idx * 0.08
        if dt >= 0:
            env = math.exp(-dt * 3.2) * min(1.0, dt / 0.01)
            v += math.sin(2*math.pi*f*dt) * 0.24 * env
    s2.append(int(max(-0.98, min(0.98, v * 0.95)) * 32767))
save_wav("repair_resolve_chime_TEMP.wav", s2)

# 3. Bugiganga quebra SOZINHA no Beat Final (0.55s: estalo seco sem musica!)
n = int(sr * 0.55)
s3 = []
random.seed(99)
for i in range(n):
    t = i / sr
    snap = math.exp(-t * 32.0) * (random.uniform(-1.0, 1.0) * 0.85 + math.sin(2*math.pi*920*t)*0.4)
    crack2 = math.exp(-max(0.0, t - 0.07) * 24.0) * (0.0 if t < 0.07 else random.uniform(-0.7, 0.7))
    v = (snap + crack2) * 0.88
    s3.append(int(max(-0.98, min(0.98, v)) * 32767))
save_wav("act2_trinket_crack_TEMP.wav", s3)
PY

echo "ALL_REPAIR_ASSETS_READY"
