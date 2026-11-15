#!/usr/bin/env bash
# Resolve o python do venv do projeto em qualquer máquina (ADR-006).
# Uso: tools/setup/py.sh <script.py> [args...]
# Regra: o venv canônico é ~/.venvs/printer3d-ia no WSL da máquina local (ADR-004).
# NUNCA hardcode /home/<usuario>/ — o username varia entre máquinas.
set -euo pipefail

VENV_PY="$HOME/.venvs/printer3d-ia/bin/python"

if [ -x "$VENV_PY" ]; then
    exec "$VENV_PY" "$@"
fi

echo "[py.sh] ERRO: venv do projeto não encontrado em $VENV_PY" >&2
echo "[py.sh] Crie com: bash tools/setup/make-venv.sh" >&2
echo "[py.sh] Se o python 3.11 do sistema também falta: bash tools/setup/install-python311.sh" >&2
exit 1
