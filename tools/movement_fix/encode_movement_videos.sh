#!/usr/bin/env bash
set -euo pipefail

DIR="/mnt/c/Users/Bruno/workspace/game-concerto/captures/movement_fix"
SFX_STEP="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/Movement/footstep_floor_TEMP.wav"
SFX_LAND="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/Movement/landing_thud_TEMP.wav"

encode_clip() {
  local name="$1"
  local frames="$DIR/${name}_frames/frame_%05d.jpg"
  local out="$DIR/${name}_1080p.mp4"
  if [ ! -f "$DIR/${name}_frames/frame_00000.jpg" ]; then
    echo "SKIP $name (no frames)"
    return
  fi
  ffmpeg -y \
    -framerate 30 -i "$frames" \
    -stream_loop -1 -i "$SFX_STEP" \
    -map 0:v:0 -map 1:a:0 \
    -c:v libx264 -pix_fmt yuv420p -crf 21 -preset fast -movflags +faststart \
    -c:a aac -b:a 160k -shortest \
    "$out"
  rm -rf "$DIR/${name}_frames"
  echo "ENCODED OK: $out"
  ls -lh "$out"
}

encode_clip "before_after_snag_fix"
encode_clip "full_scenes_tour_zero_snag"
