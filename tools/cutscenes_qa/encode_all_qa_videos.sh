#!/usr/bin/env bash
set -euo pipefail

QA_DIR="/mnt/c/Users/Bruno/workspace/game-concerto/captures/cutscenes_qa"

encode_one() {
  local tag="$1"
  local audio="$2"
  local frames="$QA_DIR/${tag}_frames/frame_%05d.jpg"
  local out="$QA_DIR/${tag}_qa_fixed_1080p.mp4"
  if [ ! -f "$QA_DIR/${tag}_frames/frame_00000.jpg" ]; then
    echo "SKIP $tag (no frames)"
    return
  fi
  ffmpeg -y \
    -framerate 30 -i "$frames" \
    -stream_loop -1 -i "$audio" \
    -map 0:v:0 -map 1:a:0 \
    -c:v libx264 -pix_fmt yuv420p -crf 22 -preset fast -movflags +faststart \
    -c:a aac -b:a 160k -shortest \
    "$out"
  rm -rf "$QA_DIR/${tag}_frames"
  echo "ENCODED OK: $out"
  ls -lh "$out"
}

encode_one "cs01_concerto"   "/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/Cutscenes/CS01/cs01_musicbox_motif_TEMP.wav"
encode_one "cs02_viagem"     "/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/Cutscenes/CS01/cs01_musicbox_motif_TEMP.wav"
encode_one "cs03_retorno"    "/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/Cutscenes/CS03/cs03_machine_hum_loop_TEMP.wav"
encode_one "cs04_ceu_rachou" "/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/Sector/sector_cold_wind_ambience_TEMP.wav"
