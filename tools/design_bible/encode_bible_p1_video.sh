#!/usr/bin/env bash
set -euo pipefail

FRAMES="/mnt/c/Users/Bruno/workspace/game-concerto/captures/design_bible/p1_frames/frame_%05d.jpg"
OUT="/mnt/c/Users/Bruno/workspace/game-concerto/captures/design_bible/design_bible_p1_fixes_1080p.mp4"
SFX="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/dez_thruster_dash_TEMP.wav"

ffmpeg -y \
  -framerate 30 -i "$FRAMES" \
  -stream_loop -1 -i "$SFX" \
  -map 0:v:0 -map 1:a:0 \
  -c:v libx264 -pix_fmt yuv420p -crf 21 -preset fast -movflags +faststart \
  -c:a aac -b:a 160k -shortest \
  "$OUT"

rm -rf "/mnt/c/Users/Bruno/workspace/game-concerto/captures/design_bible/p1_frames"
echo "ENCODED OK: $OUT"
ls -lh "$OUT"
