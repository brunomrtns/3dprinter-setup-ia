#!/usr/bin/env bash
# Porta oficial de instalacao do ComfyUI headless + FLUX.1-dev FP8 (ADR-010 / Lei 8)
# Uso: bash tools/setup/install_comfyui.sh [--download-flux]
set -euo pipefail

COMFY_DIR="${COMFYUI_DIR:-$HOME/tools/comfyui}"
VENV_DIR="${COMFYUI_VENV:-$HOME/.venvs/comfyui}"
DOWNLOAD_FLUX="${1:-}"

echo "[install_comfyui] 1/4 Clonando/atualizando ComfyUI em $COMFY_DIR"
if [ ! -d "$COMFY_DIR/.git" ]; then
    mkdir -p "$(dirname "$COMFY_DIR")"
    git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git "$COMFY_DIR"
else
    echo "[install_comfyui] ComfyUI ja existe em $COMFY_DIR"
fi

echo "[install_comfyui] 2/4 Criando venv dedicada $VENV_DIR"
if [ ! -x "$VENV_DIR/bin/python" ]; then
    BASE_PY="$(~/.venvs/hunyuan/bin/python -c 'import sys; print(sys.base_executable)' 2>/dev/null || which python3.11 || which python3)"
    echo "[install_comfyui] Usando Python base: $BASE_PY"
    "$BASE_PY" -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip wheel
    "$VENV_DIR/bin/pip" install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
fi

echo "[install_comfyui] 3/4 Instalando requirements.txt do ComfyUI"
"$VENV_DIR/bin/pip" install -r "$COMFY_DIR/requirements.txt"

"$VENV_DIR/bin/python" -c "import torch; print('[install_comfyui] torch=', torch.__version__, 'cuda=', torch.cuda.is_available())"

if [ "$DOWNLOAD_FLUX" = "--download-flux" ]; then
    CKPT_DIR="$COMFY_DIR/models/checkpoints"
    mkdir -p "$CKPT_DIR"
    OUT_FILE="$CKPT_DIR/flux1-dev-fp8.safetensors"
    URL="https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors"
    echo "[install_comfyui] 4/4 Baixando peso unico autorizado (FLUX.1-dev FP8 all-in-one)..."
    curl -L -C - --retry 5 --retry-delay 5 -o "$OUT_FILE" "$URL"
    echo "[install_comfyui] Calculando SHA-256 de $OUT_FILE..."
    sha256sum "$OUT_FILE" | tee "$OUT_FILE.sha256"
else
    echo "[install_comfyui] 4/4 Download de peso pulado (passe --download-flux para baixar FLUX.1-dev FP8)."
fi

echo "[install_comfyui] CONCLUIDO!"
