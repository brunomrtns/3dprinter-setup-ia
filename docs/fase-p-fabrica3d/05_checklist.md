# 05 — Checklist executável da Fábrica 3D

> Granular, marcável, por milestone. Convencões do repo: `[x]` feito com evidência real ·
> toda etapa commitada + pushed · PROGRESS.md atualizado por marco.

## Pré (M1 — pipe_std) — BLOQUEANTE
- [ ] `pipeline/defaults.json` com os valores aprovados do Fox (2048, gutter, cos 0.80–0.92,
      w_max 0.8, SR x4, limiares de QA)
- [ ] `pipeline/run_asset.py` — 1 comando, `--resume` por etapa, cadeia completa aprovada
- [ ] Schema `assets/<id>.json` (tiers photos/single/none) + conversão do `cars/fox.json`
      sem mudar comportamento
- [ ] Pré-voo UV (estatísticas de ilhas; warning sem aborto)
- [ ] QA automático (`eval_texture.py` v2): lap_var, patches ≤ 0,01%, saturação, consistência
      fotográfica, MR presente → `qa.json` PASS/FAIL + crops padronizados
- [ ] Validação em 3 assets diversos (1 humanoide, 1 criatura, 1 prop — incluir Anubis entre
      eles se houver imagem local) — pinta o tier "single" e fecha a dúvida do Anubis
- [ ] Deploy dos aprovados + relatório de tempos/VRAM por tier

## M0 — Ratificação & higiene
- [ ] D1–D6 ratificados pelo dono (00 §6)
- [ ] Suíte `fabrica3d-docs` → `docs/fase-p-fabrica3d/`
- [ ] ADR-008: "Fábrica 3D — plataforma integrada + worker local"
- [ ] Fase P registrada no `docs/roadmap.md` (relação com C4 e Fase 4)
- [ ] Nota de uso privado/proibido comercial no README + docs da Fase P
- [ ] Inventário dos modelos publicados (lista mantém / backup+apaga) aprovado pelo dono
- [ ] Backup local dos que sairão (antes de qualquer remoção) — remoção é gate do dono

## M2 — VPS (API + web esqueleto)
- [ ] `factory/` monorepo pnpm+Turbo (api, web, packages) no padrão avesia
- [ ] Prisma: User/Asset/AssetVersion/Job/JobInput/ChatMessage (03 §3)
- [ ] Auth do ecossistema + RBAC (admin/user) + plugin worker-auth
- [ ] MinIO: bucket `fab3d/`, presigned URLs (upload direto + download autenticado)
- [ ] BullMQ: fila serial `fab3d-jobs`, claim com lease (worker morre → job volta)
- [ ] Rotas user: assets, inputs, jobs, approve/reject, download, chat
- [ ] Rotas worker: claim, progress, results, heartbeat, chat_reply
- [ ] nginx: `brunointegrations.com/fab3d/` (padrão das demais apps)
- [ ] Web: login padrão + home vazia + tema padrão + responsivo
- [ ] e2e mínimo (Playwright): login → criar draft → upload → job queued
- [ ] Auditoria de segredos no diff (zero `.env`/chaves commitados)

## M3 — Worker local
- [ ] `factory/worker` Python: poll → claim → download inputs → executar → upload → heartbeat
- [ ] Geração automática de `assets/<job>.json` por modo (single/multi/mesh) a partir do
      template do `defaults.json`
- [ ] Execução de `run_asset.py` com guard de VRAM + logger 10s + evidence por etapa
- [ ] Progresso por etapa → API (nomes de estágio mapeados para linguagem de UI)
- [ ] Upload: GLB 8K/4K + renders de revisão + qa.json → MinIO
- [ ] Falha: status `failed` + erro real + evidência; retry/retomada `--resume`
- [ ] `.env` do PC (WORKER_TOKEN, VPS_URL) fora do git; conexões só de saída
- [ ] Teste real: 1 job multi-foto de ponta a ponta com PC ligado; 1 teste com PC offline
      (job espera e retoma)

## M4 — Web UI completa + migração
- [ ] Wizard T3.3 (3 passos, zero knobs de qualidade, dicas de ângulo)
- [ ] Fila/status T3.6 (etapa amigável, posição, "worker offline")
- [ ] Viewer T3.4: three.js (base v19) + **toggle pintado/sem pintura** + downloads 8K/4K
- [ ] Review: renders + gates do qa.json em linguagem clara + aprovar/rejeitar
- [ ] Home T3.2: grid de peças do usuário + ações
- [ ] Migração: Fox `mv_b` + Anubis importados como peças do dono (com evidência/qa)
- [ ] Remoção dos descartados (após backup; gate do dono)
- [ ] Destino do MODELOS 3D antigo conforme D2
- [ ] e2e: J1 (multi-foto completo), J2 (1 foto), J4 (foto ruim → rembg), download, toggle
- [ ] **Veredito visual do dono no viewer (gate final de publicação)**

## M5 — Assistente de imagem
- [ ] Detector genérico de entrada fraca (luminância, fundo pós-rembg, resolução)
- [ ] Oferta na UI com explicação honesta
- [ ] Integração Gemini/Nano Banana no worker (chave no `.env` do PC) + prompt padrão do sistema
- [ ] Comparação antes/depois na UI antes de confirmar; cache por job
- [ ] Teste com foto real de fundo bagunçado

## M6 — Modo edição agêntico
- [ ] Rotas de chat + persistência por peça
- [ ] Agente GLM no worker (Z.ai API) com contexto: pedido, qa.json resumido, catálogo
- [ ] Catálogo whitelist fechado (run_asset, patch_repair, photo_blend, eval_texture, pack_glb,
      render blender) — nada fora
- [ ] Plano visível na UI antes de executar; execução logada em evidence (comando/exit/VRAM)
- [ ] Guardrails: seed 42 fixo, máx. passos, timeout, sem rede além de VPS/Z.ai,
      **publish nunca é ação do agente**
- [ ] Resposta do agente com antes/depois + métricas → review → aprovação humana
- [ ] Teste de segurança: pedido que tente comando fora da whitelist → bloqueado + logado
- [ ] Teste real do dono: "limpar rabiscos da traseira" de ponta a ponta

## M7 — Fechamento
- [ ] Relatório técnico completo no chat (tempos, VRAM, QA, incidentes)
- [ ] PROGRESS.md / HANDOFF.md finais + tag de versão
- [ ] Lições aprendidas → `docs/knowledge/`
- [ ] Backlog honesto: múltiplos workers, Fase 3 Pose, Forja, novos tiers
- [ ] Dono declara ciclo encerrado

## Checklist transversal (TODOS os milestones)
- [ ] Seed 42 · guard de VRAM · logger 10s · evidence por etapa
- [ ] Commit conventional + push por marco · PROGRESS.md atualizado
- [ ] Zero segredos no diff · uso privado nos docs
- [ ] ZIP de entrega só após meu veredito visual
- [ ] Nada publicado sem gate humano
