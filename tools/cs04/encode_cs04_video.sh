#!/usr/bin/env bash
set -euo pipefail

FRAMES="/mnt/c/Users/Bruno/workspace/game-concerto/captures/cs04_sky_cracked/frames_raw/frame_%05d.jpg"
OUT="/mnt/c/Users/Bruno/workspace/game-concerto/captures/cs04_sky_cracked/cutscene04_o_ceu_rachou_1080p.mp4"
SFX_CRACK="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/Repair/act2_trinket_crack_TEMP.wav"
SFX_ALARM="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/Cutscenes/cs04_alarm_backup_TEMP.wav"
SFX_DOOR="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/Cutscenes/cs04_heavy_door_unlock_TEMP.wav"
SFX_WIND="/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/Sector/sector_cold_wind_ambience_TEMP.wav"

# Mixa audio sincronizado com o video completo:
#   0.0s..2.5s : Beat final do Ato 2 (bugiganga quebra + luz pisca)
#   2.5s..12.5s: Beat 1 (Alarme discreto + luzes de backup)
#  12.5s..20.5s: Beat 2 (Porta pesada destravando com esforco + pressao + vento)
#  20.5s..fim  : Beat 3 & 4 + controle no Setor + Continuar (silencio, so vento frio)
ffmpeg -y \
  -framerate 30 -i "$FRAMES" \
  -i "$SFX_CRACK" \
  -i "$SFX_ALARM" \
  -i "$SFX_DOOR" \
  -stream_loop -1 -i "$SFX_WIND" \
  -filter_complex "\
    [1:a]adelay=700|700,volume=0.85[a1]; \
    [2:a]adelay=2600|2600,volume=0.72[a2]; \
    [3:a]adelay=12500|12500,volume=0.95[a3]; \
    [4:a]adelay=19500|19500,volume=0.62[a4]; \
    [a1][a2][a3][a4]amix=inputs=4:duration=longest:normalize=0,alimiter=limit=0.95[aout]" \
  -map 0:v:0 -map "[aout]" \
  -c:v libx264 -pix_fmt yuv420p -crf 21 -preset medium -movflags +faststart \
  -c:a aac -b:a 192k -shortest \
  "$OUT"

echo "ENCODED OK: $OUT"
ls -lh "$OUT"
