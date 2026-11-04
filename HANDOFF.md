# HANDOFF.md — Retomada por qualquer agente

> Leia isto DEPOIS de `PROGRESS.md` (fonte da verdade) e ANTES de executar qualquer coisa. Contexto mínimo para um agente frio continuar o projeto sem conversa anterior.

## Estado atual (2026-11-03)

- **Fase 0 concluída tecnicamente**, aguardando aprovação do dono → gate para a Fase 1.
- Repo: `git@github.com:brunomrtns/3dprinter-setup-ia.git` · branch `main` · tudo pushed.
- Ambiente auditado e verde (Blender 5.0.1 no WSL, CUDA funcional, disco folgado) — `docs/operations/environment-audit.md`.
- Nenhum código de pipeline existe ainda (por design — Fase 0 é documentação). `tools/*/` estão vazios com `.gitkeep`.

## Se você é um agente retomando agora

1. Leia `PROGRESS.md` → este arquivo → `docs/roadmap.md` (fase corrente) → `AGENTS.md` (contrato).
2. **Confirme a fase autorizada.** A Fase 0 terminou; a Fase 1 (venv + TRELLIS + benchmark) só começa com aprovação do dono registrada em `PROGRESS.md`. Não antecipe.
3. Execute seguindo o fluxo de sessão (AGENTS.md §3): tarefa → validação → evidência em `evidence/` → atualizar `PROGRESS.md`/`HANDOFF.md` → commit convencional + push (commit sem push = falha).
4. Ambiente dual: Windows é host; Blender/CUDA/IA rodam no WSL (`wsl blender -b -P ...`, `wsl /home/bruno/.venvs/printer3d-ia/bin/python ...` — venv a criar na Fase 1). Caminhos `C:\foo` → `/mnt/c/foo`.

## Decisões que você não deve reabrir sem motivo forte

- Multi-modo com pipeline comum e plugins de gerador (ADR-001)
- Headless/CLI primeiro; UI só com dor real (ADR-002)
- Local-first + sidecar de procedência obrigatório em TODO asset (ADR-003)
- venv isolado `printer3d-ia`; `game-ai3d` é intocável/referência (ADR-004)
- Jobs GPU sempre serializados com guard de VRAM (`docs/knowledge/wsl-gpu.md`)

## Cuidados conhecidos do ambiente

- Python default do WSL é 3.14.4 — para stack CUDA use `/usr/bin/python3.11` (audit, Pendência #1).
- ~1.2 GB de VRAM já consumidos pelo desktop Windows em repouso — nunca orçar os 12 GB inteiro.
- `nvidia-smi` no WSL mostra a GPU do Windows (compartilhada) — OOM de um lado afeta o outro.
- Integrar com PrintFlow3D SOMENTE via endpoints documentados em `docs/architecture.md` §6; procedência é registrada AQUI, não no painel.

## Gatilho para iniciar a Fase 1

1. Dono registra 👍 na Fase 0 (conversa com o dono → marcar item 12 de `PROGRESS.md` como `[x]`).
2. Seguir `docs/roadmap.md` §Fase 1 e as pendências #1–#2 do audit.
3. Primeiro passo canônico: criar o venv isolado `/home/bruno/.venvs/printer3d-ia` com `python3.11` e evidenciar que `game-ai3d` permaneceu intocado.
