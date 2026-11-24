#!/usr/bin/env bash
set -euo pipefail

CAP_DIR="/mnt/c/Users/Bruno/workspace/game-concerto/captures/act2_return"
FRAMES_DIR="$CAP_DIR/frames_raw"
OUT_MP4="$CAP_DIR/act2_return_and_anomalies_1080p.mp4"
CS03_AUDIO="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/Cutscenes/CS03"

if [ ! -d "$FRAMES_DIR" ] || [ -z "$(ls -A "$FRAMES_DIR"/frame_*.jpg 2>/dev/null)" ]; then
  echo "ERROR: No frames found in $FRAMES_DIR"
  exit 1
fi

ffmpeg -y \
  -framerate 30 -i "$FRAMES_DIR/frame_%05d.jpg" \
  -i "$CS03_AUDIO/cs03_flash_return_TEMP.wav" \
  -stream_loop -1 -i "$CS03_AUDIO/cs03_machine_hum_loop_TEMP.wav" \
  -stream_loop -1 -i "$CS03_AUDIO/cs03_anomaly_wrong_sound_TEMP.wav" \
  -filter_complex "\
    [1:a]adelay=100:all=1,volume=0.72[a1];\
    [2:a]atrim=0:30,asetpts=PTS-STARTPTS,adelay=18200:all=1,volume=0.68[a2];\
    [3:a]atrim=0:16,asetpts=PTS-STARTPTS,adelay=32000:all=1,volume=0.55[a3];\
    [a1][a2][a3]amix=inputs=3:duration=longest:dropout_transition=0:normalize=0,alimiter=limit=0.95[aout]" \
  -map 0:v:0 -map "[aout]" \
  -c:v libx264 -preset medium -crf 22 -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  -shortest \
  "$OUT_MP4"

echo "ENCODED OK: $OUT_MP4"
ls -lh "$OUT_MP4"
