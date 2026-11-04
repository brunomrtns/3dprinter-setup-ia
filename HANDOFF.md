# HANDOFF.md — Retomada por qualquer agente

> Leia isto DEPOIS de `PROGRESS.md` (fonte da verdade) e ANTES de executar qualquer coisa. Contexto mínimo para um agente frio continuar o projeto sem conversa anterior.

## Estado atual (2026-11-04)

- **Fase 1: benchmark CONCLUÍDO** (`evidence/benchmark/`: results.json, scores.md, gallery.md + 34 renders). Resumo: trellis 7/10 (3 OOM confirmados 2× em casos densos — limite físico da 3060 12GB), mediana 65,7s, VRAM 12.070 MiB, manifold 4/10, casca fina (pct5 0,002-0,008); triposr 10/10, mediana 27,3s, VRAM 3.588 MiB, manifold 9/10, casca mais grossa (0,016-0,176).
- **Único passo restante da Fase 1**: votação 👍/👎 do dono por caso na `gallery.md` → **ADR-005 (default mode)** → item 7 `[x]`.
- Repo: `git@github.com:brunomrtns/3dprinter-setup-ia.git` · branch `main` · tudo pushed.
- Infra pronta e validada: venv `/home/bruno/.venvs/printer3d-ia` (py3.11, torch 2.5.1+cu121), TRELLIS em `~/tools/TRELLIS` (pesos `~/ai-models/trellis/TRELLIS-image-large`), TripoSR em `~/tools/TripoSR`, plugins + `gpu_guard.py` em `tools/generator/` (repo).
- Malhas do benchmark em `~/printer3d-work/benchmark/<caso>/<modo>/` (mesh.obj, mesh_reparada.obj, report.json) — insumo da Fase 2 (Forja).

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
