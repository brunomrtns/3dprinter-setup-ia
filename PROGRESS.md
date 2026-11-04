# PROGRESS.md — 3dprinter-setup-ia

> **Fonte da verdade do estado do projeto.** Toda sessão começa aqui e termina atualizando este arquivo (AGENTS.md §1.2 e §3).
> Legenda: `[x]` concluído · `[~]` em andamento · `[ ]` pendente · `[!]` bloqueado/pendência

---

## Fase 0 — Fundação e Documentação

**Status:** `[~]` concluída tecnicamente — **aguardando aprovação do dono (👍)** para abrir a Fase 1.

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
| 12 | Aprovação do dono | [ ] |

### Registros da sessão fundadora (2026-11-03)

- Remote: `git@github.com:brunomrtns/3dprinter-setup-ia.git` (SSH OK — "Hi brunomrtns!")
- Identidade git estava ausente em todos os escopos → configurada: `Bruno Martins / brunomartinsss@gmail.com`, `init.defaultBranch=main`
- **Nada foi instalado e nenhum código de pipeline foi escrito** (respeitado o escopo da Fase 0)
- Histórico: 9 commits convencionais, todos pushed (init → README → AGENTS → architecture → roadmap → knowledge → ADRs → skeleton → audit → PROGRESS/HANDOFF)

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
