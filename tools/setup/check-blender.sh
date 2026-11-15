#!/usr/bin/env bash
# check-blender.sh — valida Blender headless (idempotente; não instala nada).
# Uso: bash tools/setup/check-blender.sh
set -u
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

log "=== check-blender — início ==="

if ! command -v blender >/dev/null 2>&1; then
    warn "blender não está no PATH"
    log "Para instalar (Ubuntu, versão nova via tarball oficial — apt costuma ter versão velha):"
    log "  1. baixe https://download.blender.org/release/Blender5.0/ (linux x64 tar.xz)"
    log "  2. sudo tar -xJf blender-5.0.1-linux-x64.tar.xz -C /opt/"
    log "  3. sudo ln -sf /opt/blender-5.0.1-linux-x64/blender /usr/local/bin/blender"
    log "  4. rode este script de novo"
    log "=== check-blender — fim (log: $LOG_FILE) ==="
    exit 1
fi

ok "blender no PATH: $(command -v blender)"
VER="$(blender --version 2>/dev/null | head -1 || true)"
log "versão: $VER"

case "$VER" in
    Blender\ 5.*) ok "Blender 5.x — compatível com o projeto (referência: 5.0.1)" ;;
    "") fail "não consegui ler a versão do blender (ver log)" ;;
    *) warn "versão não-5.x detectada — o projeto usa bpy de Blender 5.0.1; valide compatibilidade" ;;
esac

# Prova headless (sem GUI): expressão Python simples pelo -b
if blender -b --python-expr "import bpy; print('BLENDER_HEADLESS_OK', bpy.app.version)" 2>&1 | grep -q BLENDER_HEADLESS_OK; then
    ok "modo headless (-b) funcionando"
else
    fail "blender -b não respondeu — sem display/GPU pode faltar; ver log"
fi

log "=== check-blender — fim (log: $LOG_FILE) ==="
