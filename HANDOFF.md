# HANDOFF.md — Retomada por qualquer agente

> Leia isto DEPOIS de `PROGRESS.md` (fonte da verdade) e ANTES de executar qualquer coisa. Contexto mínimo para um agente frio continuar o projeto sem conversa anterior.

## Estado atual (2026-11-17)

- **Benchmark TripoSF (C5) PRONTO — aguardando veredito visual do dono.** TripoSF = VAE de malhas (NÃO imagem→3D); comparativo anubis feito como TripoSG-bruto × TripoSG→TripoSF (256/512), guard 10 GB respeitado (picos 5,6–7,5 GB; 1024³ BLOQUEADO, 10.057–11.615 MiB). Gate: `evidence/rtx3060-12gb/triposf-benchmark/gallery_render/comparativo/` (+ `notes.md` com métricas/defeitos). Infra: venv `~/venvs/triposf`, clone `~/tools/TripoSF`, pesos HF oficiais em `~/tools/TripoSF/ckpts/`, runner com guard+poller em `~/printer3d-work/triposf-bench/triposf_bench.py`. Redução `sample_points_num` 819.200→409.600 (knob oficial) é OBRIGATÓRIA para caber no guard — gargalo medido no LocalPoolPointnet fp32.
- **Viewer 3D web NO AR e verificado**: https://brunointegrations.com/modelos3d/ — site em `tools/modelos3d-site/` + `deploy.sh` (mesmo padrão printflow3d: rsync + container `modelos3d` nginx estático + location `/modelos3d/` no trivestia-nginx). 12 casos (10 C3 + anubis_a/b). **Pendência conhecida**: GLBs `*__trellis2` com winding inconsistente → visual quebrado no viewer; fix testado pela metade (`trimesh.repair.fix_winding`+`fix_normals` antes do export GLB — detalhes no registro C3 do PROGRESS.md). GLBs fonte: `~/printer3d-work/modelos3d-site/models/`; meshes: `~/printer3d-work/c3-bench/<caso>/<modo>/mesh_reparada.obj` e `~/printer3d-work/anubis/out/<mode>_<var>/`.
- **C3 técnico CONCLUÍDO na 3060 — aguardando veredito visual do dono → ADR-007.** Resultados: trellis2 10/10 OK (mediana 156s, VRAM máx 5,4GB — rodar SEMPRE 512³ single-stage; 1024_cascade OOM), triposr 10/10 OK (45,5s), trellis 1/10 (9 OOM — entradas densas), triposg 7/10 (dono pulou 3 casos). Evidência completa em `evidence/fase-c/comparativo-3060/` (`gallery.md` = portão do dono, `scores.md`, `results.json`, `gallery_render/` 58 PNGs). Malhas brutas em `~/printer3d-work/c3-bench/<caso>/<modo>/mesh.obj`. Se o dono quiser gerar personagem TRELLIS.2 avulso: `run_comparativo_c3.py gerar trellis2` já cobre os 10 casos; smoke avulso = `trellis2_runner.py --image <png> --output-dir <dir> --res 512`.
- **Infra C3 completa e validada** (venvs trellis2/triposg, extensões CUDA com gcc-14 + patch glibc 2.42, pesos com mirrors documentados, plugins + runners + orquestrador `tools/generator/run_comparativo_c3.py`). Armadilhas e comandos prontos: `evidence/fase-c/comparativo-3060/install-notes.md`. TRELLIS.2 só roda em **512³** nesta GPU (1024_cascade OOM); autograd desligado é obrigatório.
- **Fase 1 ENCERRADA com veredito NEGATIVO do dono (2026-11-16)**: ele recusou a votação por caso e reprovou globalmente os dois geradores nas duas máquinas ("ficou tudo ruim" / TripoSR reprovado sem ressalvas). **ADR-005** registra: **nenhum default mode, nenhum gerador em uso produtivo**. Benchmark técnico permanece válido como referência (`evidence/benchmark/` + `evidence/rtx5060ti-8gb/benchmark/`).
- **Fase C ABERTA (2026-11-16)** — nova geração de geradores + qualidade de entrada (roadmap §Fase C; entra antes da Fase 2 por decisão do dono). C2 concluído: `tools/generator/preprocess_input.py` + testset pré-processado em `~/printer3d-work/testset_preproc/` (evidência `evidence/fase-c/preproc/`). Próximo: **veredito do dono na galeria C3 → ADR-007** e **C1 na máquina do colega** (TRELLIS.2 fork na 5060 Ti — PROMPT-08). Achado honesto registrado: caso `trex_figurine` é o pergolado `T.png` da Microsoft (mal nomeado desde a Fase 1; testset imutável, comparabilidade preservada).
- Onboarding multi-máquina NA MAIN (merge 2026-11-16): perfis de máquina, guard paramétrico, `tools/setup/`, `docs/onboarding/`, ADR-006. 2º contribuidor (RTX 5060 Ti 8GB, Blackwell sm_120): Fase A e Fase B concluídas e integradas (PR #1) — benchmark TripoSR medido: 10/10 OK, mediana 14,4s, pico 4385 MiB; TRELLIS inviável confirmada por execução (10/10 sem mesh).
- **Fase 1 infra entregue e validada** (reaproveitável): venv por máquina (`~/.venvs/printer3d-ia`), TRELLIS em `~/tools/TRELLIS` (3060), TripoSR em `~/tools/TripoSR` (ambas), plugins + `gpu_guard.py` paramétrico em `tools/generator/`, benchmark automático.
- **Fase 1 Forja entregue** (`tools/forja/forja/`; workspace `~/printer3d-work/forja/`): 7/7 TRELLIS reparados, gate PASS em `evidence/fase1-forja/gate_final.txt`. **Forja é CPU-only** — pode rodar com o dono jogando. APIs novas: trimesh 5.2, pymeshfix `.points/.faces`.
- Repo: `git@github.com:brunomrtns/3dprinter-setup-ia.git` · branch `main` · tudo pushed.

## Decisões que você não deve reabrir sem motivo forte

- Multi-modo com pipeline comum e plugins de gerador (ADR-001)
- Headless/CLI primeiro; UI só com dor real (ADR-002)
- Local-first + sidecar de procedência obrigatório em TODO asset (ADR-003)
- venv isolado `printer3d-ia`; `game-ai3d` é intocável/referência (ADR-004)
- Multi-máquina: caminhos portáveis, perfis por máquina, guard paramétrico, evidências namespaced (ADR-006)
- **Sem default mode para gerador image→3D** (ADR-005): dono reprovou TRELLIS e TripoSR globalmente (benchmark + 3 reprovações visuais na Jubarte). NÃO reinstalar, NÃO reavaliar os mesmos pesos sem ordem do dono e NÃO propor "mais uma tentativa" sem caminho novo de qualidade.
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

1. ~~Dono revisa e mergeia `feat/onboarding-multi-maquina` na main~~ — feito (2026-11-16).
2. ~~Colega: Fase A~~ — concluída e auditada (2026-11-15). ~~Fase B (PR #1)~~ — revisada, corrigida e **mergeada na main (2026-11-16)**: Blender 5.0.1, torch 2.11.0+cu128 (capability (12,0) ✓), TripoSR benchmarkado — 10/10 OK, mediana 14,4s, VRAM pico 4385 MiB < guard 6500. Perfil `rtx5060ti-8gb.md` sem nenhum "A VALIDAR" restante.
3. ~~Votação do dono → ADR-005~~ — **fechada (2026-11-16)**: dono recusou votação por caso e **reprovou globalmente** os dois geradores → ADR-005 = "sem default mode", Gerador de Peças parado até decisão do dono (ADR-005 §4).
