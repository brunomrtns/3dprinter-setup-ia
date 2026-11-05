#!/bin/bash
set -e
PY311=/usr/bin/python3.11
VENV=~/.venvs/printer3d-sd
[ -d "$VENV" ] || $PY311 -m venv "$VENV"
$VENV/bin/pip install -q --upgrade pip
$VENV/bin/pip install -q torch==2.5.1 --index-url https://download.pytorch.org/whl/cu121
$VENV/bin/python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
$VENV/bin/pip install -q diffusers==0.31.0 transformers==4.46.3 accelerate safetensors Pillow
$VENV/bin/python -c "import diffusers, transformers; print('diffusers', diffusers.__version__, '| transformers', transformers.__version__)"
echo SD_VENV_OK
