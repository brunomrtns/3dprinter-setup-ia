# HANDOFF.md — Retomada por qualquer agente

> Leia isto DEPOIS de `PROGRESS.md` (fonte da verdade) e ANTES de executar qualquer coisa. Contexto mínimo para um agente frio continuar o projeto sem conversa anterior.

## Estado atual (2026-11-14)

- **Fase 1** segue com o único passo pendente: votação 👍/👎 do dono por caso na `gallery.md` → **ADR-005 (default mode)**.
- **Novo: onboarding multi-máquina** na branch `feat/onboarding-multi-maquina` (aguardando merge do dono): perfis de máquina (`docs/operations/machine-profiles/`), guard de VRAM paramétrico, `tools/setup/` idempotente, `docs/onboarding/` completo + ADR-006. 2º contribuidor (máquina RTX 5060 Ti 8GB, Blackwell sm_120): **Fase A concluída e auditada 2026-11-15** (`evidence/rtx5060ti-8gb/environment-audit-fase-a.md`); Fase B após o merge (`PROMPT-ONBOARDING-B.md`).
- **Fase 1 Forja CONCLUÍDA** (`tools/forja/forja/`; workspace `~/printer3d-work/forja/`): 7/7 TRELLIS reparados, gate PASS em `evidence/fase1-forja/gate_final.txt`.
- Benchmark Fase 1 concluído (`evidence/benchmark/`): TRELLIS 65,7s/12.070 MiB (3/10 OOM em casos densos) · TripoSR 27,3s/3.588 MiB (0/10 erros).
- Repo: `git@github.com:brunomrtns/3dprinter-setup-ia.git` · main + branch `feat/onboarding-multi-maquina` · tudo pushed.
- Infra pronta e validada (PC de referência): venv `~/.venvs/printer3d-ia` (py3.11, torch 2.5.1+cu121), TRELLIS em `~/tools/TRELLIS`, TripoSR em `~/tools/TripoSR`, plugins + `gpu_guard.py` em `tools/generator/`.
- **Forja é CPU-only** (PyMeshFix + Blender headless): pode rodar enquanto o dono joga. Não altera entradas; saídas sempre em `forja_out/`. APIs novas: trimesh 5.2, pymeshfix `.points/.faces`.

## Decisões que você não deve reabrir sem motivo forte

- Multi-modo com pipeline comum e plugins de gerador (ADR-001)
- Headless/CLI primeiro; UI só com dor real (ADR-002)
- Local-first + sidecar de procedência obrigatório em TODO asset (ADR-003)
- venv isolado `printer3d-ia`; `game-ai3d` é intocável/referência (ADR-004)
- Multi-máquina: caminhos portáveis, perfis por máquina, guard paramétrico, evidências namespaced (ADR-006)
- Jobs GPU sempre serializados com guard de VRAM (`docs/knowledge/wsl-gpu.md`) — **o dono joga no Windows**: nunca iniciar job GPU sem o guard; se VRAM ocupada, o guard espera (poll 1Hz), não força.

## Cuidados conhecidos do ambiente

- Python default do WSL é 3.14.4 — para stack CUDA use `tools/setup/py.sh` ou `~/.venvs/printer3d-ia/bin/python` (venv do projeto, qualquer máquina — ADR-006).
- ~1,2 GB de VRAM já consumidos pelo desktop Windows na 3060 — TRELLIS precisa de ~11,9 GB e OOM em casos densos (dado real do benchmark; 3/10 casos).
- `nvidia-smi` no WSL mostra a GPU do Windows (compartilhada) — OOM de um lado afeta o outro.
- Guard de VRAM é **paramétrico por perfil** (ADR-006): default = perfil rtx3060-12gb (10.000 MiB); `PRINTER3D_MACHINE_PROFILE=rtx5060ti-8gb` → 6500 MiB **confirmado** (audit Fase A 2026-11-15: 6803 MiB livres com desktop ativo). Nessa máquina, fechar navegadores/jogos/overlay NVIDIA antes de jobs GPU (margem pequena). Números ainda "A VALIDAR (Fase B)" não são medidas — proibido citá-los como medidos.
- Malhas TRELLIS brutas NÃO são manifold na maioria (FlexiCubes) — esperado; reparo pesado é Fase 2 (Forja). O benchmark mede isso honestamente (`manifold_antes→depois`).
- Integrar com PrintFlow3D SOMENTE via endpoints documentados em `docs/architecture.md` §6; procedência é registrada AQUI, não no painel.

## Se você é um agente retomando agora

1. Leia `PROGRESS.md` → este arquivo → `docs/roadmap.md` (fase corrente) → `AGENTS.md` (contrato; §7 se você opera na máquina de um contribuidor).
2. Execute seguindo o fluxo de sessão (AGENTS.md §3): tarefa → validação → evidência em `evidence/` (namespaced por máquina — ADR-006) → atualizar `PROGRESS.md`/`HANDOFF.md` → commit convencional + push (commit sem push = falha). Contribuidor só pusha em branch própria `feat/<nome>/<topico>`.
3. Ambiente dual: Windows é host; Blender/CUDA/IA rodam no WSL — agente no Windows prefixa com `wsl`, agente dentro do WSL roda direto (tabela em `README.md`). Caminhos `C:\foo` → `/mnt/c/foo`. Sem username hardcoded em comando (use `tools/setup/py.sh`).

## Próximo gatilho

1. Dono revisa e mergeia `feat/onboarding-multi-maquina` na main.
2. Colega: Fase A **concluída e auditada** (2026-11-15, `evidence/rtx5060ti-8gb/environment-audit-fase-a.md`) — base da máquina pronta (WSL2 + Ubuntu 26.04.1, RTX 5060 Ti visível no WSL, python3.11.18, git configurado).
3. Após merge: colega roda Fase B (`PROMPT-ONBOARDING-B.md`) → Blender + venv torch cu128 + TripoSR + benchmark local → dono troca os "A VALIDAR (Fase B)" restantes no `rtx5060ti-8gb.md`.
4. Dono vota na galeria → ADR-005 fecha a Fase 1.
