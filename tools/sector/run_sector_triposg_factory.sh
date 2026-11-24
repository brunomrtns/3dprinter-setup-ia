#!/usr/bin/env bash
set -euo pipefail

REPO="/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia"
GAME="/mnt/c/Users/Bruno/workspace/game-concerto"
WORK="$REPO/work/sector"
EV="$REPO/evidence/sector"
TRIPOSG_VENV="/home/bruno/.venvs/triposg"
UNIRIG_VENV="/home/bruno/.venvs/unirig"
HUNYUAN_VENV="/home/bruno/.venvs/hunyuan"
export TRIPOSG_HOME="/home/bruno/tools/TripoSG"

mkdir -p "$WORK" "$EV" \
  "$GAME/unity/Assets/Game/Art/Generated/npcs/npc_engenheira_vera" \
  "$GAME/unity/Assets/Game/Art/Generated/sector" \
  "$GAME/unity/Assets/Game/Materials/Fab3D" \
  "$GAME/unity/Assets/Game/Audio/SFX/Sector"

echo "=== [1/4] Gerando concepts 2D (SDXL-Turbo local): Vera + Gerador + Antena + Carga ==="
"$HUNYUAN_VENV/bin/python" - <<PY
import os, torch
from diffusers import AutoPipelineForText2Image

prompts = {
    "npc_engenheira_vera": (501, "full body A-pose stylized alien female sector chief engineer, same Lombax-like large ears species, dark slate teal armored coat with copper shoulder pads and visor goggles, calm tense expression, Pixar Ratchet style, pure white background, no shadow"),
    "sector_prop_gerador": (502, "stylized sci-fi alien industrial power generator reactor monolith with brass pipes and glowing cyan energy coils, heavy base, 3/4 view game prop, studio lighting, pure white background, clean silhouette"),
    "sector_prop_antena":  (503, "stylized sci-fi alien industrial communications relay antenna tower with copper dish and glowing cyan beacon tip, 3/4 view game prop, studio lighting, pure white background, clean silhouette"),
    "sector_prop_carga":   (504, "stylized sci-fi alien industrial heavy cargo container structure with reinforced dark steel frame and copper trim, 3/4 view game prop, studio lighting, pure white background, clean silhouette"),
}

missing = [k for k in prompts if not os.path.exists(f"$EV/{k}.png")]
if missing:
    pipe = AutoPipelineForText2Image.from_pretrained(
        "stabilityai/sdxl-turbo", torch_dtype=torch.float16, variant="fp16", local_files_only=True
    ).to("cuda")
    for slug in missing:
        seed, prompt = prompts[slug]
        gen = torch.Generator("cuda").manual_seed(seed)
        img = pipe(prompt=prompt, num_inference_steps=4, guidance_scale=0.0, generator=gen, width=512, height=512).images[0]
        img.save(f"$EV/{slug}.png")
        print("CONCEPT_OK:", slug)
    del pipe
    torch.cuda.empty_cache()
PY

echo "=== [2/4] Gerando malhas 3D EXCLUSIVAMENTE via TripoSG + PBR 4K ==="
for SLUG in npc_engenheira_vera sector_prop_gerador sector_prop_antena sector_prop_carga; do
  echo ">>> [TripoSG + PBR 4K] $SLUG"
  W="$WORK/$SLUG"
  mkdir -p "$W"
  IMG="$EV/${SLUG}.png"
  CFG="$REPO/assets/${SLUG}.json"
  GLB="$W/pbr_out/staged_models/${SLUG}__pbr_4k.glb"

  if [ ! -f "$W/mesh.obj" ]; then
    "$TRIPOSG_VENV/bin/python" "$REPO/tools/generator/triposg_runner.py" \
      --image "$IMG" --output-dir "$W" --seed 505
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
  "notes": "Setor Externo asset ($SLUG) — EXCLUSIVAMENTE TripoSG."
}
JSON

  if [ ! -f "$GLB" ]; then
    cd "$REPO"
    "$HUNYUAN_VENV/bin/python" pipeline/run_asset.py --config "$CFG" --out "$W/pbr_out"
  fi
done

echo "=== [3/4] UniRig Humanoid em npc_engenheira_vera + FBX Watertight nos 3 Props ==="
W_VERA="$WORK/npc_engenheira_vera"
GLB_VERA="$W_VERA/pbr_out/staged_models/npc_engenheira_vera__pbr_4k.glb"
SKEL_VERA="$W_VERA/unirig_skel.fbx"
SKIN_VERA="$W_VERA/unirig_skin.fbx"

if [ ! -f "$SKIN_VERA" ]; then
  cd /home/bruno/tools/UniRig
  bash launch/inference/generate_skeleton.sh --input "$GLB_VERA" --output "$SKEL_VERA" --seed 501
  bash launch/inference/generate_skin.sh     --input "$SKEL_VERA" --output "$SKIN_VERA" --seed 501
fi

"$UNIRIG_VENV/bin/python" "$REPO/tools/npcs/build_solid_npc_humanoid.py" \
  "npc_engenheira_vera" "$GLB_VERA" "$SKIN_VERA" \
  "$GAME/unity/Assets/Game/Art/Generated/npcs/npc_engenheira_vera/npc_engenheira_vera_humanoid.fbx" \
  "$GAME/unity/Assets/Game/Materials/Fab3D" || true

for SLUG in sector_prop_gerador sector_prop_antena sector_prop_carga; do
  GLB_P="$WORK/$SLUG/pbr_out/staged_models/${SLUG}__pbr_4k.glb"
  "$UNIRIG_VENV/bin/python" - <<PY || true
import os, json, struct, io, bpy, numpy as np
from PIL import Image
from mathutils import Vector

slug = "$SLUG"
glb_path = "$GLB_P"
out_art = "$GAME/unity/Assets/Game/Art/Generated/sector"
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
if len(obj.data.polygons) > 6500:
    dec = obj.modifiers.new(name="DecSolid", type="DECIMATE")
    dec.ratio = 6500.0 / float(len(obj.data.polygons))
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
print(f"SECTOR_PROP_OK: {slug} polys={len(obj.data.polygons)} -> {fbx_out}")
PY
done

echo "=== [4/4] Gerando audio ambiente frio/vento do Setor Externo ==="
python3 - <<PY
import os, wave, struct, math, random
out_dir = "$GAME/unity/Assets/Game/Audio/SFX/Sector"
sr = 44100
n = int(sr * 12.0)
random.seed(505)
lp = 0.0
samples = []
for i in range(n):
    t = i / sr
    # Vento frio filtrado + grave distante da rachadura no ceu
    w = random.uniform(-1.0, 1.0)
    lp = lp * 0.985 + w * 0.015
    gust = 0.55 + 0.45 * math.sin(2*math.pi*0.17*t)
    rift = math.sin(2*math.pi*46.0*t) * 0.14 + math.sin(2*math.pi*92.5*t) * 0.06
    v = max(-0.98, min(0.98, (lp * 6.5 * gust + rift) * 0.65))
    samples.append(int(v * 32767))
wav_path = os.path.join(out_dir, "sector_cold_wind_ambience_TEMP.wav")
with wave.open(wav_path, "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
    wf.writeframes(struct.pack("<" + "h"*len(samples), *samples))
print("SECTOR_WAV_OK:", wav_path)
PY

echo "ALL_SECTOR_ASSETS_READY"
