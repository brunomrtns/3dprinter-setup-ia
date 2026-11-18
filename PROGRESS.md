# PROGRESS.md — 3dprinter-setup-ia

> **Fonte da verdade do estado do projeto.** Toda sessão começa aqui e termina atualizando este arquivo (AGENTS.md §1.2 e §3).
> Legenda: `[x]` concluído · `[~]` em andamento · `[ ]` pendente · `[!]` bloqueado/pendência

---

## Estado por fase (resumo rápido)

| Fase | Estado |
|---|---|
| 0 — Fundação | `[x]` aprovada pelo dono (2026-11-04) |
| 1 — Gerador de Peças (venv + TRELLIS/TripoSR + benchmark) | `[x]` encerrada 2026-11-16 com **veredito NEGATIVO do dono** — sem default mode (ADR-005); infra validada e reaproveitável |
| **C — Nova geração de geradores + qualidade de entrada** | `[~]` **EM ANDAMENTO (aberta 2026-11-16)** — C2 concluído; C1 na máquina do colega; C3 na 3060 |
| 2 — Forja (parcial: pacote entregue na Fase 1) | `[~]` pipeline/reparo funcionais; catálogo completo é Fase 2 propriamente dita — depois da Fase C |
| 3 — Pose / 4 — Operador IA | `[ ]` não abertas |

**Gatilho atual:** C1 na máquina do colega (TRELLIS.2 fork na 5060 Ti) + C3 no PC do Bruno (comparativo 4 geradores na entrada pré-processada).

---

## Fase C — Nova geração de geradores + qualidade de entrada `[~] EM ANDAMENTO (aberta 2026-11-16)`

> Contexto: ADR-005 encerrou a Fase 1 sem gerador eleito. O dono decidiu abrir a Fase C: geradores de nova geração + ataque ao elo mais fraco medido (qualidade da entrada). Detalhes no roadmap §Fase C. Entra ANTES da Fase 2 por decisão do dono.

| # | Tarefa | Status |
|---|---|---|
| C2 | `tools/generator/preprocess_input.py` (fundo removido via rembg, pad quadrado sem corte, 1024px, sidecar ADR-003, upscale opcional OFF) + 10 casos do testset → `~/printer3d-work/testset_preproc/` + evidência `evidence/fase-c/preproc/` | [x] 10/10 OK |
| C1 | TRELLIS.2 (fork IgorAherne, VRAM reduzida) na máquina `rtx5060ti-8gb` — tarefa do colega | [ ] aguardando |
| C3 | Comparativo formal na 3060: TRELLIS.2 + TripoSG + TRELLIS 1 + TripoSR na mesma entrada pré-processada, galeria lado a lado | `[~]` **GERAÇÃO+EVIDÊNCIA PUBLICADAS** — trellis2 10/10 OK, triposr 10/10, trellis 1/10 (9 OOM), triposg 7/10 (3 casos pulados por decisão do dono); gallery.md + scores.md + results.json em `evidence/fase-c/comparativo-3060/` — **aguarda veredito visual do dono → ADR-007** |
| C4 | Fila de jobs entre máquinas | [ ] FUTURO (fora da fase) |
| C6 | **Hunyuan3D-2.1 multi-vista + fotogrametria (VGGT) no carro fox** — handoff pronto em `docs/onboarding/PROMPT-C6-hunyuan-multivista.md` (dono pediu outra IA pra executar; créditos) | `[ ]` **prompt pronto — aguardando execução** |
| C5 | Benchmark TripoSF na 3060 (ordem direta do dono, 2026-11-17): caso anubis apenas, TripoSG × TripoSF | `[x]` **CONCLUÍDO COM VEREDITO DO DONO (2026-11-17)**: *"o triposf512 ganhou, melhor até agora"* — gate visual feito no viewer (modelos3d) com `triposg` × `triposf512`; 4/4 runs OK (256/512 × vistas a/b), picos 5,6–7,5 GB, guard 10 GB intacto; 1024³ **BLOQUEADO pelo guard**; evidência em `evidence/rtx3060-12gb/triposf-benchmark/`. **Pendência de decisão do dono**: promover o pipeline gerador→TripoSF512 como etapa oficial (exige Forja antes de imprimir — 512 não é watertight) |

### Registro C5 (2026-11-17 — TripoSF × TripoSG, caso anubis)

- **Achado crítico de escopo**: TripoSF oficial (`~/tools/TripoSF`) é **VAE de malhas 3D** (entrada `--mesh-path`, point cloud) — NÃO existe modo imagem→3D no repo. Comparativo feito pela linhagem da imagem do teste TripoSG: `anubis_{a,b}_preproc.png` → TripoSG (evidência existente, intocada) → malha bruta → TripoSF 256/512. Detalhe e limitações em `evidence/rtx3060-12gb/triposf-benchmark/notes.md` §0.
- **Ambiente**: venv dedicado `~/venvs/triposf` (py3.11.16, torch 2.8.0+cu128, xformers 0.0.32.post2 no lugar de flash-attn via backend nativo do código, spconv-cu120, open3d 0.18, numpy 1.26.4 — desvios documentados; `pip check` OK). Pesos HF oficial `VAST-AI/TripoSF` (sha256 em notes.md §1).
- **Guard 10.000 MiB (pico, nvidia-smi 1Hz)**: exemplo oficial jacket.obj com config oficial BLOQUEADO (pico 11.615 MiB — README pede ≥12 GB p/ 1024³; sonda por fases localizou o gargalo no `LocalPoolPointnet` fp32 com 819.200 pts, independe da resolução de saída). Remédio pelo knob oficial do README (`sample_points_num: 409.600`): exemplo OK a 256 (7.962) e 512 (8.328); 1024 segue BLOQUEADO (10.057).
- **Benchmark anubis 4/4 OK**: 256 → pico 5,6/5,7 GB, ~24s, ~157k faces, watertight ✅ (8–18 componentes-ilha); 512 → pico 7,2/7,5 GB, ~29s, ~616–631k faces, **não-watertight** (+winding inconsistente no a_512). Referência TripoSG: 55,9s/vista, 537/549k faces, watertight, 1 componente.
- **Renders canônicos + comparativos lado a lado** (câmera/luz do C3): `gallery_render/comparativo/gate_anubis_{a,b}_{a,b}.png` — **gate humano do dono pendente** (a IA não decide o vencedor).

### Registro C5 — pós-veredito (2026-11-17, tarde)

- **Veredito do dono no gate (viewer modelos3d)**: *"o triposf512 ganhou, melhor até agora"*. Decisão visual do dono, registrada sem maquiagem — nota: o trellis2 não pôde ser avaliado visualmente (bug do viewer, abaixo).
- **PIPELINE OFICIAL DECIDIDO PELO DONO**: `imagem → preproc C2 → TripoSG → refino TripoSF 512`. Ferramenta one-command: `tools/generator/pipeline_imagem3d.sh <imagem> <dir> [seed]` + runner versionado `tools/generator/triposf/{triposf_runner.py,TripoSFVAE_o512.yaml,TripoSFVAE_o256.yaml}` (venv `~/venvs/triposf`; TRIPOSF_PY/TRIPOSF_HOME sobrescrevem — ADR-006). **Smoke ponta-a-ponta OK** (anubis_a.jpg: TripoSG 536.792 faces [reproduziu a evidência, seed 42] → TripoSF 616.348 faces, pico 7.523 MiB, guard ok, ~100s totais; saída em `~/printer3d-work/pipeline-smoke/anubis_a/`). Para imprimir: Forja antes (512 não é watertight).
- **Viewer — 3 melhorias do dono**: (1) pausa de giro: **arrastar a peça PARA o giro automático** + botão `⏸/▶` claro; (2) **link compartilhável** — URL reflete o estado (`?case=anubis_a&mode=triposf512&vs=1&mode2=triposg&auto=0`) + botão `🔗 Copiar link`; (3) **DoubleSide** no material (abaixo).
- **Trellis2 "picotado" — mitigado, NÃO curado**: receita `fix_winding+fix_normals` testada e **falhou honestamente** (winding False→False — malha FlexiCubes aberta/non-manifold; reparo pesado segue sendo da Forja). Mitigação aplicada no viewer: material `side: DoubleSide` → elimina o efeito transparente por faces invertidas em TODOS os modelos. Furos reais de geometria do 512³ sparse permanecem visíveis. **Avaliação visual do trellis2 pelo dono segue pendente** — a escolha "TripoSG > trellis2" do dono foi feita sem ver o trellis2 direito.

### Registro viewer mobile-friendly (2026-11-17, noite) — `[x]` CONCLUÍDO (v3)

- **Motivo**: dono compartilhou o link com um amigo; v0/v1 reprovadas por poluição sobre o modelo; v2 deployada mas com defeito grave descoberto por inspeção real com screenshot em 390×844.
- **Diagnóstico real da v2 (causa raiz)**: (1) `#stage` não tinha `display: grid` no modo single e `.vp` não tinha `height: 100%` → canvas colapsava para **`390×195` (23,1% da tela)** com 73% de vazio preto e modelo cortado; (2) câmera hardcoded `(1.6, 1.2, 1.6)` / `target (0, 0.8, 0)` ignorava bounding box e aspect ratio (cortava orelhas/pés e laterais de modelos largos no portrait); (3) header extra roubava altura, VS espremia 3 selects sem identificar painel A/B, `btnVs` não acendia em `?vs=1`, `rebuildViewports()` vazava `requestAnimationFrame`, chip ativo no desktop ficava ilegível, e nginx tinha `expires 1h` travando HTML/JS velho no celular.
- **Fix v3 em `tools/modelos3d-site/`** (`index.html`, `app.js`, `deploy.sh`):
  - **Canvas full-stage**: `height: 100dvh`, `#stage` grid `1fr` + `.vp` `100%` → canvas mobile sobe de **195px → 728px (86,3% da tela)**, zero overlay sobre o modelo;
  - **Enquadramento automático (`fitCamera`)**: calcula distância via cilindro de rotação em Y + `vFov`/`hFov` do aspect real (portrait/landscape/VS), garantindo 100% do modelo inteiro durante o giro 360° e no reset (`⟲`);
  - **UI mobile limpa (≤640px)**: header oculto, barra superior única de 1 linha (`Caso` + `Gerador` no single; `Caso` + `⇄` no VS), alvos táteis `44px` em `pointer: coarse`, safe-area insets; detalhes técnicos (faces, verts, tempo, VRAM, manifold) sob demanda em `<dialog id="infoDialog" closedby="any">` (com fallback light-dismiss p/ Safari);
  - **Decisão VS mobile**: **empilhado vertical (`1fr / 1fr`)** com mini-barra dedicada fora do canvas por painel (`A [select]` / `B [select]`) + **câmera sincronizada** ao girar/pinçar + botão `⇄`; desktop (≥641px) mantém chips originais com contraste de `.chip.on` corrigido;
  - **Limpeza & cache**: `disposeViewport()` cancela rAF/ResizeObserver/renderer; `btnVs` sincronizado no boot; toast no copiar link (`🔗`); `deploy.sh` trocado de `expires 1h` para `Cache-Control: no-cache` + `./app.js?v=3`.
- **Deploy**: `tools/modelos3d-site/deploy.sh` — rsync OK, `nginx -t` OK, reload sem downtime, smoke 200, `Cache-Control: no-cache` confirmado.
- **Validação real (Chrome headless via CDP, `390×844` @ 2x na URL pública + `320×568` e `1280×800` local)**: `0` erros console, `errbox` vazio, `spin` oculto, `0` overflow; `anubis_a` passou de **28.238 px (19,7% h)** na v2 para **234.791 px (65,0% h / 67,2% w — 8,3×)** na v3; `trex_figurine` inteiro (71,0% w); VS empilhado com ambos os modelos inteiros. Evidência: `evidence/fase-c/viewer-mobile-v3/validacao.md`.
- **Update pós-processamento Anubis no viewer (2026-11-18)**: adicionados 3 modos em `anubis_a` (`posproc` sólido 200k watertight/Taubin 5it, `posproc_oco` parede 3mm + dreno 4,5mm via `manifold3d`, `posproc_corte` corte transversal do oco), `computeVertexNormals()` de fallback no `app.js` (GLBs sem `NORMAL` ficavam pretos) e `flatShading` automático no `trellis2` (elimina granulado das normais corrompidas por winding invertido). Deployado via `deploy.sh` (40 GLBs) e validado ao vivo em `390×844`.

### Registro — carro fox do dono (2026-11-18, avulso) `[!]` VEREDITO PARCIAL: ainda não prestam — handoff C6 pronto

- **VEREDITO DO DONO (2026-11-18, depois de ver o viewer)**: o carro **ainda não ficou bom** ("frente fica bom atras fica ruim, atras fica bom frente fica ruim"); o anubis tinha ficado aceitável/imprimível, o carro não. **Dado novo e importante: no carro, trellis2 ficou MELHOR que triposg** (inverte o gate C5). Diagnóstico aceito: single-view adivinha o lado invisível → dono quer multi-vista local ("tenho recurso").
- **Decisão do dono**: testar **Hunyuan3D-2.1 multi-vista** (shape-only = 10GB VRAM, cabe; bate TripoSG/TRELLIS nos benchmarks da Tencent) **+ preparar fotogrametria VGGT** — handoff completo com comandos em `docs/onboarding/PROMPT-C6-hunyuan-multivista.md` pra OUTRA IA executar (créditos do dono acabando).
- **Pedido original**: carro com máx. fidelidade ("força total": triposg, triposf, pós-processamento) a partir de 3 imagens do dono (`Downloads/fox/{front,back,all}.webp` — `all` = 3 vistas numa imagem só).
- **Geração 9/9 OK** (GPU serial, guard OK): pipeline oficial (`preproc → TripoSG → TripoSF512`) nas 3 vistas + trellis2 512³ nas 3 vistas. Telemetria: front 80s/75s(vram 9.035)/42s · back 82s/66s(8.727)/44s · all 68s/38s(6.103)/30s. Malhas em `~/printer3d-work/carro/<vista>/{1_triposg,2_triposf512,trellis2}/`.
- **Viewer**: 9 GLBs (decimados ~600k faces p/ peso) + manifest → deployado e validado ao vivo (200): `https://brunointegrations.com/modelos3d/` — casos `carro_front`/`carro_back`/`carro_all` × modos `trellis2`/`triposg`/`triposf512` (VS disponível).
- **Pós-processamento PAUSADO por decisão do dono** ("não insistir antes de ver"): script versionado `tools/generator/posproc_impressao.py` (receita anubis: fragmentos→pymeshfix→manifold→200mm→Taubin→200k→oco 3mm+dreno 4,5→corte). Status real: reparo watertight FUNCIONOU (`01_reparado.obj` front/back gerados); Taubin/decimação falhavam por `libOpenGL` ausente — **corrigido** (`apt libopengl0`); dono escolhe o vencedor visual e o posproc termina em minutos.
- **Vistas separadas do all.webp**: `~/printer3d-work/carro/vistas/{v1_esq,v2_meio,v3_dir}.png` (terços recortados às cegas — confirmar com o dono qual é frente/lado/trás antes de usar no multi-vista).
- Nota técnica: a malha do carro (2,9M faces) veio "non-manifold" de verdade — o roundtrip manifold3d direto falha; o caminho correto é pymeshfix antes (já no script).

### Registro C3 (2026-11-17, continuação — benchmark em execução)

- **Smoke TRELLIS.2 RESOLVIDO** (7 bugs reais, todos documentados em `install-notes.md` §Atualização): BiRefNet_config/handler baixados do HF oficial; `pipeline.cuda()` adicionado; patch `needs_grad` no flex_gemm (fork desatualizado vs FlexGEMM upstream); **causa raiz do OOM = autograd ligado** (`torch.set_grad_enabled(False)` — oficial roda sob `@torch.no_grad()`); setup low_vram do decoder replicado de `decode_latent`.
- **Decisão medida**: TRELLIS.2 roda em **512³ single-stage** — 1024_cascade OOM confirmado 2× (até `--max-tokens 24576`); oficial exige 24GB. Registrado honestamente.
- **Smoke OK**: caneca preproc → 925.437 verts / ~2M faces / 82s run / 0 erros. Renders de preview na mesa do dono (`preview_a/b.png`).
- **Benchmark parcial** (`~/printer3d-work/c3-bench/<caso>/<modo>/report.json`, retomável):
  - triposr: **10/10 OK** (~43-80s, VRAM pico até 10,6GB — inputs densos)
  - trellis: **10/10 rodados, 9 OOM** (só local_gancho OK) — entradas pré-processadas densas estouram VRAM consistentemente (Fase 1 era 3/10)
  - triposg: 3/10 · trellis2: 0/10 — **re-run em curso desde 2026-11-17 ~manhã**
- Fixes no orquestrador: sys.path prefere repo sobre `~/printer3d-work/gen` (base_plugin antigo sombreava `venv_py`); triposr não recebe `--seed` (determinístico).
- **Benchmark concluído (2026-11-17 ~12:25)** — resultados reais (`scores.md`/`results.json` na evidência):
  - **trellis2: 10/10 OK** — mediana 156s, VRAM pico máx **5.451 MiB** (low_vram funciona; ~9GB de folga na 3060)
  - **triposr: 10/10 OK** — mediana 45,5s, VRAM máx 10.642 MiB
  - **trellis: 1/10 OK** (9 OOM — entradas densas; Fase 1 era 3/10)
  - **triposg: 7/10** — dono ordenou pular os 3 casos restantes (2026-11-17); parcial documentado
- Render (Blender headless, câmera/luz idênticas, 2 ângulos × malhas existentes) + `publish` executados → `evidence/fase-c/comparativo-3060/{gallery.md,scores.md,results.json,gallery_render/}` (58 renders commitados).
- **Próximo gatilho: veredito visual do dono na galeria → decisão → ADR-007** (nenhum gerador é promovido automaticamente — ADR-005 segue valendo).
- **Viewer 3D web deployado e FUNCIONAL (2026-11-17)**: `tools/modelos3d-site/` (three.js r170 vendor local em `vendor/jsm/`, orbit/pinch, modo VS lado a lado, mobile, errbox de debug) → container `modelos3d` (nginx:1.25-alpine estático) na VPS + rota `/modelos3d/` no trivestia-nginx (backup + nginx -t + reload + smoke — mesmo padrão do printflow3d/deploy.sh). Live: **https://brunointegrations.com/modelos3d/** — **verificado com Chrome headless** (DOM + screenshot) antes de entregar. Casos: 10 do C3 + `anubis_a`/`anubis_b` (imagens do dono, TRELLIS.2+TripoSG apenas, fora do benchmark). GLBs em `~/printer3d-work/modelos3d-site/models/` (~241MB, não commitados). Deploy: `tools/modelos3d-site/deploy.sh` (MODELS3D_DIR override p/ models). Manifest: `gen_manifest.py` (C3) — anubis foi editado à mão no JSON.
- **[!] Qualidade visual TRELLIS.2 no viewer (diagnosticado, NÃO resolvido)**: só os trellis2 aparecem "picotados/meio transparentes". Causa provável medida: `mesh_reparada` do trellis2 tem **winding inconsistente** (`is_winding_consistent=False` — triposg/triposr=True) + não-watertight → faces invertidas = transparência/z-fighting. Já tentado: re-export de 250k→500k faces (sem efeito — não era decimate). Em teste quando a sessão acabou: `trimesh.repair.fix_winding()` + `fix_normals()` no OBJ antes do export GLB (script `/tmp` efêmero — **recriar**: load trimesh → fix_winding → fix_normals → export OBJ → `eg.py` p/ GLB). Se resolver, re-exportar só os `*__trellis2.glb` e re-deployar models. Nota: degrau de silhueta 512³ é inerente; 1024³ OOM na 3060 (C1 do colega pode mostrar em mais VRAM).

### Registro C3 anterior (2026-11-16, sessão interrompida no limite de quota)

- **Infra 100% montada e validada por partes** (detalhes e armadilhas: `evidence/fase-c/comparativo-3060/install-notes.md` — LEIA PRIMEIRO):
  - venvs próprios: `~/.venvs/trellis2` (torch 2.8.0+cu128 + xformers + lock do fork) e `~/.venvs/triposg` (torch 2.8.0+cu128, **diffusers 0.33.1 + transformers 4.57.3** — pins obrigatórios);
  - extensões CUDA compiladas com gcc-14 + toolkit 12.8 (`~/cuda-12.8`, com **patch de header p/ glibc 2.42**): flex_gemm ✓ cumesh ✓ o_voxel ✓ nvdiffrast ✓ (nvdiffrec falhou no link — não é necessário p/ shape-only);
  - pesos: TRELLIS.2-4B ✓ TripoSG ✓ DINOv3 (mirror camenduru, oficial é gated) ✓ BiRefNet público no lugar do RMBG-2.0 gated ✓;
  - código novo no repo: `trellis2_runner.py`, `triposg_runner.py`, `trellis2_plugin.py`, `triposg_plugin.py`, `run_comparativo_c3.py`, `base_plugin.py` (attr `venv_py`, backward compat);
- **Smoke TripoSG: OK** — caneca preproc: 959.744 verts / 1,9M faces / 76,6s / 0 erros (13× mais vértices que TripoSR);
- **Smoke TRELLIS.2: INCONCLUSIVO** (sessão acabou no meio; bloqueios anteriores — DINOv3 e RMBG gated — já resolvidos; **re-rodar é o passo 1**);
- **Benchmark 10×4, render, publish: NÃO RODADOS** — comandos prontos no install-notes §Próximos passos.

### Registro C2 (2026-11-16)

- 10/10 casos pré-processados (log real em `evidence/fase-c/preproc/execucao-c2.log`); par antes/depois commitado (trex_figurine).
- **Achado honesto:** o caso `trex_figurine` contém a imagem do **pergolado (trellis) do repo oficial da Microsoft** (`T.png` — manifest provava a origem desde a Fase 1) — caso MAL NOMEADO desde a criação do testset, não é bug do pré-processamento. Testset é imutável; comparação segue válida (mesma entrada para todos); renomeação fica registrada como pendência cosmética de fase futura.
- Upscale (Real-ESRGAN): OFF por default, deps ausentes — pendência registrada, nada pesado instalado (decisão C2).

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
| 7 | Fechamento: PROGRESS/HANDOFF + relatório ao dono + votação do default mode (→ ADR-005) | [x] **veredito do dono: REPROVADO global — sem default mode (ADR-005)** |

### Fechamento da Fase 1 — veredito do dono (2026-11-16)

- Dono **recusou a votação por caso** e deu veredito global nas duas galerias (3060 e 5060 Ti): **"ficou tudo ruim" / "esse TripoSR é uma bosta"** — reprovação dos dois geradores. Registrado em `evidence/benchmark/votacao-dono.md` (template arquivado, não preenchido).
- **ADR-005** (`docs/decisions/ADR-005-sem-default-mode.md`): nenhum default mode eleito; **nenhum gerador image→3D entra em uso produtivo** até decisão do dono; benchmark permanece válido como referência técnica; Forja/pipeline não são afetados.
- **Fase 1 encerra com veredito NEGATIVO** — critério de aceite "dono aprova" não atendido (resultado honesto; a infra/tech da fase foi entregue e validada). Consistência com os dados: TripoSR = sólidos robustos porém baixa fidelidade (~74k verts); TRELLIS = detalhe mas casca fina + OOM + 3 reprovações visuais na Jubarte.
- Próximo passo é decisão do dono (opções em ADR-005 §4): avaliar gerador novo no mesmo benchmark, caminho procedural Blender, ou direção própria. Nenhuma instalação nova até lá (regra de uma fase por vez).


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

- **r3 "B2" (2026-11-05): ENTREGUE SEM APROVAÇÃO INTERMEDIÁRIA (ordem do dono)** — input `jubarte_b2.png` (cerâmica cinza-pedra) fornecido pelo dono em Downloads, procedência: uso pessoal.
- **[x] TRELLIS 2/2** (seeds 42/777; VRAM confirmada antes de cada: 11.031 → 11.996 MiB): cand_42 503.956v/98s/12.094 MiB · cand_777 509.184v/82s/12.076 MiB.
- **[x] Forja B2 multi-componente**: regra dos **2% das faces** implementada (nunca "maior apenas") — ambos candidatos vieram com baleia+anel **fundidos num único componente** (4 e 2 fragmentos <2% descartados); união manifold3d não necessária. PyMeshFix individual, escala 200mm, espessura com localização.
- **[x] Vencedor automático (critério registrado)**: **cand_42** — ambos watertight; decidiu o critério 2 (espessura mínima 0,315 > 0,289mm). `experimento_jubarte.json`.
- **[!] FRAGILIDADE**: espessura mínima 0,315mm (<1,6mm) — pontas/caracóis podem quebrar no FDM; localização registrada (x≈0,53 y≈0,42 z≈0,07 do componente). Correção (Solidify) = fase futura.
- **[x] Entrega**: `forja_out/jubarte_final.stl` (200mm, watertight) + 6 renders 1600px clay (2 cand × frente-3/4/perfil/traseira-3/4) + `impressao_jubarte.md` (0,2mm, tree só cauda/barbatanas/caracóis, brim no pedestal, PLA mármore/prata/pedra).

- **r2 (noite 2026-11-04): também REPROVADA** — input Gemini escolhido a olho pelo dono → TRELLIS 94.722v ok, Forja @200mm ok (espessura 3,72mm), mas visual reprovado ("ficou ruim"). `jubarte2/reviews2.json`.
- **Diagnóstico sistêmico (2 rodadas, inputs diferentes)**: o elo fraco é o **TRELLIS para escultura orgânica complexa** — consistente com o benchmark (manifold 4/10, OOM nos densos, melhor em props). Pipeline técnico (SD/Gemini→TRELLIS→Forja→review) funciona; a qualidade do gerador para o sujeito, não.
- **Opções abertas ao dono**: (A) mesma imagem no TripoSR — A/B barato de gerador; (B) baleia procedural Blender + anel na Forja; (C) cancelar vitrine e direcionar TRELLIS a props simples.

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

## Onboarding multi-máquina (2026-11-14) — branch `feat/onboarding-multi-maquina` `[~] aguardando merge do dono`

Preparação do repo para o 2º contribuidor (leigo, outra máquina: Windows 11, WSL2 a instalar, RTX 5060 Ti 8GB Blackwell/sm_120). Contexto: ADR-006.

| # | Tarefa | Status |
|---|---|---|
| 1 | Monitor WSL da área de trabalho investigado e documentado (`docs/onboarding/monitor-wsl.md`) + fontes em `evidence/onboarding/` | [x] |
| 2 | AGENTS.md/README despersonalizados (`~/.venvs/printer3d-ia`, helper `tools/setup/py.sh`, tabela dual-shell, ADR-006) | [x] |
| 3 | Perfis de máquina: `docs/operations/machine-profiles/` (rtx3060-12gb medido · rtx5060ti-8gb "A VALIDAR" · profiles.json) | [x] |
| 4 | `gpu_guard.py` paramétrico por perfil (env `PRINTER3D_MACHINE_PROFILE`/`PRINTER3D_GUARD_MIN_FREE_MIB`, default 3060 = 10.000 MiB intacto) + 7 testes + evidência (`evidence/gpu-guard-parametric/`) | [x] |
| 5 | Onboarding: `onboarding-novato.md` (Fases A/B com GATEs), `glossario.md`, `PROMPT-ONBOARDING-A.md`, `PROMPT-ONBOARDING-B.md` | [x] |
| 6 | `tools/setup/`: check-prereqs / install-python311 / make-venv / check-blender / check-gpu / collect-audit — idempotentes, logados, validados na 3060 (`evidence/setup/`) | [x] |
| 7 | Governança multi-pessoa no AGENTS.md §7 Contribuidores | [x] |

### Integração do PR #1 — Fase B na máquina do colega (2026-11-16) `[x]`

- PR `feat/yuriiyuriiyurii91-afk/setup-inicial` revisado pelo dono e **mergeado na main** (`614c3ac` + 2 commits de correção do dono: `1fb513f`, `b560d77`).
- Setup Fase B na 5060 Ti: Blender 5.0.1, venv torch **2.11.0+cu128** (capability (12,0) ✓), TripoSR @ 107cefd + pin **transformers 4.46.2** (5.x quebra o load do ckpt — descoberta real do setup, corrige nota da Fase 1 sem reescrever evidência).
- **Benchmark TripoSR na 5060 Ti: 10/10 OK, 0 erros** — mediana 14,4s, VRAM pico 4385 MiB (< guard 6500 ✓), manifold 9/10. TRELLIS 10/10 sem mesh (inviável confirmada por execução). Evidência: `evidence/rtx5060ti-8gb/benchmark/`.
- Correções do dono na revisão: (1) removidas 8 duplicatas de logs da máquina do colega em `evidence/setup/` (violação §7.1 — copias namespaced já existiam); (2) meta do benchmark agora reporta o python real (`platform.python_version()` — estava `py3.11.16` hardcode; o results.json da 5060 Ti mantém o metadado gerado, divergência registrada aqui e no perfil).
- Perfil `rtx5060ti-8gb.md` + `profiles.json` atualizados pelo dono com os números medidos da Fase B — **nenhum "A VALIDAR" restante neste perfil**.

### Pendências deste update (não bloqueiam o merge)

- [~] Números da máquina do colega — **Fase A CHEGOU e foi integrada (2026-11-15)**: audit real em `evidence/rtx5060ti-8gb/environment-audit-fase-a.md`; perfil `rtx5060ti-8gb.md` e `profiles.json` atualizados com valores medidos. **Fase B também chegou e foi integrada (2026-11-16, PR #1)** — perfil sem nenhum "A VALIDAR" restante.
- [x] Guard da 5060 Ti **confirmado como seguro**: livre medido 6803 MiB (desktop ativo usando 1090 MiB dos 8151 MiB) → 6500 MiB com margem ~303 MiB. **Validado em produção no benchmark Fase B**: liberou 10/10 jobs (6687–6691 MiB livres), pico do TripoSR 4385 MiB. Nota operacional registrada no perfil: fechar navegadores/jogos/overlay NVIDIA antes de jobs GPU nesta máquina.
- [x] Votação do dono na galeria do benchmark → ADR-005: **fechada com veredito global NEGATIVO** (dono recusou votação por caso; reprovou os dois geradores; ADR-005 registra "sem default mode").
- [ ] Monitor WSL: nesta máquina o watcher (`WSLIconWatcher` na chave Run) não estava rodando na coleta (reinício recente) — inofensivo (janela mostra estado correto); registrar na cabeça se o ícone congelar.

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

## Registro — Fase B setup na máquina rtx5060ti-8gb (2026-11-16, contribuidor yuriiyuriiyurii91-afk)

- Perfil ativado: `PRINTER3D_MACHINE_PROFILE=rtx5060ti-8gb` (`~/.bashrc` + `~/.profile`).
- Repo clonado em `~/projetos/3dprinter-setup-ia`; remote de push em SSH.
- Blender 5.0.1 headless instalado (tarball oficial em /opt + symlink; libs do sistema: libsm6, libxext6, libgl1, libusb-1.0-0). `check-blender.sh` OK.
- venv `printer3d-ia`: Python 3.11.18, **torch 2.11.0+cu128**, `cuda.is_available()=True`, capability **(12, 0)** — `check-gpu.sh` OK.
- TripoSR em `~/tools/TripoSR` @ `107cefd` — repo oficial **VAST-AI-Research/TripoSR** (o caminho "microsoft/TripoSR" não existe; API GitHub responde 404). Pesos `model.ckpt` = 1.677.246.742 bytes (stabilityai/TripoSR, MIT) em `~/tools/TripoSR/`.
- Deps no venv: **transformers 4.46.2** (5.x quebra o load do ckpt — keys do ViT renomeadas em 5.x; 4.46.2 é a pinada pelo TRELLIS) · omegaconf 2.4.0 · rembg[cpu] (backend bria-rmbg-2.0, ~1 GB baixado) · open3d 0.20.0 · trimesh 5.2.1 · scikit-image 0.26.0 (base do shim torchmcubes) · pytorch-lightning 2.6.6 · einops · xatlas · imageio · pillow · huggingface-hub.
  - Nota: `evidence/fase1/triposr-install-notes.md` registra "transformers não é importado" — **incorreto no clone 107cefd** (`tsr/models/tokenizers/image.py` importa transformers). Na 3060 funcionou porque o TRELLIS já trazia transformers no venv.
- Shim torchmcubes recriado em `~/printer3d-work/shim/torchmcubes/` (skimage, sem CUDA/nvcc no WSL — conforme notes da Fase 1). Plugins (`base_plugin.py`, `triposr_plugin.py`, `gpu_guard.py`) em `~/printer3d-work/gen/`; runner sincronizado via `GENERATOR_SRC` (override de env — sem editar repo).
- Portabilidade (ADR-006): commit `b0818b6` — `run_benchmark.py` deriva testset/render/evidência do próprio repo (antes: caminhos hardcoded do PC de referência, violando §1.6); evidência de benchmark namespaced por `PRINTER3D_MACHINE_PROFILE`.
- **Benchmark TripoSR nesta máquina — 10/10 OK, 0 erros:** pico **4385 MiB** (todos os casos) · tempo **13,42–31,11 s**/caso · vértices 45.976–107.770 · manifold **9/10** (`estrutura_castelo` False→False) · guard OK (liberado com 6687–6691 MiB; linha de base desktop ~1,2 GB). Log: `evidence/rtx5060ti-8gb/benchmark-triposr-2026-11-16.log`; `results.json`/`scores.md`/`gallery.md`+20 renders: `evidence/rtx5060ti-8gb/benchmark/`. TRELLIS não executado (inviável nesta GPU — decisão por descarte já registrada no perfil).
- Auditoria Fase B consolidada: `evidence/rtx5060ti-8gb/audit-fase-b-2026-11-16.md` (log do collect-audit no mesmo diretório).
- Rodadas de setup falhadas arquivadas em `~/printer3d-work/benchmark-run1-failed-2026-11-16/` e `benchmark-run2-failed-2026-11-16/` (erros reais: transformers ausente; transformers 5.x incompatível).
- PR: `feat/yuriiyuriiyurii91-afk/setup-inicial` → main — revisão do dono pendente (trocar os "A VALIDAR (Fase B)" do perfil pelos valores acima).
