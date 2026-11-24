#!/usr/bin/env bash
set -euo pipefail

REPO="/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia"
GAME="/mnt/c/Users/Bruno/workspace/game-concerto"
BRAIN="/mnt/c/Users/Bruno/.gemini/antigravity/brain/430e8586-6e41-4737-9ee8-884f505b33ac"
EV="$REPO/evidence/cs01"
WORK="$REPO/work/cs01"
UNIRIG_VENV="$HOME/.venvs/unirig"
export TRIPOSG_HOME="$HOME/tools/TripoSG"

mkdir -p "$EV" "$WORK"

# 1. Converte concepts 3D -> PNG e compoe o retrato nostalgico 2D da foto antiga (Dez + esposa)
~/.venvs/triposg/bin/python - <<PY
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

Image.open("$BRAIN/clockwork_music_box_concept_1795475884656.jpg").convert("RGB").save("$EV/cs01_prop_caixinha_musica.png")
Image.open("$BRAIN/time_machine_tarp_concept_1795475884738.jpg").convert("RGB").save("$EV/cs01_prop_maquina_coberta.png")

# Compoe retrato simples vintage sepia de Dez + esposa para o porta-retrato da bancada
W, H = 512, 640
bg = Image.new("RGB", (W, H), (226, 204, 170))
dr = ImageDraw.Draw(bg)
# Fundo quente de oficina/jardim ao entardecer
for y in range(H):
    t = y / float(H)
    c = (int(235 - 55 * t), int(208 - 65 * t), int(168 - 62 * t))
    dr.line([(0, y), (W, y)], fill=c)

# Cola busto do Dez (esquerda) recortado de dex_front.png
dex_im = Image.open("$REPO/evidence/dex_rig/preproc/dex_front.png").convert("RGBA")
arr = np.asarray(dex_im)
# Mascara fundo branco
mask = ~((arr[...,0] > 235) & (arr[...,1] > 235) & (arr[...,2] > 235))
ys, xs = np.where(mask)
crop_dex = dex_im.crop((int(xs.min()), int(ys.min()), int(xs.max()), int(ys.min() + (ys.max()-ys.min())*0.58)))
# Aplica transparencia no branco
cd = np.asarray(crop_dex).copy()
bg_m = (cd[...,0] > 232) & (cd[...,1] > 232) & (cd[...,2] > 232)
cd[bg_m, 3] = 0
crop_dex = Image.fromarray(cd, "RGBA").resize((270, 290), Image.LANCZOS)

# Cria retrato caloroso da esposa ao lado (direita) usando Vo Segunda/Juno em tom pessego-coral suave
wife_im = Image.open("$REPO/evidence/npcs/npc_vo_segunda.png").convert("RGBA")
wa = np.asarray(wife_im)
wmask = ~((wa[...,0] > 235) & (wa[...,1] > 235) & (wa[...,2] > 235))
wys, wxs = np.where(wmask)
crop_w = wife_im.crop((int(wxs.min()), int(wys.min()), int(wxs.max()), int(wys.min() + (wys.max()-wys.min())*0.56)))
cw = np.asarray(crop_w).copy()
wbg = (cw[...,0] > 232) & (cw[...,1] > 232) & (cw[...,2] > 232)
cw[wbg, 3] = 0
crop_w = Image.fromarray(cw, "RGBA").resize((250, 280), Image.LANCZOS)

bg.paste(crop_dex, (28, 220), crop_dex)
bg.paste(crop_w, (238, 232), crop_w)

# Aplica tom sepia nostalgico + vinheta suave + borda de foto antiga
arr_f = np.asarray(bg, dtype=np.float32) / 255.0
luma = arr_f[...,0]*0.30 + arr_f[...,1]*0.59 + arr_f[...,2]*0.11
sepia = np.stack([
    np.clip(arr_f[...,0]*0.55 + luma*0.52 + 0.05, 0, 1),
    np.clip(arr_f[...,1]*0.50 + luma*0.44 + 0.02, 0, 1),
    np.clip(arr_f[...,2]*0.42 + luma*0.33, 0, 1),
], axis=-1)
yy, xx = np.mgrid[0:H, 0:W]
r2 = ((xx - W*0.5)/(W*0.55))**2 + ((yy - H*0.48)/(H*0.55))**2
vig = np.clip(1.0 - 0.42 * r2, 0.45, 1.0)[..., None]
rng = np.random.default_rng(7)
grain = rng.normal(0, 0.022, sepia.shape)
final = np.clip(sepia * vig + grain, 0, 1)
out_im = Image.fromarray((final * 255).astype(np.uint8), "RGB")
d2 = ImageDraw.Draw(out_im)
d2.rectangle([0, 0, W-1, H-1], outline=(235, 222, 198), width=18)
out_im.save("$GAME/unity/Assets/Game/Art/Textures/Cutscenes/cs01_foto_dez_esposa.png")
print("CS01_CONCEPTS_AND_PHOTO_OK")
PY

# 2. Gera os 2 props 3D EXCLUSIVAMENTE via TripoSG + PBR 4K Oficial
declare -A TRIS=(
  ["cs01_prop_caixinha_musica"]=4500
  ["cs01_prop_maquina_coberta"]=7000
)

for SLUG in cs01_prop_caixinha_musica cs01_prop_maquina_coberta; do
  echo "=== [CS01 FACTORY] $SLUG (TripoSG + PBR 4K) ==="
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
  "qa": { "lap_min": 500.0, "patch_max_pct": 0.25, "sat_min_pct": 3.0, "sat_max_pct": 98.0 },
  "notes": "Cutscene 1 prop ($SLUG) — EXCLUSIVAMENTE TripoSG."
}
JSON

  if [ ! -f "$GLB" ]; then
    cd "$REPO"
    /home/bruno/.venvs/hunyuan/bin/python pipeline/run_asset.py \
      --config "$CFG" --out "$W/pbr_out"
  fi

  # Exporta FBX solido (remove_doubles ANTES do Decimate) + PBR + EmissionMask ciano!
  "$UNIRIG_VENV/bin/python" - <<PY || true
import os, json, struct, io, bpy, numpy as np
from PIL import Image
from mathutils import Vector

slug = "$SLUG"
glb_path = "$GLB"
target_tris = ${TRIS[$SLUG]}
out_art = "$GAME/unity/Assets/Game/Art/Generated/cs01"
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
    cs = np.clip((np.minimum(g, b) - r * 1.25 - 0.30) / 0.25, 0.0, 1.0)
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
if len(obj.data.polygons) > target_tris:
    dec = obj.modifiers.new(name="DecSolid", type="DECIMATE")
    dec.ratio = float(target_tris) / float(len(obj.data.polygons))
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
print(f"CS01_FBX_OK {slug}: polys={len(obj.data.polygons)} -> {fbx_out}")
PY
done

echo "ALL_CS01_PROPS_READY"
