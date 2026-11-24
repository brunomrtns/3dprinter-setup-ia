#!/usr/bin/env bash
set -euo pipefail

REPO="/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia"
GAME="/mnt/c/Users/Bruno/workspace/game-concerto"
EV="$REPO/evidence/parts"
WORK="$REPO/work/parts"
UNIRIG_VENV="$HOME/.venvs/unirig"
export TRIPOSG_HOME="$HOME/tools/TripoSG"

mkdir -p "$EV" "$WORK"

# 1. Gera 3 concepts limpos em fundo branco puro via SDXL-Turbo local (cache HF)
echo "=== [0/3] Gerando 3 concepts 2D das pecas mecanicas (SDXL-Turbo local) ==="
~/.venvs/triposg/bin/python - <<PY
import torch
from diffusers import AutoPipelineForText2Image

pipe = AutoPipelineForText2Image.from_pretrained(
    "stabilityai/sdxl-turbo", torch_dtype=torch.float16, variant="fp16"
).to("cuda")

prompts = {
    "part_nucleo_ressonancia": "3D game prop render of a compact stylized steampunk clockwork brass sphere core with interlocking copper gyro rings and a glowing cyan energy crystal inside, Ratchet and Clank style, centered on pure solid white background, studio lighting, no shadow, no text",
    "part_bobina_fase": "3D game prop render of a compact stylized sci-fi copper induction coil cylinder with riveted dark iron flanges, brass bolts, and a glowing turquoise crystal rod in the center, Ratchet and Clank style, centered on pure solid white background, studio lighting, no shadow, no text",
    "part_regulador_crono": "3D game prop render of a compact stylized clockwork brass gear regulator device with copper pipes and a glowing cyan energy dial gauge, Ratchet and Clank style, centered on pure solid white background, studio lighting, no shadow, no text",
}

for slug, prompt in prompts.items():
    gen = torch.Generator("cuda").manual_seed(42)
    img = pipe(prompt=prompt, num_inference_steps=4, guidance_scale=0.0, generator=gen).images[0]
    out = f"$EV/{slug}.png"
    img.save(out)
    print(f"CONCEPT_OK: {out}")

del pipe
torch.cuda.empty_cache()
PY

# 2. Gera os 3 modelos 3D EXCLUSIVAMENTE via TripoSG + PBR 4K Oficial + FBX solidos!
for SLUG in part_nucleo_ressonancia part_bobina_fase part_regulador_crono; do
  echo "=== [PARTS FACTORY] $SLUG (TripoSG + PBR 4K) ==="
  W="$WORK/$SLUG"
  mkdir -p "$W"
  IMG="$EV/${SLUG}.png"
  CFG="$REPO/assets/${SLUG}.json"
  GLB="$W/pbr_out/staged_models/${SLUG}__pbr_4k.glb"

  if [ ! -f "$W/mesh.obj" ]; then
    ~/.venvs/triposg/bin/python "$REPO/tools/generator/triposg_runner.py" \
      --image "$IMG" --output-dir "$W" --seed 42
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
  "notes": "Peca mecanica coletavel ($SLUG) — EXCLUSIVAMENTE TripoSG."
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
out_art = "$GAME/unity/Assets/Game/Art/Generated/parts"
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
if len(obj.data.polygons) > 3500:
    dec = obj.modifiers.new(name="DecSolid", type="DECIMATE")
    dec.ratio = 3500.0 / float(len(obj.data.polygons))
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
print(f"PART_FBX_OK {slug}: polys={len(obj.data.polygons)} -> {fbx_out}")
PY
done

# 3. Gera os 2 SFX TEMP (pickup chime + Act 1 complete stinger)
"$UNIRIG_VENV/bin/python" - <<PY
import os, wave, numpy as np
out_dir = "$GAME/unity/Assets/Game/Audio/SFX/Parts"
os.makedirs(out_dir, exist_ok=True)
SR = 44100

def save_wav(name, sig):
    pcm = (np.clip(sig, -0.95, 0.95) * 32767.0).astype(np.int16)
    with wave.open(os.path.join(out_dir, name), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR); wf.writeframes(pcm.tobytes())
    print("SFX_OK:", name)

# Pickup chime: arpejo curto cristalino (E5 -> B5)
buf = np.zeros(int(SR * 0.65), dtype=np.float32)
for st, fr in [(0.0, 659.25), (0.09, 987.77)]:
    t = np.linspace(0, 0.5, int(SR * 0.5), endpoint=False, dtype=np.float32)
    s = (0.65*np.sin(2*np.pi*fr*t) + 0.25*np.sin(2*np.pi*fr*2*t)) * np.minimum(1, t/0.006) * np.exp(-t*6.5) * 0.55
    idx = int(st * SR)
    buf[idx:idx+len(s)] += s
save_wav("sfx_part_pickup_TEMP.wav", buf)

# Act 1 complete stinger: acorde resolvido quente (A4 -> C#5 -> E5 -> A5)
buf2 = np.zeros(int(SR * 2.8), dtype=np.float32)
for st, fr in [(0.0, 440.0), (0.14, 554.37), (0.28, 659.25), (0.45, 880.0)]:
    t = np.linspace(0, 2.2, int(SR * 2.2), endpoint=False, dtype=np.float32)
    s = (0.60*np.sin(2*np.pi*fr*t) + 0.22*np.sin(2*np.pi*fr*2*t)) * np.minimum(1, t/0.012) * np.exp(-t*1.6) * 0.45
    idx = int(st * SR)
    end = min(len(buf2), idx + len(s))
    buf2[idx:end] += s[:end-idx]
save_wav("sfx_act1_complete_stinger_TEMP.wav", buf2)
PY

echo "ALL_PARTS_TRIPOSG_AND_SFX_READY"
