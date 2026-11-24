#!/usr/bin/env bash
set -euo pipefail

CAP_DIR="/mnt/c/Users/Bruno/workspace/game-concerto/captures/cs02_viagem"
FRAMES_DIR="$CAP_DIR/frames_raw"
OUT_MP4="$CAP_DIR/cs02_a_viagem_1080p.mp4"
CS01_AUDIO="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/Cutscenes/CS01"
CS02_AUDIO="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/Cutscenes/CS02"

if [ ! -d "$FRAMES_DIR" ] || [ -z "$(ls -A "$FRAMES_DIR"/frame_*.jpg 2>/dev/null)" ]; then
  echo "ERROR: No frames found in $FRAMES_DIR"
  exit 1
fi

ffmpeg -y \
  -framerate 30 -i "$FRAMES_DIR/frame_%05d.jpg" \
  -i "$CS02_AUDIO/cs02_machine_charge_TEMP.wav" \
  -i "$CS02_AUDIO/cs02_timewarp_stretch_TEMP.wav" \
  -i "$CS01_AUDIO/cs01_musicbox_motif_TEMP.wav" \
  -i "$CS02_AUDIO/cs02_glitch_distort_TEMP.wav" \
  -filter_complex "\
    [1:a]adelay=1500:all=1,volume=0.72[a1];\
    [2:a]adelay=15000:all=1,volume=0.78[a2];\
    [3:a]atrim=0:35,asetpts=PTS-STARTPTS,adelay=30000:all=1,volume=0.68[a3];\
    [4:a]adelay=65000:all=1,volume=0.78[a4];\
    [a1][a2][a3][a4]amix=inputs=4:duration=longest:dropout_transition=0:normalize=0,alimiter=limit=0.95,apad=whole_dur=85[aout]" \
  -map 0:v:0 -map "[aout]" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  -shortest \
  "$OUT_MP4"

echo "ENCODED OK: $OUT_MP4"
ls -lh "$OUT_MP4"
