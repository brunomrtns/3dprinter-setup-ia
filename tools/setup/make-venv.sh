#!/usr/bin/env bash
# make-venv.sh — cria o venv canônico do projeto ~/.venvs/printer3d-ia (idempotente).
# Uso: bash tools/setup/make-venv.sh
# Segurança: se o venv JÁ existe, NÃO TOCA (nenhuma reinstalação silenciosa).
#   Para recriar de propósito: apague a pasta à mão e rode de novo (ação manual).
set -u
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

log "=== make-venv — início ==="

VENV="$HOME/.venvs/printer3d-ia"

if [ -x "$VENV/bin/python" ]; then
    ok "venv já existe em $VENV ($("$VENV/bin/python" --version 2>&1)) — NADA foi alterado."
    log "=== make-venv — fim (log: $LOG_FILE) ==="
    exit 0
fi

if ! command -v python3.11 >/dev/null 2>&1; then
    fail "python3.11 ausente — rode antes: bash tools/setup/install-python311.sh"
    exit 1
fi

log "criando venv em $VENV (python3.11)"
if ! run_logged python3.11 -m venv "$VENV"; then
    fail "criação do venv falhou"
    exit 1
fi

# Determina a wheel do torch pela GPU da máquina (ADR-006: perfis de máquina).
# Blackwell (RTX 50xx, sm_120) exige torch >= 2.7 com index cu128.
# Turing/Ampere/Ada (RTX 16/20/30/40xx) usa o index cu121 padrão do projeto.
GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || true)"
if [ -z "$GPU_NAME" ]; then
    warn "nvidia-smi não respondeu — não vou instalar torch sem saber a GPU"
    log "instale torch MANUALMENTE depois, com o index certo para sua GPU"
    TORCH_DONE=0
elif echo "$GPU_NAME" | grep -qiE 'RTX 5[0-9]{2}|50[0-9]0'; then
    log "GPU detectada: '$GPU_NAME' → arquitetura Blackwell (sm_120)"
    log "instalando torch cu128 (PyTorch >= 2.7) — versão exata será A VALIDAR no audit"
    if run_logged "$VENV/bin/pip" install --upgrade pip && \
       run_logged "$VENV/bin/pip" install torch --index-url https://download.pytorch.org/whl/cu128; then
        TORCH_DONE=1
    else
        fail "instalação do torch cu128 falhou"
        TORCH_DONE=0
    fi
else
    log "GPU detectada: '$GPU_NAME' → pré-Blackwell"
    log "instalando torch cu121 (padrão do projeto, testado na 3060)"
    if run_logged "$VENV/bin/pip" install --upgrade pip && \
       run_logged "$VENV/bin/pip" install torch --index-url https://download.pytorch.org/whl/cu121; then
        TORCH_DONE=1
    else
        fail "instalação do torch cu121 falhou"
        TORCH_DONE=0
    fi
fi

if [ "${TORCH_DONE:-0}" -eq 1 ]; then
    "$VENV/bin/python" -c "import torch; print('torch', torch.__version__, '| cuda:', torch.cuda.is_available())" 2>&1 | tee -a "$LOG_FILE"
fi

ok "venv criado em $VENV"
log "=== make-venv — fim (log: $LOG_FILE) ==="
