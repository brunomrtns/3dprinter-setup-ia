#!/usr/bin/env bash
# check-prereqs.sh — checa pré-requisitos do projeto (não instala nada).
# Uso (dentro do WSL): bash tools/setup/check-prereqs.sh
set -u
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

log "=== check-prereqs — início ==="

MISSING=0
check() { # check <descrição> <comando...>
    local desc="$1"; shift
    if "$@" >/dev/null 2>&1; then
        ok "$desc"
    else
        warn "$desc — AUSENTE"
        MISSING=$((MISSING + 1))
    fi
}

if grep -qi microsoft /proc/version 2>/dev/null; then
    ok "rodando dentro do WSL ($(grep -io 'microsoft' /proc/version | head -1))"
else
    warn "não parece ser WSL — os scripts do projeto assumem WSL2 Ubuntu"
fi

check "python3.11 disponível" bash -c 'command -v python3.11'
check "git disponível" bash -c 'command -v git'
check "curl disponível" bash -c 'command -v curl'
check "nvidia-smi disponível (GPU visível)" bash -c 'command -v nvidia-smi'
check "venv do projeto (~/.venvs/printer3d-ia)" bash -c 'test -x ~/.venvs/printer3d-ia/bin/python'
check "Blender no PATH" bash -c 'command -v blender'

FREE_GB=$(df --output=avail -BG "$HOME" | tail -1 | tr -dc '0-9')
if [ "${FREE_GB:-0}" -ge 30 ]; then
    ok "disco livre em \$HOME: ${FREE_GB} GB (>= 30 GB)"
else
    warn "disco livre em \$HOME: ${FREE_GB} GB (< 30 GB — pesos de IA precisam de espaço)"
    MISSING=$((MISSING + 1))
fi

log "=== check-prereqs — fim ($MISSING item(ns) pendente(s); log: $LOG_FILE) ==="
[ "$MISSING" -eq 0 ] && exit 0
log "Para instalar python3.11: bash tools/setup/install-python311.sh"
log "Para criar o venv: bash tools/setup/make-venv.sh"
exit 1
