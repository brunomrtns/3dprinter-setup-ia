#!/usr/bin/env bash
# collect-audit.sh — auditoria de ambiente no formato de
# docs/operations/environment-audit.md (outputs REAIS, nunca inventar).
# Uso: bash tools/setup/collect-audit.sh [arquivo-saida.md]
set -u
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

log "=== collect-audit — início ==="

OUT="${1:-$EVID_DIR/audit-$(hostname 2>/dev/null || echo maquina)-$(date +%Y-%m-%d).md}"
HOST_OK="$(grep -qi microsoft /proc/version 2>/dev/null && echo "WSL2 ($(grep -m1 -o 'microsoft/standard.*\|WSL2' /proc/version 2>/dev/null || echo 'WSL'))" || echo 'não-WSL')"
CMD="$(command -v blender >/dev/null 2>&1 && blender --version 2>/dev/null | head -1 || echo 'AUSENTE')"
PY311="$(command -v python3.11 >/dev/null 2>&1 && python3.11 --version 2>&1 || echo 'AUSENTE')"
GITV="$(git --version 2>&1)"
NVG="$(command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi --query-gpu=name,driver_version,memory.total,memory.free --format=csv,noheader 2>/dev/null | head -1 || echo 'AUSENTE')"
DISCO="$(df -h / | tail -1)"
VENV="$( [ -x ~/.venvs/printer3d-ia/bin/python ] && ~/.venvs/printer3d-ia/bin/python -c 'import torch; print(torch.__version__, torch.cuda.is_available())' 2>/dev/null || echo 'venv ausente ou torch falhou')"

cat > "$OUT" <<EOF
# Auditoria de Ambiente — $(date '+%Y-%m-%d %H:%M %Z')

**Executor:** agente (tools/setup/collect-audit.sh) · **Método:** comandos reais, outputs colados abaixo — nenhum output inventado (AGENTS.md §1.5).

## Sumário

| Item | Comando | Status | Resultado-chave |
|---|---|---|---|
| WSL | \`(dentro do WSL)\` | ✅ | $HOST_OK |
| Distro | \`lsb_release\`/\`os-release\` | ✅ | $(. /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-?}") (kernel $(uname -r)) |
| Blender | \`blender --version\` | $( [ "$CMD" = "AUSENTE" ] && echo "❌" || echo "✅") | $CMD |
| GPU (WSL) | \`nvidia-smi --query-gpu=...\` | $( [ "$NVG" = "AUSENTE" ] && echo "❌" || echo "✅") | $NVG |
| Python 3.11 | \`python3.11 --version\` | $( [ "$PY311" = "AUSENTE" ] && echo "❌" || echo "✅") | $PY311 @ $(command -v python3.11 2>/dev/null || echo '-') |
| Git | \`git --version\` | ✅ | $GITV |
| Disco WSL | \`df -h /\` | ✅ | $DISCO |
| venv printer3d-ia | \`torch; cuda.is_available()\` | $( echo "$VENV" | grep -q True && echo "✅" || echo "❌") | $VENV |
| Guard (perfil) | \`tools/setup/py.sh tools/generator/gpu_guard.py\` | — | rodar separadamente e colar aqui |

## Outputs Reais

### Distro / kernel

\`\`\`bash
$ (. /etc/os-release && echo \$PRETTY_NAME); uname -r
$(. /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-?}")
$(uname -r)
\`\`\`

### GPU (nvidia-smi completo)

\`\`\`
$(command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi 2>/dev/null || echo "AUSENTE — driver NVIDIA do Windows não está mapeando para o WSL")
\`\`\`

### Guard de VRAM (perfil de máquina, ADR-006)

\`\`\`
$ tools/setup/py.sh tools/generator/gpu_guard.py || python3.11 tools/generator/gpu_guard.py
$(python3.11 "$REPO_ROOT/tools/generator/gpu_guard.py" 2>&1 || echo "(falhou — colar erro real)")
\`\`\`

### Python / venv / git

\`\`\`bash
$ python3.11 --version; git --version
$PY311
$GITV
$ ~/.venvs/printer3d-ia/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
$VENV
\`\`\`

### Disco

\`\`\`bash
$ df -h /
$DISCO
\`\`\`

## Pendências

- [ ] preencher conforme os outputs acima (o que falhou vai aqui com o erro REAL)
EOF

ok "auditoria gerada: $OUT"
log "=== collect-audit — fim (log: $LOG_FILE) ==="
