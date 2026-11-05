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

### Peça Vitrine — "Jubarte nas Ondas" (2026-11-04) — `[!]` REPROVADA PELO DONO — encerrada a rodada

- **VEREDITO (2026-11-04): Ficha A REPROVADA** — "não dá pra entender nada" (baleia irreconhecível). Registrado em `~/printer3d-work/jubarte/reviews.json` + `evidence/jubarte/`. Sem iteração adicional na sessão (regra).
- **Diagnóstico honesto**: o elo fraco foi a **seleção de input sem visão** — heurísticas (fundo/centralização/cobertura) não medem "parece baleia". Entrada ambígua do SD1.4 → malha ambígua do TRELLIS. Pipeline técnico funcionou de ponta a ponta (SD→TRELLIS→Forja→review), o conceito não sobreviveu.
- **Licores aproveitáveis**: SD venv próprio + workaround do HF gated/xet; campo espessura da Forja validado em caso real (6,18mm@200mm); fluxo review com parada para veredito funciona.
- **Próxima rodada (propostas, a decidir com o dono)**: (1) dono escolhe a imagem de entrada com olho antes de queimar GPU; (2) sketch Blender procedural como guia img2img; (3) dividir conceito (baleia e anel separados, unidos na Forja).
- Fatos da rodada: SD 4/4 gerados (v1-4; 2.1 gated no HF) · TRELLIS 1/2 com malha (cand_42 OOM) · Forja @200mm watertight/espessura ok · commits `1a2e25f`..`d8886f3`.

- **[x] SD setup**: venv novo `printer3d-sd` (torch 2.5.1+cu121, diffusers 0.31). **SD 2.1 está gated no HF** (401 anônimo; todos os repos stabilityai) → fallback `CompVis/stable-diffusion-v1-4` público (CreativeML OpenRAIL-M). Workarounds: token HF inválido desativado + `HF_HUB_DISABLE_XET=1` (backend xet com I/O error).
- **[x] 4 candidatos** gerados (seeds 11/23/42/77, 512px, ~4,5s cada, VRAM alloc pico 2.679 MiB, processo encerrado → VRAM liberada) — `~/printer3d-work/jubarte/sd/` + `sd_report.json`. **Seleção objetiva (sem olho)**: bg_std + descentramento + cobertura + componentes → **cand_42 (nota 44,3) e cand_77 (39,4)**; ranking completo em `evidence/jubarte/selecao.json`. Sidecars de procedência ADR-003 para todos.
- **[x] Forja — campo novo `espessura`** (raycast −normal, 300 amostras, pct5+mín em mm; aviso automático < 2,4mm com sugestão de Solidify NÃO implementado — próximo passo registrado). Validado: caneca@200mm pct5=2,673mm; testes sintéticos continuam 3/3.
- **[x] TRELLIS ×2 (orçamento 2/2 usado)**: cand_77 → **malha OK** (161.912v, 59s, VRAM 11.646 MiB); cand_42 → **OOM no decode** (82s, 11.902 MiB — caso denso; mesmo padrão do benchmark). Sem retry conforme regra. `experimento.json` em `evidence/jubarte/`.
- **[x] Forja cand_77 @200mm**: watertight ✅ winding ✅ 142×52×200mm · 184.868 tris · **espessura pct5 6,177mm / mín 2,506mm (acima do limiar 2,4)** · 2 componentes lixo descartados · volume ~391 cm³.
- **[x] Review**: fichas em `http://localhost:8765/review/` (entrada + 3 ângulos + métricas + ficha de falha do cand_42). Servidor: `~/printer3d-work/dashboard/` na porta 8765.
- **[!] FLUXO PARADO**: aguardando veredito do dono em `~/printer3d-work/jubarte/reviews.json` (`"aprovado": true/false` na ficha A_cand_77). **Sem veredito, sem STL final** (regra da sessão).
- Próximos passos pós-veredito: STL final 200mm do vencedor + `impressao_jubarte.md` (camada 0,2mm, suportes tree na cauda/barbatanas, anel tocando a mesa, PLA prata/branco seda/mármore, tempo estimado).

### Fase 1 — Forja (módulo de reparo/printabilidade, 2026-11-04) — `[x]` CONCLUÍDA

- **Pacote** `tools/forja/forja/` (mirror do workspace `~/printer3d-work/forja/`): `cli.py` (`python -m forja repair|batch`), `pipeline.py` (8 etapas com métricas antes/depois), `report.py`, `render.py` (antes/depois 512px CPU, câmera do benchmark), `blender_mod.py` (voxel remesh/decimate headless), `tests/`.
- **Pipeline**: limpeza (duplicados/degenerados/componentes; `--keep-all-components`, `--min-component-tris`) → normais (`fix_normals`) → PyMeshFix (watertight) → `--smooth N` (opc.) → `--voxel` (opc., Blender) → `--max-tris` (opc., Blender) → `--target-height mm` (escala pela maior dimensão; sem o parâmetro reporta unitário) → STL binário + `forja_report.json`.
- **Testes sintéticos 3/3 PASS** (esfera c/ furo→watertight; cubo c/ face invertida→winding ok+volume+; 2 componentes→mantém maior).
- **Lote 7/7 TRELLIS PASS** no gate (`wt ∧ is_volume ∧ winding ∧ maxdim=100mm`): `evidence/fase1-forja/gate_final.txt` + `forja_index.json`. Renders antes/depois: 14/14 em `~/printer3d-work/forja_out/<caso>/`.
- **Decisões**: (1) `--target-height` escala pela MAIOR dimensão da bbox (malhas de gerador não têm orientação canônica — documentado no report); (2) autointerseção: proxy de faces duplicadas + **limitação conhecida** (checagem completa fora do escopo, conforme spec/timebox); (3) decimação/remesh via Blender headless (CPU, não toca VRAM — usuário jogando em paralelo).
- **Bug corrigido no caminho**: glob default do batch era `*/trellis/*.obj` (pegava `mesh_reparada.obj` junto → 14 itens duplicados) → agora `*/trellis/mesh.obj`.
- APIs: trimesh 5.2 (sem `unique_vertices_mask`) e pymeshfix novo (`.points`/`.faces`).

### Comparativo extra a pedido do dono (2026-11-04, escultura complexa)

- Escultura procedural Blender (pedestal+coluna+nó tófita+esfera+anel, bronze) → mesma input nos 2 modos.
- TRELLIS: seed 42 → **OOM** (12.039 MiB); seed 7 → OK (221k verts, 68s, 11.915 MiB). TripoSR: OK de primeira (47k verts, 48s, 3.567 MiB).
- Comparação interativa web (three.js, GLB, laranja=TRELLIS/azul=TripoSR): `~/printer3d-work/sculpture/viewer/` + `python -m http.server 8765`.
- Reforça o padrão: TRELLIS no limite de VRAM em entradas densas; votação do dono (ADR-005) ainda pendente.

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
