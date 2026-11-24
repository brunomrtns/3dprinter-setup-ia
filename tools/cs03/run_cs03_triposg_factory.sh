#!/usr/bin/env bash
set -euo pipefail

REPO="/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia"
GAME="/mnt/c/Users/Bruno/workspace/game-concerto"
WORK="$REPO/work/cs03"
EV="$REPO/evidence/cs03"
TRIPOSG_VENV="/home/bruno/.venvs/triposg"
UNIRIG_VENV="/home/bruno/.venvs/unirig"
HUNYUAN_VENV="/home/bruno/.venvs/hunyuan"
export TRIPOSG_HOME="/home/bruno/tools/TripoSG"

mkdir -p "$WORK" "$EV" "$GAME/unity/Assets/Game/Art/Generated/cs03" "$GAME/unity/Assets/Game/Materials/Fab3D" "$GAME/unity/Assets/Game/Audio/Cutscenes/CS03"

if [ ! -f "$EV/cs03_prop_bugiganga_quebrada.png" ]; then
echo "=== [1/3] Gerando concept 2D da bugiganga quebrada (SDXL-Turbo local) ==="
"$HUNYUAN_VENV/bin/python" - <<PY
import torch, os
from diffusers import AutoPipelineForText2Image

pipe = AutoPipelineForText2Image.from_pretrained(
    "stabilityai/sdxl-turbo", torch_dtype=torch.float16, variant="fp16", local_files_only=True
).to("cuda")
gen = torch.Generator("cuda").manual_seed(303)
img = pipe(
    prompt="small cracked broken antique brass alien clockwork trinket gadget with split glowing cyan core, stylized 3D game prop, studio lighting, pure white background, clean silhouette",
    num_inference_steps=4, guidance_scale=0.0, generator=gen, width=512, height=512
).images[0]
out = "$EV/cs03_prop_bugiganga_quebrada.png"
img.save(out)
print("CONCEPT_OK:", out)
PY
fi

echo "=== [2/3] Gerando malha 3D EXCLUSIVAMENTE via TripoSG + PBR 4K ==="
SLUG="cs03_prop_bugiganga_quebrada"
W="$WORK/$SLUG"
mkdir -p "$W"
if [ ! -f "$W/mesh.obj" ]; then
  "$TRIPOSG_VENV/bin/python" "$REPO/tools/generator/triposg_runner.py" \
    --image "$EV/$SLUG.png" --output-dir "$W" --seed 303
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
  "notes": "Cutscene 3 broken trinket ($SLUG) — EXCLUSIVAMENTE TripoSG."
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
out_art = "$GAME/unity/Assets/Game/Art/Generated/cs03"
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
obj.location.z -= mn.z
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
fbx_out = os.path.join(out_art, f"{slug}.fbx")
bpy.ops.export_scene.fbx(filepath=fbx_out, use_selection=False, bake_anim=False, path_mode="AUTO")
print(f"CS03_TRINKET_FBX_OK: polys={len(obj.data.polygons)} -> {fbx_out}")
PY

echo "=== [3/3] Gerando audios TEMP da Cutscene 3 e Anomalia ==="
python3 - <<PY
import os, wave, struct, math, random
out_dir = "$GAME/unity/Assets/Game/Audio/Cutscenes/CS03"
sr = 44100

def save_wav(name, samples):
    path = os.path.join(out_dir, name)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(struct.pack("<" + "h"*len(samples), *samples))
    print("CS03_WAV_OK:", name)

# 1. Flash de retorno (1.8s: impacto branco -> silencio)
n = int(sr * 1.8)
s1 = []
for i in range(n):
    t = i / sr
    env = math.exp(-t * 3.8)
    v = (math.sin(2*math.pi*180*t)*0.5 + math.sin(2*math.pi*540*t)*0.25 + random.uniform(-0.3,0.3)) * env * 0.7
    s1.append(int(max(-0.98, min(0.98, v)) * 32767))
save_wav("cs03_flash_return_TEMP.wav", s1)

# 2. Zumbido grave persistente da maquina (12s loopavel — sem musica, so o zumbido!)
n = int(sr * 12.0)
s2 = []
for i in range(n):
    t = i / sr
    lfo = 0.82 + 0.18 * math.sin(2*math.pi*0.5*t)
    v = (math.sin(2*math.pi*55*t)*0.52 + math.sin(2*math.pi*110.3*t)*0.26 + math.sin(2*math.pi*82.4*t)*0.16) * lfo * 0.72
    s2.append(int(max(-0.98, min(0.98, v)) * 32767))
save_wav("cs03_machine_hum_loop_TEMP.wav", s2)

# 3. Som errado vindo do canto (anomalia 4: notas da caixinha com pitch/tempo errados + reverso!)
n = int(sr * 6.0)
s3 = []
notes = [523.25, 493.88, 392.00, 440.00]
for i in range(n):
    t = i / sr
    step = int(t / 1.5) % len(notes)
    lt = t % 1.5
    # Envelope invertido (cresce e corta seco = sensacao de audio ao contrario!)
    env = math.pow(lt / 1.5, 2.4) * (0.0 if lt > 1.44 else 1.0)
    detune = 1.0 + 0.06 * math.sin(2*math.pi*2.3*t)
    f = notes[step] * 0.72 * detune
    v = (math.sin(2*math.pi*f*t)*0.55 + math.sin(2*math.pi*f*2.01*t)*0.22) * env * 0.65
    s3.append(int(max(-0.98, min(0.98, v)) * 32767))
save_wav("cs03_anomaly_wrong_sound_TEMP.wav", s3)
PY

echo "ALL_CS03_ASSETS_READY"
