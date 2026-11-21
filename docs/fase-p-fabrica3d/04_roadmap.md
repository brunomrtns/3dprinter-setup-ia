# 04 — Roadmap da Fábrica 3D (M0–M7)

> Cada milestone = critérios de aceite objetivos + o prompt que eu (Z.ai) gero quando ele
> começa. Respeita o contrato do `AGENTS.md`: docs antes de código, evidência real, commit+push
> por marco, PROGRESS.md atualizado.

## Pré-requisito global
**M1 (pipe_std) concluído** — runner único (`run_asset.py`), `assets/<id>.json`,
`defaults.json`, QA PASS/FAIL. Tudo abaixo consome esse contrato. O prompt
`prompt_pipe_std_v1.md` já existe; se o run ainda não rodou, é o primeiro passo.

## M0 — Ratificação & higiene (metade chat, metade repo)
- **Objetivo:** travar decisões antes de codar e limpar o terreno.
- **Atividades:** dono ratifica D1–D6 (00 §6) · esta suíte entra em `docs/fase-p-fabrica3d/` ·
  ADR-008 (Fábrica 3D: plataforma integrada + worker local) · entrada no `docs/roadmap.md` como
  Fase P · **inventário dos modelos publicados** com lista "mantém / backup+apaga" (proposta:
  mantém Fox `mv_b` 8K/4K + Anubis vencedor; o resto vai para backup local antes de qualquer
  remoção) · nota de licença/uso privado no README e nos docs.
- **Aceite:** docs commitados + ADR + PROGRESS.md/HANDOFF.md atualizados + inventário aprovado
  pelo dono (gate humano — remoção é destrutiva).
- **Prompt:** um só (`prompt_fab3d_m0.md`) — eu gero sob demanda.

## M2 — VPS: API + auth + storage (esqueleto do produto)
- **Objetivo:** esqueleto `factory/` (api+web+worker stub) no padrão avesia, deployado.
- **Atividades:** monorepo pnpm/Turbo dentro de `factory/` · Fastify+Prisma (Postgres) com as
  tabelas de 03 §3 · rotas de auth do ecossistema + plugin worker-auth · MinIO + presigned
  URLs · fila BullMQ (Redis) com claim/lease · rotas de worker (claim/progress/results/
  heartbeat) · nginx `brunointegrations.com/fab3d/` · web com login padrão + home vazia.
- **Aceite:** login funciona; upload de foto cai no MinIO; job entra na fila e fica `queued`;
  e2e mínimo (Playwright) de login+upload; sem segredos no repo.
- **Prompt:** 1–2 prompts (api / web).

## M3 — Worker local: fila → pipeline → upload
- **Objetivo:** o PC do dono processa jobs de verdade.
- **Atividades:** `factory/worker` (Python): claim/lease, download dos inputs, criação de
  `assets/<job>.json` a partir do template do modo (single/multi/mesh), execução do
  `run_asset.py` com guard+evidência, progresso por etapa → API, upload de GLBs/renders/qa.json,
  heartbeat, retomada `--resume`, tratamento de falha (status `failed` + erro real).
- **Aceite:** job multi-foto sobe na UI do M2 e sai do worker com GLBs 8K/4K + qa.json no
  MinIO, passando pelo gate de review; job com PC offline espera e retoma; evidence completa.
- **Prompt:** 1.

## M4 — Web UI completa + migração dos modelos
- **Objetivo:** o produto utilizável de ponta a ponta.
- **Atividades:** wizard 3 passos (T3.3) · fila/status (T3.6) · viewer com **toggle pintado/
  sem pintura** + downloads (T3.4) · review com renders+QA e botões aprovar/rejeitar ·
  **migração**: Fox `mv_b` + Anubis viram peças do dono no sistema (import dos GLBs/evidência) ·
  remoção dos modelos descartados (após backup, gate do dono) · MODELOS 3D antigo vira redirec-
  ionamento ou fica como galeria pública estática (decisão D2).
- **Aceite:** J1–J4 do PRD funcionam no navegador (e2e Playwright); peças migradas visíveis e
  baixáveis; dono aprova visualmente (gate final).
- **Prompt:** 1–2.

## M5 — Assistente de imagem
- **Objetivo:** entrada ruim deixa de ser problema.
- **Atividades:** detecção de entrada fraca (métricas simples) · oferta na UI · integração
  Gemini/Nano Banana no **worker** (chave no `.env` do PC) com prompt padrão · antes/depois na
  UI antes de confirmar · cache do re-render por job.
- **Aceite:** foto de teste com fundo bagunçado entra, é limpa (rembg) e, se ofertada, re-gerada
  com comparação visível; usuário escolhe qual usar; nenhum segredo em repo.
- **Prompt:** 1.

## M6 — Modo edição agêntico (chat GLM)
- **Objetivo:** "arruma isso" funciona com segurança.
- **Atividades:** rotas de chat (03 §5) · agente no worker com catálogo whitelist fechado
  (03 §6) · plano visível na UI antes de executar · execução logada em evidence · resposta com
  antes/depois + métricas · gate humano para publicar · limite de passos/timeout · chat
  persistido por peça.
- **Aceite:** pedido real do dono (ex.: "limpar rabiscos da traseira") resulta em plano →
  execução → antes/depois → aprovação → versão nova publicada; tentativa de comando fora da
  whitelist é bloqueada e logada.
- **Prompt:** 1–2 (agente + UI do chat).

## M7 — Fechamento do ciclo
- **Objetivo:** encerrar a Fase P com estado limpo.
- **Atividades:** relatório técnico completo no chat · PROGRESS.md/HANDOFF.md finais ·
  tag/versão no monorepo · lições aprendidas → `docs/knowledge/` · backlog honesto do que
  ficou para depois (ex.: múltiplos workers, Fase 3 Pose).
- **Aceite:** zero pendência `[!]` sem causa/registro; dono declara o ciclo encerrado.

## Dependências e ordem

```
M1(pipe_std) ──► M0 ──► M2 ──► M3 ──► M4 ──► M7
                          (M2∥M3 parcial)      ├─► M5 (após M4)
                                               └─► M6 (após M4; pode antecipar após M3)
```

- M0 antes de M2 porque o ADR e o inventário travam escopo (e a remoção de modelos é destrutiva).
- M5 e M6 são independentes entre si; ambos dependem de M4 (UI) e M3 (worker).
- Cada prompt mantém as políticas de sempre: seed 42, guard, VRAM 10s, evidence por etapa,
  commit+push por marco, relatório técnico no chat, **ZIP só após veredito visual**.

## Riscos (honestos)

| Risco | Mitigação |
|---|---|
| pipe_std atrasar/reprovar nos 3 assets | M1 é bloqueante; sem ele M3 não começa |
| Temporizamento de GPU (PC offline) | Fila com lease; retomada `--resume`; UI honesta |
| Agente GLM executando algo errado | Whitelist + evidence + review humano; nunca publica |
| Uploads pesados (8K ~20 MB) na VPS | Presigned URLs direto pro MinIO; variantes 4K para o viewer |
| Scope creep (múltiplos workers, pose, forja) | Fora de escopo explícito (00 §3); backlog no M7 |
