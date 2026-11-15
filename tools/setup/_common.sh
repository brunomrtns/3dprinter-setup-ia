#!/usr/bin/env bash
# _common.sh — base compartilhada dos scripts de tools/setup/ (não executar direto).
# Regras de segurança (valem para TODO script que incluir este arquivo):
#   1. Nunca deletar nada fora do diretório do projeto;
#   2. Ação potencialmente destrutiva (sobrescrever/apagar) = PARAR e pedir
#      confirmação em texto simples antes de executar;
#   3. Nada é instalado sem checagem antes (scripts idempotentes).

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EVID_DIR="${EVIDENCE_SETUP_DIR:-$REPO_ROOT/evidence/setup}"
mkdir -p "$EVID_DIR"

# Log compartilhado por script: evidence/setup/<script>-<data>.log
LOG_FILE="$EVID_DIR/$(basename "${BASH_SOURCE[1]:-${BASH_SOURCE[0]}}" .sh)-$(date +%Y%m%d-%H%M%S).log"

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG_FILE"; }
ok() { log "OK: $*"; }
warn() { log "AVISO: $*"; }
fail() { log "FALHA: $*"; }

# Registra o comando e executa, guardando output no log
run_logged() {
    log "\$ $*"
    "$@" 2>&1 | tee -a "$LOG_FILE"
}

# Pedir confirmação humana (texto simples) antes de ação destrutiva
confirm_or_stop() {
    log "AÇÃO POTENCIALMENTE DESTRUTIVA detectada:"
    log "  $*"
    log "PARE — peça ao humano para ler acima e responder 'sim' para continuar."
    read -r -p "Continuar? (digite 'sim' para prosseguir, qualquer outra coisa cancela): " answer
    if [ "$answer" != "sim" ]; then
        log "Cancelado pelo humano (ou resposta diferente de 'sim'). Nada foi alterado."
        exit 3
    fi
}

# sudo disponível sem prompt? (senão: GATE humano — agente não digita senha)
sudo_ready() {
    if [ "$(id -u)" -eq 0 ]; then return 0; fi
    sudo -n true 2>/dev/null
}
