#!/usr/bin/env bash
set -euo pipefail

CAP_DIR="/mnt/c/Users/Bruno/workspace/game-concerto/captures/tool_system"
FRAMES_DIR="$CAP_DIR/frames_raw"
OUT_MP4="$CAP_DIR/tool_system_modes_1080p.mp4"
SFX_DIR="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/Tool"
HUM_BG="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/Cutscenes/CS01/cs01_machine_hum_TEMP.wav"

if [ ! -d "$FRAMES_DIR" ] || [ -z "$(ls -A "$FRAMES_DIR"/frame_*.jpg 2>/dev/null)" ]; then
  echo "ERROR: No frames found in $FRAMES_DIR"
  exit 1
fi

ffmpeg -y \
  -framerate 30 -i "$FRAMES_DIR/frame_%05d.jpg" \
  -stream_loop -1 -i "$HUM_BG" \
  -i "$SFX_DIR/tool_mode_switch_TEMP.wav" \
  -i "$SFX_DIR/tool_melee_hit_TEMP.wav" \
  -i "$SFX_DIR/tool_bolt_fire_TEMP.wav" \
  -filter_complex "\
    [1:a]volume=0.20[bg];\
    [2:a]adelay=2000:all=1,volume=0.80[sw];\
    [3:a]adelay=4500:all=1,volume=0.90[hit1];\
    [4:a]adelay=11000:all=1,volume=0.88[bolt];\
    [bg][sw][hit1][bolt]amix=inputs=4:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95[aout]" \
  -map 0:v:0 -map "[aout]" \
  -c:v libx264 -preset medium -crf 22 -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  -shortest \
  "$OUT_MP4"

echo "ENCODED OK: $OUT_MP4"
ls -lh "$OUT_MP4"
