#!/usr/bin/env bash
set -euo pipefail

FRAMES="/mnt/c/Users/Bruno/workspace/game-concerto/captures/quest_signal/frames_raw/frame_%05d.jpg"
OUT="/mnt/c/Users/Bruno/workspace/game-concerto/captures/quest_signal/quest_signal_walkthrough_1080p.mp4"
WIND="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/Sector/sector_cold_wind_ambience_TEMP.wav"
CHIME="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/Repair/repair_resolve_chime_TEMP.wav"
CAPTURE="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/Sector/signal_antenna_capture_TEMP.wav"

ffmpeg -y \
  -framerate 30 -i "$FRAMES" \
  -stream_loop -1 -i "$WIND" \
  -i "$CHIME" \
  -i "$CAPTURE" \
  -filter_complex "\
    [1:a]volume=0.42[w]; \
    [2:a]adelay=7500|7500,volume=0.75[c1]; \
    [3:a]adelay=14500|14500,volume=0.88[cap]; \
    [w][c1][cap]amix=inputs=3:duration=longest:normalize=0,alimiter=limit=0.95[aout]" \
  -map 0:v:0 -map "[aout]" \
  -c:v libx264 -pix_fmt yuv420p -crf 21 -preset medium -movflags +faststart \
  -c:a aac -b:a 192k -shortest \
  "$OUT"

echo "ENCODED OK: $OUT"
ls -lh "$OUT"
