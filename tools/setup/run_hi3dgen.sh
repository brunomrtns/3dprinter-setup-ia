#!/usr/bin/env bash
set -e
export SPCONV_ALGO=native
export HI3DGEN_HOME="$HOME/tools/Hi3DGen"
REPO_DIR="/mnt/c/Users/Bruno/OneDrive/Documentos/Default Project/3dprinter-setup-ia"
exec "$HOME/.venvs/hi3dgen/bin/python" "$REPO_DIR/tools/generator/hi3dgen_runner.py" "$@"
