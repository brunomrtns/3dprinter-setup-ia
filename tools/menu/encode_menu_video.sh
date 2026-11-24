#!/usr/bin/env bash
set -euo pipefail

CAP_DIR="/mnt/c/Users/Bruno/workspace/game-concerto/captures/menu_flow"
FRAMES_DIR="$CAP_DIR/frames_raw"
OUT_MP4="$CAP_DIR/menu_flow_1080p.mp4"
MUSIC="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/Cutscenes/CS01/cs01_musicbox_motif_TEMP.wav"

if [ ! -d "$FRAMES_DIR" ] || [ -z "$(ls -A "$FRAMES_DIR"/frame_*.jpg 2>/dev/null)" ]; then
  echo "ERROR: No frames found in $FRAMES_DIR"
  exit 1
fi

ffmpeg -y \
  -framerate 15 -i "$FRAMES_DIR/frame_%05d.jpg" \
  -stream_loop -1 -i "$MUSIC" \
  -filter_complex "[1:a]volume=0.38[aout]" \
  -map 0:v:0 -map "[aout]" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  -shortest \
  "$OUT_MP4"

echo "ENCODED OK: $OUT_MP4"
ls -lh "$OUT_MP4"
