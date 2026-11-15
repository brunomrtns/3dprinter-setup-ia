#!/usr/bin/env bash
# install-python311.sh — garante python3.11 no Ubuntu do WSL (idempotente).
# Uso: bash tools/setup/install-python311.sh
# Segurança: só instala pacotes via apt; não apaga nada; sudo com senha é GATE humano.
set -u
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

log "=== install-python311 — início ==="

if command -v python3.11 >/dev/null 2>&1; then
    ok "python3.11 já existe: $(command -v python3.11) → $(python3.11 --version 2>&1). Nada a fazer."
    log "=== install-python311 — fim (log: $LOG_FILE) ==="
    exit 0
fi

. /etc/os-release 2>/dev/null || { fail "não identifiquei a distro (/etc/os-release)"; exit 1; }
log "distro: ${PRETTY_NAME:-?}"

if ! sudo_ready; then
    log "PARE — este passo precisa de sudo (apt). Peça ao HUMANO para rodar ele mesmo:"
    log "  bash tools/setup/install-python311.sh"
    log "(no sudo, o humano digita a própria senha do Linux)"
    exit 4
fi

# Ubuntu 24.04+/26.04 já tem python3.11 nos repos; distros antigas precisam deadsnakes
if apt-cache show python3.11 >/dev/null 2>&1; then
    log "python3.11 disponível no apt da distro"
    APT_PKGS="python3.11 python3.11-venv python3.11-dev"
else
    log "python3.11 NÃO está nos repos da distro — adicionando PPA deadsnakes"
    APT_PKGS="python3.11 python3.11-venv python3.11-dev"
    run_logged sudo apt-get update
    run_logged sudo apt-get install -y software-properties-common
    run_logged sudo add-apt-repository -y ppa:deadsnakes/ppa
fi

run_logged sudo apt-get update
if run_logged sudo apt-get install -y $APT_PKGS; then
    ok "python3.11 instalado: $(python3.11 --version 2>&1) @ $(command -v python3.11)"
else
    fail "instalação do python3.11 falhou (ver log acima)"
    log "=== install-python311 — fim (log: $LOG_FILE) ==="
    exit 1
fi

log "=== install-python311 — fim (log: $LOG_FILE) ==="
