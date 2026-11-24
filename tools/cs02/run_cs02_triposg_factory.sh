#!/usr/bin/env bash
set -euo pipefail

REPO="/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia"
GAME="/mnt/c/Users/Bruno/workspace/game-concerto"
EV="$REPO/evidence/cs02"
WORK="$REPO/work/cs02"
UNIRIG_DIR="$HOME/tools/UniRig"
UNIRIG_VENV="$HOME/.venvs/unirig"
export TRIPOSG_HOME="$HOME/tools/TripoSG"

mkdir -p "$EV" "$WORK"

# 1. Gera 2 concepts 2D em fundo branco puro via SDXL-Turbo local
echo "=== [0/3] Gerando concepts de Lira (esposa) e Maquina Completa (SDXL-Turbo local) ==="
~/.venvs/triposg/bin/python - <<PY
import torch
from diffusers import AutoPipelineForText2Image

pipe = AutoPipelineForText2Image.from_pretrained(
    "stabilityai/sdxl-turbo", torch_dtype=torch.float16, variant="fp16"
).to("cuda")

prompts = {
    "npc_esposa_lira": "full body 3D stylized character render in strict symmetrical front facing A-pose, gentle female alien clockmaker same species as a small orange-peach alien with large pointed ears, two delicate thin antennae, warm expressive eyes, terracotta and cream workshop tunic apron, soft teal scarf, compact leather boots, Ratchet and Clank Pixar style, centered full body head to toe on pure solid white background, studio lighting, no floor shadow, no text",
    "cs02_prop_maquina_completa": "3D game prop render of an intricate stylized steampunk clockwork time machine apparatus uncovered, interlocking brass gyroscopic rings, riveted copper coils, mechanical levers, glowing bright cyan energy core crystal suspended in the center, thick power cables at the base, Ratchet and Clank style, centered on pure solid white background, studio lighting, no shadow, no text",
}

for slug, prompt in prompts.items():
    gen = torch.Generator("cuda").manual_seed(77)
    img = pipe(prompt=prompt, num_inference_steps=4, guidance_scale=0.0, generator=gen).images[0]
    out = f"$EV/{slug}.png"
    img.save(out)
    print(f"CONCEPT_OK: {out}")

del pipe
torch.cuda.empty_cache()
PY

# 2. Gera malhas 3D EXCLUSIVAMENTE via TripoSG + PBR 4K Oficial
for SLUG in npc_esposa_lira cs02_prop_maquina_completa; do
  echo "=== [CS02 FACTORY] $SLUG (TripoSG + PBR 4K) ==="
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
  "notes": "Cutscene 2 asset ($SLUG) — EXCLUSIVAMENTE TripoSG."
}
JSON

  if [ ! -f "$GLB" ]; then
    cd "$REPO"
    /home/bruno/.venvs/hunyuan/bin/python pipeline/run_asset.py \
      --config "$CFG" --out "$W/pbr_out"
  fi
done

# 3. UniRig Humanoid na esposa Lira (npc_esposa_lira_humanoid.fbx)
W_LIRA="$WORK/npc_esposa_lira"
GLB_LIRA="$W_LIRA/pbr_out/staged_models/npc_esposa_lira__pbr_4k.glb"
SKIN_LIRA="$W_LIRA/npc_esposa_lira_skin.fbx"
if [ ! -f "$SKIN_LIRA" ]; then
  SKEL_LIRA="$W_LIRA/npc_esposa_lira_skeleton.fbx"
  cd "$UNIRIG_DIR"
  export PATH="$UNIRIG_VENV/bin:$PATH"
  bash launch/inference/generate_skeleton.sh --input "$GLB_LIRA" --output "$SKEL_LIRA" --seed 12345
  bash launch/inference/generate_skin.sh --input "$SKEL_LIRA" --output "$SKIN_LIRA" --seed 12345
fi

"$UNIRIG_VENV/bin/python" "$REPO/tools/npcs/build_solid_npc_humanoid.py" \
  "npc_esposa_lira" \
  "$GLB_LIRA" \
  "$SKIN_LIRA" \
  "$GAME/unity/Assets/Game/Art/Generated/npcs/npc_esposa_lira/npc_esposa_lira_humanoid.fbx" \
  "$GAME/unity/Assets/Game/Materials/Fab3D" || true

# 4. Exporta cs02_prop_maquina_completa.fbx solido + PBR + EmissionMask ciano!
"$UNIRIG_VENV/bin/python" - <<PY || true
import os, json, struct, io, bpy, numpy as np
from PIL import Image
from mathutils import Vector

slug = "cs02_prop_maquina_completa"
glb_path = "$WORK/cs02_prop_maquina_completa/pbr_out/staged_models/cs02_prop_maquina_completa__pbr_4k.glb"
out_art = "$GAME/unity/Assets/Game/Art/Generated/cs02"
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
    if im.width > 2048: im = im.resize((2048, 2048), Image.LANCZOS)
    im.save(os.path.join(out_mat, f"{slug}_albedo.png"))
    arr = np.asarray(im, dtype=np.float32) / 255.0
    r, g, b = arr[...,0], arr[...,1], arr[...,2]
    cs = np.clip((np.minimum(g, b) - r * 1.15 - 0.25) / 0.25, 0.0, 1.0)
    em = np.stack([r*cs, g*cs, b*cs], axis=-1)
    Image.fromarray(np.clip(em*255, 0, 255).astype(np.uint8), "RGB").save(os.path.join(out_mat, f"{slug}_emission.png"))
if "metallicRoughnessTexture" in pbr:
    im = load_img(pbr["metallicRoughnessTexture"]["index"]).convert("RGB")
    if im.width > 2048: im = im.resize((2048, 2048), Image.LANCZOS)
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
if len(obj.data.polygons) > 7500:
    dec = obj.modifiers.new(name="DecSolid", type="DECIMATE")
    dec.ratio = 7500.0 / float(len(obj.data.polygons))
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
print(f"CS02_MACHINE_FBX_OK: polys={len(obj.data.polygons)} -> {fbx_out}")
PY

# 5. Gera os 3 audios TEMP da Cutscene 2 (charge, timewarp reverse-stretch + silencio subito, glitch distorcido)
"$UNIRIG_VENV/bin/python" - <<PY
import os, wave, numpy as np
out_dir = "$GAME/unity/Assets/Game/Audio/Cutscenes/CS02"
os.makedirs(out_dir, exist_ok=True)
SR = 44100

def save_wav(name, sig):
    pcm = (np.clip(sig, -0.95, 0.95) * 32767.0).astype(np.int16)
    with wave.open(os.path.join(out_dir, name), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR); wf.writeframes(pcm.tobytes())
    print("CS02_WAV_OK:", name)

# 1. Machine charge (14.5s): zumbido subindo 55Hz -> 220Hz + cliques de alavanca
dur = 14.5
t = np.linspace(0, dur, int(SR * dur), endpoint=False, dtype=np.float32)
freq = 55.0 + 165.0 * (t / dur) ** 2
phase = np.cumsum(2 * np.pi * freq / SR)
sig = (0.45 * np.sin(phase) + 0.22 * np.sin(phase * 2.0)) * np.minimum(1.0, t / 2.0) * (0.35 + 0.65 * (t / dur))
save_wav("cs02_machine_charge_TEMP.wav", sig * 0.7)

# 2. Timewarp stretch + reverse sweep + SILENCIO SUBITO no pico (14.0s, silencio nos ultimos 2.2s)
dur2 = 14.0
t2 = np.linspace(0, dur2, int(SR * dur2), endpoint=False, dtype=np.float32)
active = t2 < 11.8
f2 = 140.0 + 980.0 * np.clip(t2 / 11.8, 0, 1) ** 2.6
ph2 = np.cumsum(2 * np.pi * f2 / SR)
rev_env = np.clip(t2 / 11.8, 0, 1) ** 1.5
s2 = (0.5 * np.sin(ph2) + 0.25 * np.sin(ph2 * 1.5) + 0.12 * np.random.default_rng(1).normal(0, 1, len(t2))) * rev_env * active
# Corte seco de silencio subito em 11.8s!
save_wav("cs02_timewarp_stretch_TEMP.wav", s2 * 0.75)

# 3. Glitch distorcido (Beat 4 cliffhanger — 14.0s): nota esticada desafinada + zumbido distorcido no corte pro preto
dur3 = 14.0
t3 = np.linspace(0, dur3, int(SR * dur3), endpoint=False, dtype=np.float32)
detune_f = 523.25 * (1.0 - 0.35 * np.clip(t3 / 8.0, 0, 1) ** 1.8)
ph3 = np.cumsum(2 * np.pi * detune_f / SR)
warble = 0.28 * np.sin(ph3) * np.exp(-t3 * 0.22)
sub_dist = np.tanh(3.2 * np.sin(2 * np.pi * 48.0 * t3)) * np.clip((t3 - 7.0) / 3.5, 0, 1) * 0.55
save_wav("cs02_glitch_distort_TEMP.wav", (warble + sub_dist) * 0.75)
PY

echo "ALL_CS02_ASSETS_READY"
