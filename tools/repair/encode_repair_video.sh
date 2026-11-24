#!/usr/bin/env bash
set -euo pipefail

CAP_DIR="/mnt/c/Users/Bruno/workspace/game-concerto/captures/repair_act2"
FRAMES_DIR="$CAP_DIR/frames_raw"
OUT_MP4="$CAP_DIR/repair_act2_loop_1080p.mp4"
REP_AUDIO="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/Repair"
MUSICBOX="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/Cutscenes/CS01/cs01_musicbox_motif_TEMP.wav"

if [ ! -d "$FRAMES_DIR" ] || [ -z "$(ls -A "$FRAMES_DIR"/frame_*.jpg 2>/dev/null)" ]; then
  echo "ERROR: No frames found in $FRAMES_DIR"
  exit 1
fi

ffmpeg -y \
  -framerate 30 -i "$FRAMES_DIR/frame_%05d.jpg" \
  -stream_loop -1 -i "$REP_AUDIO/repair_tool_channel_TEMP.wav" \
  -i "$REP_AUDIO/repair_resolve_chime_TEMP.wav" \
  -i "$MUSICBOX" \
  -i "$REP_AUDIO/act2_trinket_crack_TEMP.wav" \
  -filter_complex "\
    [1:a]volume=0.25[ch];\
    [2:a]adelay=5200:all=1,volume=0.85[r1];\
    [3:a]atrim=0:0.7,asetpts=PTS-STARTPTS,adelay=5300:all=1,volume=0.65[mb1];\
    [4:a]adelay=24500:all=1,volume=0.95[cr];\
    [ch][r1][mb1][cr]amix=inputs=4:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95[aout]" \
  -map 0:v:0 -map "[aout]" \
  -c:v libx264 -preset medium -crf 22 -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  -shortest \
  "$OUT_MP4"

echo "ENCODED OK: $OUT_MP4"
ls -lh "$OUT_MP4"
