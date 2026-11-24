#!/usr/bin/env bash
set -euo pipefail

REPO="/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia"
GAME="/mnt/c/Users/Bruno/workspace/game-concerto"
W_VERA="$REPO/work/sector/npc_engenheira_vera"
GLB_VERA="$W_VERA/pbr_out/staged_models/npc_engenheira_vera__pbr_4k.glb"
SKEL_VERA="$W_VERA/unirig_skel.fbx"
SKIN_VERA="$W_VERA/unirig_skin.fbx"
UNIRIG_VENV="$HOME/.venvs/unirig"
export PATH="$UNIRIG_VENV/bin:$PATH"

cd "$HOME/tools/UniRig"
if [ ! -f "$SKEL_VERA" ]; then
  bash launch/inference/generate_skeleton.sh --input "$GLB_VERA" --output "$SKEL_VERA" --seed 501
fi
if [ ! -f "$SKIN_VERA" ]; then
  bash launch/inference/generate_skin.sh --input "$SKEL_VERA" --output "$SKIN_VERA" --seed 501
fi

"$UNIRIG_VENV/bin/python" "$REPO/tools/npcs/build_solid_npc_humanoid.py" \
  "npc_engenheira_vera" "$GLB_VERA" "$SKIN_VERA" \
  "$GAME/unity/Assets/Game/Art/Generated/npcs/npc_engenheira_vera/npc_engenheira_vera_humanoid.fbx" \
  "$GAME/unity/Assets/Game/Materials/Fab3D" || true

ls -lh "$GAME/unity/Assets/Game/Art/Generated/npcs/npc_engenheira_vera/npc_engenheira_vera_humanoid.fbx"
