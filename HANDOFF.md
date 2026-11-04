# HANDOFF.md — Retomada por qualquer agente

> Leia isto DEPOIS de `PROGRESS.md` (fonte da verdade) e ANTES de executar qualquer coisa. Contexto mínimo para um agente frio continuar o projeto sem conversa anterior.

## Estado atual (2026-11-04, noite)

- **Fase 1 em andamento**: itens 1-5 concluídos; item 6 (benchmark) PARCIAL — trellis 7/10 OK, 3 OOM com retry pendente, triposr/render/publish pendentes (detalhes e comandos em `PROGRESS.md` §Registro Fase 1).
- Repo: `git@github.com:brunomrtns/3dprinter-setup-ia.git` · branch `main` · tudo pushed.
- Infra pronta e validada: venv `/home/bruno/.venvs/printer3d-ia` (py3.11, torch 2.5.1+cu121), TRELLIS em `~/tools/TRELLIS` (pesos `~/ai-models/trellis/TRELLIS-image-large`), TripoSR em `~/tools/TripoSR`, plugins + `gpu_guard.py` em `tools/generator/` (repo).
- Workdir do benchmark: `~/printer3d-work/benchmark/<caso>/<modo>/` (mesh.obj, mesh_reparada.obj, report.json por caso) — **estado resumível por design**.

## Retomada do benchmark (ordem exata)

1. `wsl bash ~/printer3d-work/retry_trellis.sh` — refaz os 3 OOM (castelo/caixote/robô) com alloc conf novo; se OOM persistir, registra como dado (VRAM é critério do benchmark, não bug).
2. `wsl bash ~/printer3d-work/run_bench.sh triposr` — 10 casos (~8 min GPU).
3. `wsl bash ~/printer3d-work/run_bench.sh render` — 40 previews Blender CPU (dono pode jogar durante esta etapa).
4. `wsl bash ~/printer3d-work/run_bench.sh publish` — escreve `evidence/benchmark/{results.json,scores.md,gallery.md,gallery/}`.
5. Revisar evidências → commit + push → dono vota 👍/👎 por caso → **ADR-005 default mode** → item 7 `[x]`.
- Caller script sempre re-copia `tools/generator/*.py` para `~/printer3d-work/gen/` (não editar em ~/printer3d-work, editar no repo).

## Decisões que você não deve reabrir sem motivo forte

- Multi-modo com pipeline comum e plugins de gerador (ADR-001)
- Headless/CLI primeiro; UI só com dor real (ADR-002)
- Local-first + sidecar de procedência obrigatório em TODO asset (ADR-003)
- venv isolado `printer3d-ia`; `game-ai3d` é intocável/referência (ADR-004)
- Jobs GPU sempre serializados com guard de VRAM (`docs/knowledge/wsl-gpu.md`) — **o dono joga no Windows**: nunca iniciar job GPU sem o guard; se VRAM ocupada, o guard espera (poll 1Hz), não força.

## Cuidados conhecidos do ambiente

- Python default do WSL é 3.14.4 — para stack CUDA use `/home/bruno/.venvs/printer3d-ia/bin/python`.
- ~1,2 GB de VRAM já consumidos pelo desktop Windows — TRELLIS image-large precisa de ~11,9 GB e OOM em casos densos (dado real do benchmark; 3/10 casos).
- `nvidia-smi` no WSL mostra a GPU do Windows (compartilhada) — OOM de um lado afeta o outro.
- Malhas TRELLIS brutas NÃO são manifold na maioria (FlexiCubes) — esperado; reparo pesado é Fase 2 (Forja). O benchmark mede isso honestamente (`manifold_antes→depois`).
- Integrar com PrintFlow3D SOMENTE via endpoints documentados em `docs/architecture.md` §6; procedência é registrada AQUI, não no painel.

## Se você é um agente retomando agora

1. Leia `PROGRESS.md` → este arquivo → `docs/roadmap.md` (fase corrente) → `AGENTS.md` (contrato).
2. Execute seguindo o fluxo de sessão (AGENTS.md §3): tarefa → validação → evidência em `evidence/` → atualizar `PROGRESS.md`/`HANDOFF.md` → commit convencional + push (commit sem push = falha).
3. Ambiente dual: Windows é host; Blender/CUDA/IA rodam no WSL (`wsl blender -b -P ...`, `wsl /home/bruno/.venvs/printer3d-ia/bin/python ...`). Caminhos `C:\foo` → `/mnt/c/foo`.
