# ADR-008 — Fábrica 3D: plataforma de produto integrada ao ecossistema com worker local

- **Status:** Aceito (ratificado pelo dono em 2026-11-20 via `prompt_fab3d_mega_v1.md`)
- **Data:** 2026-11-20
- **Fase:** Fase P — Fábrica 3D (absorve C4 "Fila de jobs entre máquinas" e concretiza partes da Fase 4 "Operador IA")
- **Documentos relacionados:** `docs/fase-p-fabrica3d/{00_visao_geral,01_estudo_tecnico,02_prd,03_arquitetura,04_roadmap,05_checklist}.md`

## Contexto

Com a conclusão do benchmark C5 (TripoSG → TripoSF512), do pipeline multi-vista do Fox (`mv_b` 8K PBR) e da padronização universal `pipe_std` (`pipeline/run_asset.py` + `defaults.json` + QA automático validado em 3 assets diversos), o laboratório atingiu maturidade para virar um produto de uso contínuo integrado ao ecossistema **Bruno Integrations** — sem expor sliders técnicos ao usuário e preservando o gate humano antes de qualquer publicação.

## Decisão

1. **Monorepo único (`3dprinter-setup-ia`) + módulo `factory/`:**
   - `factory/api`: Fastify + Prisma (Postgres) + Redis/BullMQ + MinIO, com containers dedicados (`fab3d-postgres`, `fab3d-redis`, `fab3d-minio`, sem tocar nos containers de outras apps).
   - `factory/web`: React + Vite (tema padrão Bruno Integrations, viewer Three.js derivado do MODELOS 3D v19 com toggle Pintado / Sem pintura e downloads 8K/4K), servido em `https://brunointegrations.com/fab3d/`.
   - `factory/worker`: Worker Python local rodando na máquina do dono (RTX 3060 12GB), conexões **exclusivamente de saída** (poll → claim → download → `pipeline/run_asset.py` com `gpu_guard.py` + `seed 42` + VRAM 10s → upload → heartbeat).
2. **Decisões ratificadas (D1–D6):**
   - **D1:** Nome **Fábrica 3D**, rota `/fab3d/`.
   - **D2:** Galeria inicial enxuta: Fox `mv_b` 8K/4K + Anubis vencedor (`anubis_a__triposf512.glb`, `anubis_b__triposf512.glb`) + 3 assets PBR do `pipe_std` (`humanoide_dragonborn`, `criatura_dragao`, `prop_caixote`); demais GLBs arquivados em backup completo reversível antes da remoção.
   - **D3:** Blueprint `avesia` (Fastify + Prisma + Postgres + Redis/BullMQ + MinIO + React/Vite + `worker-python`).
   - **D4:** Modo edição agêntico operado por GLM via API Z.ai dentro do worker, sob whitelist fechada de ferramentas e gate humano obrigatório (o agente nunca publica).
   - **D5:** Assistente de imagem com `rembg` local por padrão e re-render externo opcional (feature-flag OFF sem chave).
   - **D6:** Acesso privado (conta única do dono no M4; sem self-service).
3. **Licença e Segurança:**
   - **Uso estritamente privado e pessoal. Proibido uso comercial**, venda, sublicenciamento ou prestação de serviço.
   - Repositório público: zero segredos commitados; todas as chaves/tokens vivem exclusivamente em `.env` na VPS e no PC (fora do git).

## Consequências

- **Positivas:** elimina execução manual via CLI para uso diário; fila serial com lease garante que jobs sobrevivem a PC offline ou reinício (`--resume`); isolamento total de containers protege apps vizinhos (`modelos3d`, `avesia`, `portfolio`).
- **Trade-offs:** worker único serializado limita throughput a 1 job de GPU por vez (aceito explicitamente pelo dono).
