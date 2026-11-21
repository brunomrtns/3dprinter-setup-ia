#!/usr/bin/env bash
# Deploy da Fábrica 3D (factory/) para a VPS — containers dedicados + rota /fab3d/ e /api/fab3d/
# NUNCA toca containers ou rotas de outras apps (modelos3d, avesia, gpcg, 3dpanel, portfolio).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VPS_DIR="/opt/fab3d"
NGINX_CONTAINER="trivestia-nginx"
NGINX_CONF="/opt/trivestia/nginx/nginx.conf"

vps() { my-vps --no-lock "$@"; }
log() { echo -e "\033[1;34m[fab3d-deploy]\033[0m $*"; }
ok()  { echo -e "\033[1;32m  ✓\033[0m $*"; }
err() { echo -e "\033[1;31m  ✗\033[0m $*" >&2; }

command -v my-vps &>/dev/null || { err "my-vps não encontrado"; exit 1; }

log "Step 0/5: Verificando apps existentes ANTES do deploy..."
for path in "/modelos3d/" "/gpcg/api/health" "/3dpanel/api/health" "/"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "https://brunointegrations.com${path}")
  [ "$code" = "200" ] || { err "App existente falhou ANTES do deploy: ${path} -> ${code}"; exit 1; }
  ok "Pre-check ${path} -> 200"
done

log "Step 1/5: Sincronizando factory/ para ${VPS_DIR}..."
vps "mkdir -p ${VPS_DIR}"
my-vps --no-lock --rsync "$SCRIPT_DIR/" "${VPS_DIR}/" \
  --rsync-args "--exclude=node_modules --exclude=dist --exclude=.env --exclude=worker/.venv --exclude=__pycache__"
ok "Arquivos sincronizados"

log "Step 2/5: Garantindo .env dedicado na VPS (sem imprimir segredos)..."
vps "if [ ! -f ${VPS_DIR}/.env ]; then
  PG_PW=\$(openssl rand -hex 16)
  MINIO_PW=\$(openssl rand -hex 16)
  JWT_SEC=\$(openssl rand -hex 32)
  W_TOK=\$(openssl rand -hex 24)
  ADM_PW=\$(openssl rand -hex 12)
  cat > ${VPS_DIR}/.env <<EOF
POSTGRES_USER=fab3d
POSTGRES_PASSWORD=\${PG_PW}
POSTGRES_DB=fab3d
DATABASE_URL=postgresql://fab3d:\${PG_PW}@fab3d-postgres:5432/fab3d
REDIS_HOST=fab3d-redis
REDIS_PORT=6379
MINIO_ENDPOINT=fab3d-minio
MINIO_PORT=9000
MINIO_USE_SSL=false
MINIO_ROOT_USER=fab3dadmin
MINIO_ROOT_PASSWORD=\${MINIO_PW}
MINIO_BUCKET=fab3d
PUBLIC_BASE_URL=https://brunointegrations.com/fab3d
JWT_SECRET=\${JWT_SEC}
ADMIN_EMAIL=bruno@brunointegrations.com
ADMIN_PASSWORD=\${ADM_PW}
ADMIN_NAME=Bruno
WORKER_TOKEN=\${W_TOK}
JOB_LEASE_MINUTES=30
EOF
  chmod 600 ${VPS_DIR}/.env
  echo 'ENV_CREATED'
else
  echo 'ENV_EXISTS'
fi"
ok ".env dedicado pronto em ${VPS_DIR}/.env (chmod 600)"

log "Step 3/5: Subindo containers dedicados fab3d-* (docker compose up -d --build)..."
vps "cd ${VPS_DIR} && docker compose up -d --build"
ok "Containers fab3d-* rodando"

log "Step 4/5: Injetando rotas /fab3d/ e /api/fab3d/ no ${NGINX_CONTAINER} (idempotente com rollback)..."
vps 'python3 << "PYEOF"
import re, shutil, time, subprocess, sys

CONF = "/opt/trivestia/nginx/nginx.conf"
BAK = f"{CONF}.bak_fab3d_{int(time.time())}"
shutil.copy2(CONF, BAK)

with open(CONF, "r", encoding="utf-8") as f:
    content = f.read()

block = """    # ── Fábrica 3D (Fase P) ──────────────────────────────────────────
    location = /fab3d {
        return 301 /fab3d/;
    }
    location /api/fab3d/ {
        client_max_body_size 100m;
        resolver 127.0.0.11 valid=10s;
        set $fab3d_api http://fab3d-api:3100;
        proxy_pass         $fab3d_api;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
    location /fab3d/ {
        resolver 127.0.0.11 valid=10s;
        set $fab3d_web http://fab3d-web:80;
        rewrite ^/fab3d/(.*)$ /$1 break;
        proxy_pass         $fab3d_web;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        add_header         Cache-Control "no-cache";
    }
"""

# Remove previous fab3d block if any
content = re.sub(r"    # ── Fábrica 3D \(Fase P\).*?location /fab3d/ \{.*?\n    \}\n?", "", content, flags=re.DOTALL)

# Insert right before Modelos 3D block (or last closing brace of server block)
anchor = "    # ── Modelos 3D"
if anchor in content:
    content = content.replace(anchor, block + "\n" + anchor, 1)
else:
    idx = content.rfind("}")
    content = content[:idx] + "\n" + block + "\n" + content[idx:]

with open(CONF, "w", encoding="utf-8") as f:
    f.write(content)

t = subprocess.run(["docker", "exec", "trivestia-nginx", "nginx", "-t"], capture_output=True, text=True)
if t.returncode != 0:
    shutil.copy2(BAK, CONF)
    print(t.stderr, file=sys.stderr)
    sys.exit(1)

subprocess.run(["docker", "exec", "trivestia-nginx", "nginx", "-s", "reload"], check=True)
print("NGINX_FAB3D_OK")
PYEOF'
ok "Nginx recarregado sem downtime"

log "Step 5/5: Smoke tests pós-deploy (fab3d + apps existentes)..."
sleep 3
for path in "/fab3d/" "/api/fab3d/health" "/modelos3d/" "/gpcg/api/health" "/3dpanel/api/health" "/"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "https://brunointegrations.com${path}")
  [ "$code" = "200" ] || { err "Pós-check falhou: ${path} -> ${code}"; exit 1; }
  ok "Post-check ${path} -> 200"
done

log "Deploy Fábrica 3D concluído: https://brunointegrations.com/fab3d/"
