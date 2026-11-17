#!/bin/bash
# pipeline_imagem3d.sh — pipeline OFICIAL imagem→3D (decisão do dono, gate C5 2026-11-17):
#   imagem → preproc C2 (rembg, 1024, fundo branco) → TripoSG (forma) → refino TripoSF 512
#
# Uso:  pipeline_imagem3d.sh <imagem.png|jpg|webp> <dir_saida> [seed]
#
# Saída:
#   <dir>/entrada_preproc.png            — entrada padronizada
#   <dir>/1_triposg/mesh.obj             — malha bruta do gerador
#   <dir>/2_triposf512/*_reconstruction.obj — MALHA FINAL (refinada)
#   <dir>/2_triposf512/report.json       — telemetria (VRAM pico, tempos, faces)
#
# Regras da casa: não rodar em paralelo com outros jobs GPU (a etapa 3 tem guard
# próprio de VRAM 10.000 MiB; a etapa 2, herdada do C3, não tem).
# Para IMPRIMIR a saída: passar pela Forja antes (watertight/ilhas) — Fase 2.
set -euo pipefail

IMG="${1:?uso: pipeline_imagem3d.sh <imagem> <dir_saida> [seed]}"
OUT="${2:?uso: pipeline_imagem3d.sh <imagem> <dir_saida> [seed]}"
SEED="${3:-42}"
GEN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_C2="$HOME/.venvs/printer3d-ia/bin/python"       # rembg (C2)
PY_SG="$HOME/.venvs/triposg/bin/python"             # TripoSG (C3)
PY_SF="${TRIPOSF_PY:-$HOME/venvs/triposf/bin/python}"  # TripoSF (C5)

mkdir -p "$OUT"
echo "[pipeline] 1/3 preproc (rembg → PNG 1024 fundo branco)"
"$PY_C2" "$GEN/preprocess_input.py" --input "$IMG" --output "$OUT/entrada_preproc.png"

echo "[pipeline] 2/3 TripoSG (imagem → malha) — ~1min, pico ~10-12GB"
TRIPOSG_HOME="$HOME/tools/TripoSG" "$PY_SG" "$GEN/triposg_runner.py" \
  --image "$OUT/entrada_preproc.png" --output-dir "$OUT/1_triposg" --seed "$SEED" \
  | tee "$OUT/triposg.log" | grep REPORT_JSON || true
[ -f "$OUT/1_triposg/mesh.obj" ] || { echo "[pipeline] ERRO: TripoSG não gerou mesh"; exit 1; }

echo "[pipeline] 3/3 refino TripoSF 512 (guard 10.000 MiB ativo) — ~30s, pico ~7,5GB"
"$PY_SF" "$GEN/triposf/triposf_runner.py" \
  --mesh-path "$OUT/1_triposg/mesh.obj" --output-dir "$OUT/2_triposf512" \
  --config "$GEN/triposf/TripoSFVAE_o512.yaml" --label pipeline | tee "$OUT/triposf.log"

FINAL=$(ls "$OUT"/2_triposf512/*_reconstruction.obj 2>/dev/null | head -1)
echo "[pipeline] PRONTO: $FINAL"
echo "[pipeline] P/ imprimir: rodar Forja (reparo watertight/ilhas) antes do slice."
