#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Deploy do viewer "Modelos 3D" (C3) para a VPS
#
# Uso:  ./deploy.sh
#
# O que faz (mesmo padrão do printflow3d/deploy.sh):
#   1. Sincroniza o site (html/js/vendor) para /opt/modelos3d/site na VPS
#   2. Sincroniza os GLBs de ~/printer3d-work/modelos3d-site/models
#   3. Sobe container nginx estático na rede trivestia-net (nome: modelos3d)
#   4. Injeta location /modelos3d/ no nginx.conf do trivestia-nginx
#      (idempotente, backup automático, rollback se nginx -t falhar)
#   5. nginx -t + reload (sem derrubar conexões)
#   6. Smoke tests públicos + verificação dos apps vizinhos
#
# Público: https://brunointegrations.com/modelos3d/
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE_DIR="$SCRIPT_DIR"
MODELS_DIR="${MODELS3D_DIR:-$HOME/printer3d-work/modelos3d-site/models}"
VPS_PATH="/opt/modelos3d/site"
PUBLIC_BASE="https://brunointegrations.com/modelos3d"
NGINX_CONTAINER="trivestia-nginx"
NGINX_CONF="/opt/trivestia/nginx/nginx.conf"
VIEWER_CONTAINER="modelos3d"
NGINX_IMAGE="nginx:1.25-alpine"

vps() { my-vps --no-lock "$@"; }
log() { echo -e "\033[1;34m[deploy]\033[0m $*"; }
ok()  { echo -e "\033[1;32m  ✓\033[0m $*"; }
warn() { echo -e "\033[1;33m  ⚠\033[0m $*"; }
err() { echo -e "\033[1;31m  ✗\033[0m $*" >&2; }

# ── Pré-requisitos ───────────────────────────────────────────────────────────
command -v my-vps &>/dev/null || { err "my-vps não encontrado"; exit 1; }
vps "echo ok" &>/dev/null || { err "sem conexão com a VPS"; exit 1; }
ok "Conexão VPS OK"

[ -d "$MODELS_DIR" ] || { err "MODELS_DIR não existe: $MODELS_DIR"; exit 1; }
NGLB=$(ls "$MODELS_DIR"/*.glb 2>/dev/null | wc -l)
[ "$NGLB" -gt 0 ] || { err "Nenhum .glb em $MODELS_DIR"; exit 1; }
ok "$NGLB GLBs em $MODELS_DIR"

# ── Step 1: sincronizar site + modelos ──────────────────────────────────────
log "Step 1/4: Sincronizando site para $VPS_PATH..."
vps "mkdir -p $VPS_PATH/models"

my-vps --no-lock --rsync "$SITE_DIR/" "$VPS_PATH/" \
  --rsync-args "--exclude=models --exclude=.git --exclude=node_modules" || {
    err "rsync do site falhou"; exit 1; }

my-vps --no-lock --rsync "$MODELS_DIR/" "$VPS_PATH/models/" \
  --rsync-args "--exclude=*.tmp" || {
    err "rsync dos modelos falhou"; exit 1; }
ok "Site + modelos sincronizados"

# ── Step 2: container nginx estático ─────────────────────────────────────────
log "Step 2/4: Container $VIEWER_CONTAINER..."
EXISTS=$(vps "docker ps -a --format '{{.Names}}' | grep -cx $VIEWER_CONTAINER || true")
if [ "$EXISTS" = "1" ]; then
  STATE=$(vps "docker inspect -f '{{.State.Running}}' $VIEWER_CONTAINER")
  if [ "$STATE" != "true" ]; then
    vps "docker start $VIEWER_CONTAINER" && ok "Container existente reiniciado"
  else
    ok "Container já rodando (bind mount = arquivos já atualizados)"
  fi
else
  vps "docker run -d --name $VIEWER_CONTAINER --network trivestia-net \
    --restart unless-stopped \
    -v $VPS_PATH:/usr/share/nginx/html:ro \
    $NGINX_IMAGE" && ok "Container criado ($NGINX_IMAGE)"
fi

# ── Step 3: nginx do trivestia-nginx ─────────────────────────────────────────
log "Step 3/4: Injetando rota /modelos3d/ no nginx..."
vps 'python3 << "PYEOF"
import re, sys, shutil, time

CONF_PATH = "/opt/trivestia/nginx/nginx.conf"
with open(CONF_PATH) as f:
    content = f.read()

location_block = """    # ── Modelos 3D (viewer estático — comparativo C3) ────────────────
    location = /modelos3d {
        return 301 /modelos3d/;
    }
    location /modelos3d/ {
        limit_req zone=web_limit burst=60 nodelay;
        resolver 127.0.0.11 valid=10s;
        set $m3d_backend http://modelos3d:80;
        rewrite ^/modelos3d/(.*)$ /$1 break;
        proxy_pass         $m3d_backend;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        add_header         Cache-Control "no-cache";
    }
"""

content = re.sub(
    r"    # ── Modelos 3D.*?location /modelos3d/ \{.*?\n    \}\n?",
    "",
    content,
    flags=re.DOTALL,
)
content = re.sub(
    r"    location (?:= )?/modelos3d/? \{.*?\n    \}\n?",
    "",
    content,
    flags=re.DOTALL,
)
content = re.sub(
    r"^[ \t]*#[^\n]*(?:modelos3d)[^\n]*\n?",
    "",
    content,
    flags=re.MULTILINE | re.IGNORECASE,
)
content = re.sub(r"\n{3,}", "\n\n", content)

anchor = "    location = / {"
if anchor not in content:
    print("ERRO: anchor nao encontrado", file=sys.stderr); sys.exit(1)
content = content.replace(anchor, location_block + "\n" + anchor, 1)

if content == open(CONF_PATH).read():
    print("nginx config ja atualizada"); sys.exit(0)

backup = f"{CONF_PATH}.bak-modelos3d-{int(time.time())}"
shutil.copy2(CONF_PATH, backup)
with open(CONF_PATH, "w") as f:
    f.write(content)
print(f"nginx config atualizado (backup: {backup})")
PYEOF
' || { err "Falha ao atualizar nginx.conf"; exit 1; }
ok "Nginx config atualizado"

log "Step 4/4: Testando sintaxe e recarregando nginx..."
if vps "docker exec $NGINX_CONTAINER nginx -t" 2>&1; then
  vps "docker exec $NGINX_CONTAINER nginx -s reload"
  ok "Nginx recarregado (sem downtime)"
else
  err "nginx -t FALHOU — restaurando backup"
  LATEST_BAK=$(vps "ls -t ${NGINX_CONF}.bak-modelos3d-* 2>/dev/null | head -1" | tr -d '[:space:]')
  [ -n "$LATEST_BAK" ] && vps "cp '$LATEST_BAK' $NGINX_CONF" && \
    vps "docker exec $NGINX_CONTAINER nginx -t" && ok "Backup restaurado"
  err "Deploy abortado — nginx NAO recarregado"
  exit 1
fi

# ── Smoke tests ──────────────────────────────────────────────────────────────
log "Smoke tests..."
sleep 2
CODE=$(curl -sf -o /dev/null -w "%{http_code}" --max-time 15 "$PUBLIC_BASE/" || echo "000")
[ "$CODE" = "200" ] && ok "Site: $PUBLIC_BASE/ → 200" || { err "Site → HTTP $CODE"; exit 1; }

MANI=$(curl -sf --max-time 10 "$PUBLIC_BASE/manifest.json" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d['cases']))" 2>/dev/null || echo 0)
[ "$MANI" -gt 0 ] && ok "manifest.json OK ($MANI casos)" || { err "manifest.json falhou"; exit 1; }

GLB=$(curl -sf -o /dev/null -w "%{http_code}" --max-time 20 "$PUBLIC_BASE/models/$(ls "$MODELS_DIR" | head -1)")
[ "$GLB" = "200" ] && ok "GLB de teste → 200" || warn "GLB de teste → HTTP $GLB"

log "Apps vizinhos..."
for route in "/nginx-health" "/gpcg/api/health" "/gapi/health" "/3dpanel/api/health" "/"; do
  C=$(curl -sf -o /dev/null -w "%{http_code}" --max-time 10 "https://brunointegrations.com$route" 2>/dev/null || echo "000")
  case "$C" in 200|301|302|304|401|403) ok "  $route → $C";; *) warn "  $route → $C";; esac
done

echo ""
log "═══════════════════════════════════════════"
log "  Deploy concluído: $PUBLIC_BASE/"
log "═══════════════════════════════════════════"
