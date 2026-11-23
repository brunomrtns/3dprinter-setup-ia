#!/usr/bin/env bash
set -euo pipefail

REPO="/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia"
GAME="/mnt/c/Users/Bruno/workspace/game-concerto"
BRAIN="/mnt/c/Users/Bruno/.gemini/antigravity/brain/430e8586-6e41-4737-9ee8-884f505b33ac"
EV="$REPO/evidence/npcs"
WORK="$REPO/work/npcs"
UNIRIG_DIR="$HOME/tools/UniRig"
UNIRIG_VENV="$HOME/.venvs/unirig"
export TRIPOSG_HOME="$HOME/tools/TripoSG"

mkdir -p "$EV" "$WORK"

declare -A SRC_IMAGES=(
  ["npc_tio_horario"]="$BRAIN/tio_horario_apose_concept_1795471725608.jpg"
  ["npc_vo_segunda"]="$BRAIN/vo_segunda_concept_apose_v2_1795471750364.jpg"
  ["npc_juno"]="$BRAIN/juno_concept_apose_v2_1795471750641.jpg"
  ["npc_mecanico_brito"]="$BRAIN/brito_character_apose_1795471730561.jpg"
  ["npc_analista_luma"]="$BRAIN/luma_alien_inspector_apose_purewhite_1795471754854.jpg"
)

NPCS=("npc_juno" "npc_mecanico_brito" "npc_tio_horario" "npc_vo_segunda" "npc_analista_luma")

for SLUG in "${NPCS[@]}"; do
  echo "============================================================"
  echo "=== [NPC FACTORY] Processando: $SLUG (TripoSG + PBR + UniRig) ==="
  echo "============================================================"
  W="$WORK/$SLUG"
  mkdir -p "$W"
  IMG_PNG="$EV/${SLUG}.png"
  CFG_JSON="$REPO/assets/${SLUG}.json"
  GLB_4K="$W/pbr_out/staged_models/${SLUG}__pbr_4k.glb"
  SKIN_FBX="$W/${SLUG}_skin.fbx"
  OUT_FBX="$GAME/unity/Assets/Game/Art/Generated/npcs/$SLUG/${SLUG}_humanoid.fbx"
  OUT_MAT="$GAME/unity/Assets/Game/Materials/Fab3D"

  if [ -f "$OUT_FBX" ]; then
    echo "SKIP $SLUG: $OUT_FBX ja existe!"
    continue
  fi

  # 1. Converte concept JPG -> PNG
  ~/.venvs/triposg/bin/python -c "from PIL import Image; Image.open('${SRC_IMAGES[$SLUG]}').convert('RGB').save('$IMG_PNG')"

  # 2. Gera malha 3D EXCLUSIVAMENTE via TripoSG!
  if [ ! -f "$W/mesh.obj" ]; then
    ~/.venvs/triposg/bin/python "$REPO/tools/generator/triposg_runner.py" \
      --image "$IMG_PNG" \
      --output-dir "$W" \
      --seed 42
  fi

  # 3. Decima para 30k faces
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
print("DEC30K_OK $SLUG")
PY
  fi

  # 4. Cria config JSON e roda Pipeline PBR Oficial (Hunyuan3D-Paint + TRELLIS.2 PBR + pack_glb)
  cat > "$CFG_JSON" <<JSON
{
  "id": "$SLUG",
  "variant_id": "pbr",
  "mesh": "$W/mesh_30k.obj",
  "uv": "$W/mesh_30k.obj",
  "tier": "single",
  "input_images": ["$IMG_PNG"],
  "outputs": {
    "mode_8k": "pbr_8k",
    "mode_4k": "pbr_4k",
    "glb_names": ["${SLUG}__pbr_8k.glb", "${SLUG}__pbr_4k.glb"]
  },
  "qa": { "lap_min": 500.0, "patch_max_pct": 0.25, "sat_min_pct": 3.0, "sat_max_pct": 98.0 },
  "notes": "NPC alienigena inteligente ($SLUG) — motor de forma EXCLUSIVAMENTE TripoSG."
}
JSON

  if [ ! -f "$GLB_4K" ]; then
    cd "$REPO"
    /home/bruno/.venvs/hunyuan/bin/python pipeline/run_asset.py \
      --config "$CFG_JSON" \
      --out "$W/pbr_out"
  fi

  # 5. UniRig Neural Auto-Rig (esqueleto + skinning neural) no GLB PBR!
  if [ ! -f "$SKIN_FBX" ]; then
    SKEL_FBX="$W/${SLUG}_skeleton.fbx"
    cd "$UNIRIG_DIR"
    export PATH="$UNIRIG_VENV/bin:$PATH"
    bash launch/inference/generate_skeleton.sh --input "$GLB_4K" --output "$SKEL_FBX" --seed 12345
    bash launch/inference/generate_skin.sh --input "$SKEL_FBX" --output "$SKIN_FBX" --seed 12345
  fi

  # 6. Constroi FBX Humanoid 100% solido + extrai texturas PBR + EmissionMask para o Unity!
  "$UNIRIG_VENV/bin/python" "$REPO/tools/npcs/build_solid_npc_humanoid.py" \
    "$SLUG" "$GLB_4K" "$SKIN_FBX" "$OUT_FBX" "$OUT_MAT" || true

  test -f "$OUT_FBX" && echo "=== DONE: $OUT_FBX ==="
done

echo "ALL_5_ALIEN_NPCS_READY"
