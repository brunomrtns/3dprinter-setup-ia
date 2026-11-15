#!/usr/bin/env bash
# check-gpu.sh — valida GPU visível no WSL + torch+CUDA no venv (idempotente).
# Uso: bash tools/setup/check-gpu.sh
set -u
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

log "=== check-gpu — início ==="

if ! command -v nvidia-smi >/dev/null 2>&1; then
    fail "nvidia-smi não existe dentro do WSL — driver NVIDIA do Windows ausente/antigo"
    log "O driver é instalado SÓ no Windows (nunca dentro do WSL). Atualize pelo app NVIDIA"
    log "e rode 'wsl --shutdown' antes de re-testar."
    log "=== check-gpu — fim (log: $LOG_FILE) ==="
    exit 1
fi

log "-- nvidia-smi (WSL) --"
nvidia-smi --query-gpu=name,driver_version,memory.total,memory.free --format=csv 2>&1 | tee -a "$LOG_FILE"

VENV_PY="$HOME/.venvs/printer3d-ia/bin/python"
if [ ! -x "$VENV_PY" ]; then
    warn "venv do projeto não existe — rode: bash tools/setup/make-venv.sh"
    log "=== check-gpu — fim (log: $LOG_FILE) ==="
    exit 1
fi

log "-- torch no venv do projeto --"
if OUT="$("$VENV_PY" -c "
import torch
print('torch', torch.__version__)
print('cuda_available', torch.cuda.is_available())
if torch.cuda.is_available():
    print('device', torch.cuda.get_device_name(0))
    print('capability', torch.cuda.get_device_capability(0))
    free, total = torch.cuda.mem_get_info()
    print(f'vram_free_mib {free//2**20} of {total//2**20}')
" 2>&1)"; then
    echo "$OUT" | tee -a "$LOG_FILE"
    if echo "$OUT" | grep -q "cuda_available True"; then
        ok "CUDA funcionando no venv"
    else
        fail "torch instalado mas cuda_available=False — wheel provavelmente errada para a GPU"
        log "Blackwell (RTX 50xx / sm_120) exige torch >= 2.7 wheel cu128 — refazer venv"
    fi
    if echo "$OUT" | grep -q "capability (12, 0)"; then
        ok "capability (12, 0) = Blackwell sm_120 confirmada"
    fi
else
    fail "torch não roda no venv ($OUT)"
fi

log "=== check-gpu — fim (log: $LOG_FILE) ==="
