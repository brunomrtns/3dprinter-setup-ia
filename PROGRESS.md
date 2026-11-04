# PROGRESS.md — 3dprinter-setup-ia

> **Fonte da verdade do estado do projeto.** Toda sessão começa aqui e termina atualizando este arquivo (AGENTS.md §1.2 e §3).
> Legenda: `[x]` concluído · `[~]` em andamento · `[ ]` pendente · `[!]` bloqueado/pendência

---

## Fase 0 — Fundação e Documentação

**Status:** `[x]` concluída e **aprovada pelo dono (👍 em 2026-11-04)**.

| # | Tarefa | Status |
|---|---|---|
| 1 | Init: clone, `.gitignore`, identidade git (faltava — configurada), push inicial | [x] |
| 2 | `README.md` (visão, stack, estrutura, comandos canônicos, badge de fase) | [x] |
| 3 | `AGENTS.md` (contrato vinculante, agnóstico a agente) | [x] |
| 4 | `docs/architecture.md` (3 módulos + pipeline comum, contratos, fila serial, guard de VRAM, integração PrintFlow3D) | [x] |
| 5 | `docs/roadmap.md` (fases com critérios de aceite objetivos) | [x] |
| 6 | `docs/knowledge/` — 5 guias (stl-e-malhas, impressao-resina, blender-headless, wsl-gpu, licencas-e-procedencia) | [x] |
| 7 | `docs/operations/environment-audit.md` com **outputs reais** | [x] |
| 8 | `docs/decisions/` — ADR-001..004 | [x] |
| 9 | Skeleton `tools/{forja,generator,pose,validation}` + `evidence/` (sem código) | [x] |
| 10 | `PROGRESS.md` + `HANDOFF.md` refletindo estado real | [x] |
| 11 | Todos os commits pushed (`git log origin/main..HEAD` vazio) | [x] |
| 12 | Aprovação do dono | [x] 👍 2026-11-04 |

---

## Fase 1 — Gerador de Peças: venv isolado + TRELLIS + benchmark `[~] EM ANDAMENTO (aberta 2026-11-04)`

| # | Tarefa | Status |
|---|---|---|
| 0 | Abertura formal da fase (roadmap + PROGRESS + commit + push) | [x] |
| 1 | venv `printer3d-ia` (Python 3.11) + torch CUDA + deps base + evidência de isolamento do `game-ai3d` | [x] |
| 2 | Instalação TRELLIS (`docs/operations/trellis-install.md` passo a passo; geração ponta a ponta na 3060) | [x] |
| 3 | TripoSR com venv novo (clone próprio `~/tools/TripoSR`) + geração ponta a ponta (run 1.1s, VRAM 4.2GB) | [x] |
| 4 | Interface de plugin comum + `gpu_guard.py` (threshold 10.000 MiB, fila serial, poller 1Hz) + smoke test ponta a ponta | [x] |
| 5 | Set de testes 10 casos fixos com `manifest.json` (procedência por imagem) | [x] |
| 6 | Benchmark automático 10×2 + `results.json` + `scores.md` + galeria (mesmo ângulo/luz) | [x] `evidence/benchmark/` |
| 7 | Fechamento: PROGRESS/HANDOFF + relatório ao dono + votação do default mode (→ ADR-005) | [~] aguardando votação do dono |


### Registros da sessão fundadora (2026-11-03)

- Remote: `git@github.com:brunomrtns/3dprinter-setup-ia.git` (SSH OK — "Hi brunomrtns!")
- Identidade git estava ausente em todos os escopos → configurada: `Bruno Martins / brunomartinsss@gmail.com`, `init.defaultBranch=main`
- **Nada foi instalado e nenhum código de pipeline foi escrito** (respeitado o escopo da Fase 0)
- Histórico: 9 commits convencionais, todos pushed (init → README → AGENTS → architecture → roadmap → knowledge → ADRs → skeleton → audit → PROGRESS/HANDOFF)

### Registro da sessão Fase 1 (2026-11-04, benchmark parcial)

- Commits: `5e31265` venv · `d238c72` TRELLIS · `2ef118a` TripoSR · `b4cd489` plugins+guard (smoke aprovado: 73.5s, VRAM pico 11.405 MiB, 304k verts) · `7cce4a3` testset 10 casos (7 MIT TRELLIS + 3 procedurais CC0 Blender).
- `run_benchmark.py` (estágios resumíveis: trellis|triposr|render|publish): **trellis 7/10 OK** — tempos 57-74s/caso, VRAM pico 11,7-11,9 GB, manifold True em pirâmide/caneca/engrenagem/gancho, False no resto (fill_holes não fecha buracos FlexiCubes — reparo pesado é Fase 2 Forja).
- **[!] 3 OOM reais** (estrutura_castelo, prop_caixote, robo_caranguejo — casos densos estouram ~11,9 GB úteis no decode FlexiCubes). Mitigação aplicada no runner (`garbage_collection_threshold:0.8,max_split_size_mb:256`) — **retry pendente, aguardando GPU livre** (dono usando a máquina pra jogar; guard espera VRAM, sem conflito).
- TripoSR (10 casos), render de galeria (40 previews, CPU) e publish (`evidence/benchmark/`) pendentes.
- Demo visual para o dono: 3 renders + 1 OBJ em `C:\Users\Bruno\AppData\Local\Temp\opencode\demo\`; malhas em `~/printer3d-work/benchmark/<caso>/trellis/mesh.obj` (WSL).
- Comando de retomada: `wsl bash ~/printer3d-work/retry_trellis.sh` → `wsl bash ~/printer3d-work/run_bench.sh triposr` → `... render` → `... publish` (nesta ordem).

### Resultado final do benchmark (2026-11-04T12:32, `evidence/benchmark/scores.md`)

| modo | tempo mediana | VRAM pico | vértices médios | manifold pós-reparo | erros |
|---|---|---|---|---|---|
| trellis | 65,7s | 12.070 MiB | 257.777 | 4/10 | **3/10 (OOM confirmado 2× — casos densos)** |
| triposr | 27,3s | 3.588 MiB | 74.032 | 9/10 | 0/10 |

- **Dado inesperado e relevante**: espessura pct5 do TRELLIS é baixíssima (0,002-0,008 em malha unitária — casca fina, frágil pra impressão) vs TripoSR (0,016-0,176). TRELLIS gera 3,5× mais detalhe (vértices), mas casca fina; TripoSR gera sólidos mais "imprimíveis".
- Galeria (34 renders, câmera/luz idênticas): `evidence/benchmark/gallery.md` — **aguardando votação 👍/👎 do dono por caso** → ADR-005.

## Pendências herdadas do audit (nenhuma bloqueia a Fase 1 — detalhes em `docs/operations/environment-audit.md`)

- [~] **#1** venv da Fase 1 deve usar `/usr/bin/python3.11` (default do WSL é 3.14.4 — muito novo para stack CUDA)
- [~] **#2** requisito de VRAM do TRELLIS será medido no benchmark (não confiar em números de terceiros)
- [ ] **#3** aviso de VRAM insuficiente é log apenas; toast do Windows fica para quando doer

## Próximos passos — Fase 1 (Gerador de Peças: venv + TRELLIS + benchmark)

1. **Gatilho:** aprovação 👍 do dono sobre a Fase 0 (este arquivo + audit).
2. Criar `/home/bruno/.venvs/printer3d-ia` com Python 3.11 (ADR-004 — NÃO tocar no `game-ai3d`).
3. Instalar TRELLIS no WSL (pesos ~13 GB no filesystem nativo — 866 GB livres verificados).
4. Interface de plugin comum + plugins TRELLIS e TripoSR.
5. Benchmark 10 casos fixos × 2 modos, scoring objetivo automatizado (manifold, espessura, tempo, VRAM pico, vértices), galeria de previews.
6. Dono avalia 👍/👎 por caso → ADR-005 registra o default mode.

Escopo completo e critérios de aceite: `docs/roadmap.md` §Fase 1.
