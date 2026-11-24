#!/usr/bin/env bash
set -euo pipefail

CAP_DIR="/mnt/c/Users/Bruno/workspace/game-concerto/captures/setor_externo"
FRAMES_DIR="$CAP_DIR/frames_raw"
OUT_MP4="$CAP_DIR/setor_externo_walkthrough_1080p.mp4"
WIND="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/Sector/sector_cold_wind_ambience_TEMP.wav"
CHIME="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/Repair/repair_resolve_chime_TEMP.wav"

if [ ! -d "$FRAMES_DIR" ] || [ -z "$(ls -A "$FRAMES_DIR"/frame_*.jpg 2>/dev/null)" ]; then
  echo "ERROR: No frames found in $FRAMES_DIR"
  exit 1
fi

ffmpeg -y \
  -framerate 30 -i "$FRAMES_DIR/frame_%05d.jpg" \
  -stream_loop -1 -i "$WIND" \
  -i "$CHIME" \
  -filter_complex "\
    [1:a]volume=0.55[w];\
    [2:a]adelay=11000:all=1,volume=0.80[c];\
    [w][c]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95[aout]" \
  -map 0:v:0 -map "[aout]" \
  -c:v libx264 -preset medium -crf 22 -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  -shortest \
  "$OUT_MP4"

echo "ENCODED OK: $OUT_MP4"
ls -lh "$OUT_MP4"
