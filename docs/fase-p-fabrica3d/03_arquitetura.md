# 03 — Arquitetura: Fábrica 3D

> Decisão estrutural → vira ADR (008+) no monorepo. Uso privado; zero segredos aqui.

## 1. Forma geral

**Monorepo único** (`3dprinter-setup-ia`) recebendo um novo módulo de produto, seguindo o
blueprint comprovado do avesia (mesma família de stack do portfolio-v2):

```
3dprinter-setup-ia/
├── pipeline/                  # existente — ferramentas de pintura/geração (run_asset.py a partir do pipe_std)
├── assets/                    # existente (pipe_std) — configs por asset
├── tools/generator/           # existente — gpu_guard, preprocess_input
├── tools/modelos3d-site/      # existente — vira referência do viewer (absorvido pela web)
├── evidence/                  # existente — evidência de TODA execução do worker
├── docs/fase-p-fabrica3d/     # ESTA suíte de documentação
└── factory/
    ├── api/                   # Fastify + Prisma (Postgres) — auth, peças, jobs, downloads
    ├── web/                   # React+Vite — login, wizard, fila, viewer, chat (tema padrão)
    └── worker/                # Python — worker local do PC (fila → run_asset.py → upload)
```

## 2. Componentes

### 2.1 VPS — `factory/api` (Fastify + Prisma + Postgres + Redis + MinIO)
- **Auth**: mesma do ecossistema (usuários do Bruno Integrations; RBAC simples: dono/admin +
  usuário). Plugin `worker-auth` (token de worker) como no avesia.
- **Fila**: BullMQ sobre Redis — fila única serial (`fab3d-jobs`), pois a GPU é serializada
  (regra 9 do AGENTS.md). Estados persistidos no Postgres (fonte da verdade) + Redis para
  filas/cache.
- **Storage**: MinIO — `fab3d/<user>/<asset>/<job>/` (inputs, glb_8k, glb_4k, renders, qa.json,
  chat.json). Evidência pesada fica no PC; VPS guarda o produto.
- **Downloads**: presigned URLs autenticadas.
- **Agente**: a VPS NÃO chama GLM — só transporta mensagens do chat para o job de edição.

### 2.2 PC do dono — `factory/worker` (Python)
- Loop: **poll → claim → executar → reportar progresso → upload resultados → heartbeat**.
  Apenas conexão de SAÍDA para a VPS (nada de portas abertas no PC) + API Z.ai (agente) e,
  opcionalmente, API de imagem (Gemini/Nano Banana no M5).
- Executa o pipeline real: `python pipeline/run_asset.py --config assets/<job>.json`
  (herdando seed 42, guard `gpu_guard.py`, logger de VRAM 10s, evidence por etapa).
- Sobe resultados: GLBs 8K/4K + renders de revisão + qa.json.
- **Agente GLM (modo edição)**: roda no worker (onde estão ferramentas+GPU) — ver §6.
- Config em `.env` no PC (fora do git): `WORKER_TOKEN`, `ZAI_API_KEY`, `VPS_URL`.
- Offline = só não consome a fila; jobs esperam. Retomada de job interrompido via `--resume`.

### 2.3 Web — `factory/web` (React+Vite)
- Telas do PRD (02 §3), tema padrão (mesma base do avesia: `LoginPage`, `theme-store`,
  `auth-store`), viewer three.js derivado do MODELOS 3D v19 + **toggle pintado/sem pintura**
  (sem pintura = material neutro) + botões de download.
- Rota nginx: `brunointegrations.com/fab3d/` (padrão das demais apps).

## 3. Modelo de dados (Postgres/Prisma)

| Tabela | Campos essenciais |
|---|---|
| `User` | id, email, nome, role (admin/user) — herda do ecossistema |
| `Asset` | id, user_id, name, mode (single/multi/mesh), status, current_version, created_at |
| `AssetVersion` | id, asset_id, job_id, files (keys MinIO), qa_json, published_at |
| `Job` | id, asset_id, type (new/edit), mode, status, stage, progress, worker_id, error, timestamps |
| `JobInput` | job_id, kind (photo/mesh), key MinIO, meta (resolução, ângulo declarado) |
| `ChatMessage` | job_id, role (user/agent/system), content, plan_json, artifacts, created_at |

## 4. Ciclo de vida do job

```
draft → queued → claimed → running(stage: preprocess|shape|paint|pbr|pack|qa)
      → review (renders prontos, espera dono)
      → published | rejected(volta p/ edit) | failed
      (edit: review → edit_queued → running → review … loop)
```

- `review` = gate humano. `publish` = versão nova do AssetVersion.
- Estágios do worker mapeados 1:1 nas etapas do `run_asset.py` (mesmos nomes → UI traduz).

## 5. Contratos de API (v1)

| Método & rota | Auth | Descrição |
|---|---|---|
| `POST /api/fab3d/assets` | user | cria draft {name, mode} |
| `POST /api/fab3d/assets/:id/inputs` | user | upload multipart das fotos/malha → MinIO |
| `POST /api/fab3d/jobs` | user | {asset_id} → 202 {job_id, position} |
| `GET /api/fab3d/jobs/:id` | user | status, stage, progress, position |
| `POST /api/fab3d/jobs/:id/approve` | admin | publica versão |
| `POST /api/fab3d/jobs/:id/reject` | admin | volta para edição (com comentário) |
| `GET /api/fab3d/assets/:id/download?variant=8k\|4k` | user | presigned URL |
| `POST /api/fab3d/assets/:id/chat` | user | mensagem → cria edit job |
| `GET /api/fab3d/assets/:id/chat` | user | histórico |
| `POST /api/fab3d/worker/claim` | worker | claim do próximo job queued (lease de X min) |
| `PATCH /api/fab3d/worker/jobs/:id/progress` | worker | {stage, pct, metrics} |
| `POST /api/fab3d/worker/jobs/:id/results` | worker | manifest de arquivos → MinIO (multipart) |
| `POST /api/fab3d/worker/heartbeat` | worker | vivo, job atual, VRAM livre |
| `POST /api/fab3d/worker/jobs/:id/chat_reply` | worker | resposta/plano do agente |

## 6. Agente GLM de edição (Z.ai API)

- **Onde roda:** worker (PC). Modelo: GLM (chave `ZAI_API_KEY` só no `.env` do PC).
- **Contexto enviado ao modelo:** pedido do usuário, metadata da peça, qa.json resumido,
  últimas renders (como imagens se o modelo aceitar, senão métricas), catálogo de ferramentas.
- **Catálogo de ferramentas (whitelist fechada):**
  `pipeline/run_asset.py` (re-pintura/reparo com overrides do config), `pipeline/patch_repair.py`,
  `pipeline/photo_blend.py`, `pipeline/eval_texture.py`, `pipeline/pack_glb.py`,
  render blender para crops/vistas. **Fora da whitelist: nada.**
- **Guardrails:**
  1. Toda execução logada em `evidence/` (comando, stdout/exit, VRAM);
  2. Sem rede além de VPS/Z.ai; sem escrever fora do workspace do job;
  3. seed 42 fixo — não é parâmetro do agente;
  4. Máx. N passos por pedido (ex.: 10) e timeout por passo;
  5. **Publish NUNCA é ação do agente** — resultado vai para `review` e o dono aprova;
  6. Job de edição por vez (fila serial).
- **Fluxo:** user_message → GLM devolve `{plan[], commands[]}` → worker valida whitelist →
  executa → coleta métricas/crops → GLM resume resultado → `chat_reply` → UI mostra antes/depois.

## 7. Assistente de imagem (M5)

1. **Embutido (já existe):** `tools/generator/preprocess_input.py` (rembg + pad quadrado + 1024)
   roda como primeira etapa do job — a foto "sujas" nunca chega à geração.
2. **Oferta na UI:** se a entrada for fraca (detectável por métricas simples: luminância baixa,
   fundo complexo pós-rembg, resolução), a UI oferece re-render via **Gemini/Nano Banana**
   (prompt padrão do sistema: "fotografia de produto limpa do MESMO objeto, fundo neutro,
   iluminação uniforme, enquadramento central") — chave só no `.env` do PC; comparação
   antes/depois na UI antes de confirmar. Sempre opcional.

## 8. Segurança

| Risco | Mitigação |
|---|---|
| Segredos vazados em repo/docs | `.env` fora do git; docs auditados; repo público tratado como público |
| PC exposto | Worker só faz conexões de saída; sem portas abertas; token de worker revogável |
| Upload malicioso | Validar mime/tamanho; quarentena: job só executa após validação da API; malhas passam por inspeção (trimesh) antes de tocar blender/pipeline |
| Agente fora de controle | Whitelist fechada + evidence + gate humano + limite de passos (§6) |
| Publicação indevida | Só `admin` publica; galeria pública só com peças aprovadas e procedência OK (ADR-003) |
| Uso comercial | Nota de licença em todos os docs + UI ("uso privado"); contas criadas só pelo dono |

## 9. Deploy & operação

- VPS: docker-compose (padrão avesia: api/web/postgres/redis/minio/nginx) + `deploy.sh`.
- PC: `factory/worker` rodando como script/serviço quando o dono liga a máquina; log local +
  heartbeat (a UI mostra "worker offline").
- Observabilidade: heartbeat + métricas por job na UI; `PROGRESS.md`/`HANDOFF.md` do monorepo
  continuam sendo a fonte da verdade do desenvolvimento.
