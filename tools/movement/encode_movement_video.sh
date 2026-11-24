#!/usr/bin/env bash
set -euo pipefail

CAP_DIR="/mnt/c/Users/Bruno/workspace/game-concerto/captures/movement_feel"
FRAMES_DIR="$CAP_DIR/frames_raw"
OUT_MP4="$CAP_DIR/dez_movement_feel_1080p.mp4"
DASH_SFX="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/dez_thruster_dash_TEMP.wav"
HUM_BG="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/Cutscenes/CS01/cs01_machine_hum_TEMP.wav"

if [ ! -d "$FRAMES_DIR" ] || [ -z "$(ls -A "$FRAMES_DIR"/frame_*.jpg 2>/dev/null)" ]; then
  echo "ERROR: No frames found in $FRAMES_DIR"
  exit 1
fi

ffmpeg -y \
  -framerate 30 -i "$FRAMES_DIR/frame_%05d.jpg" \
  -stream_loop -1 -i "$HUM_BG" \
  -i "$DASH_SFX" \
  -i "$DASH_SFX" \
  -i "$DASH_SFX" \
  -filter_complex "\
    [1:a]volume=0.22[bg];\
    [2:a]adelay=28500:all=1,volume=0.88[d1];\
    [3:a]adelay=32500:all=1,volume=0.88[d2];\
    [4:a]adelay=53000:all=1,volume=0.88[d3];\
    [bg][d1][d2][d3]amix=inputs=4:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95[aout]" \
  -map 0:v:0 -map "[aout]" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  -shortest \
  "$OUT_MP4"

echo "ENCODED OK: $OUT_MP4"
ls -lh "$OUT_MP4"
