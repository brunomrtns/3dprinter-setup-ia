#!/usr/bin/env bash
set -euo pipefail

REPO="/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia"
PRE="$REPO/evidence/dex_rig/preproc"
OUT_A="$REPO/work/dex_rig/cand_a_triposg"
OUT_B="$REPO/work/dex_rig/cand_b_hy2mv"
mkdir -p "$OUT_A" "$OUT_B"

VRAM_LOG="$REPO/evidence/dex_rig/vram_tarefa2_shapes.csv"
echo "ts,used_mib" > "$VRAM_LOG"
( while true; do echo "$(date -Iseconds),$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)" >> "$VRAM_LOG"; sleep 2; done ) &
VPID=$!
trap 'kill $VPID 2>/dev/null || true' EXIT

echo "=== [2A-1] Candidate A: TripoSG (front, seed 42) ==="
TRIPOSG_HOME=/home/bruno/tools/TripoSG /home/bruno/.venvs/triposg/bin/python \
  "$REPO/tools/generator/triposg_runner.py" \
  --image "$PRE/dex_front.png" \
  --output-dir "$OUT_A" \
  --seed 42

echo "=== [2A-2] Candidate B: Hunyuan3D-2mv (4 views, seed 42) ==="
/home/bruno/.venvs/hunyuan/bin/python \
  "$REPO/tools/generator/hunyuan_runner.py" \
  --variant mv \
  --image "$PRE/dex_front.png" \
  --left "$PRE/dex_left.png" \
  --back "$PRE/dex_back.png" \
  --right "$PRE/dex_right.png" \
  --output-dir "$OUT_B" \
  --seed 42

PEAK=$(awk -F, 'NR>1 && $2>m {m=$2} END {print m+0}' "$VRAM_LOG")
echo "TAREFA2_SHAPES_DONE | PEAK_VRAM_MIB=$PEAK"
