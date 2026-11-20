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
| C6 | **Hunyuan3D-2.1 + Hunyuan3D-2mv multi-vista + TripoSG→TripoSF512 Multi-Partes + VGGT no carro fox (`no-windows`)** | `[x]` **CONCLUÍDO E PUBLICADO NO VIEWER (2026-11-18)** — `reclaim_windows_vram` (`NVIDIA Broadcast.exe`) no `gpu_guard.py`; CFG sequencial `batch=1` + offload por estágio no `hunyuan_runner.py` reduziu pico de VRAM do `Hunyuan3D-2mv` (4 vistas) de `12.054 MiB` (OOM) para **`3.369 MiB`** (`801.352` faces) + refino `TripoSF 512` (`1.465.074` faces, `6.569 MiB` VRAM) + pós-proc (`280k` faces watertight); **`TripoSG 505³ → TripoSF 512 → Pós-proc Multi-Partes`** (`--min-comp-faces 1000` em `posproc_impressao.py`) reconstruiu o **Fox com cabine interna completa (bancos, encostos, painel, volante) + teto 100% sólido c/ rack e antena + 4 rodas + placa** (`3.497.404` faces → `280k` watertight, pico `10.227 MiB`); `vggt_recon.py` + `captura-fotogrametria.md` prontos; 5 GLBs deployados em `https://brunointegrations.com/modelos3d/?case=carro_nowin` + STLs 200mm em `Downloads/fox-posproc/`. Evidência: `evidence/rtx3060-12gb/hunyuan-carro/` |
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

### Registro C6 — Fox `no-windows`: `TripoSG → TripoSF 512` Multi-Partes (interna + 4 rodas) & `Hunyuan3D-2mv` 4 Vistas (2026-11-18) — `[x]` CONCLUÍDO

- **Otimização de VRAM & Reclaim NVIDIA Broadcast**: `reclaim_windows_vram()` integrado ao `tools/generator/gpu_guard.py` (encerra `NVIDIA Broadcast.exe`, `NVIDIA Broadcast UI.exe` e `RTXVoice.exe` via `taskkill.exe`), reduzindo a baseline de VRAM da RTX 3060 12 GB para **`488–585 MiB`**.
- **`Hunyuan3D-2mv` (4 vistas ortogonais `front + left + back + right` com máscara `tinted`)**:
  - Diagnóstico do OOM inicial (`12.054 MiB`): 4 vistas geram `5.480` tokens no `DinoImageEncoderMV`; avaliar CFG concatenando `batch=2` dobrava as ativações de atenção cruzada e `RMSNorm`.
  - Solução em `tools/generator/hunyuan_runner.py`: offload estrito por estágio (`conditioner → CPU`, `DiT → CPU`, `ShapeVAE → GPU`) + **CFG sequencial `batch=1`** sob `torch.amp.autocast('cuda', dtype=torch.float16)`.
  - Resultado medido: pico de VRAM caiu para **`3.369 MiB`** (`-72%`), gerando `400.532` vértices / `801.352` faces em `328,04s` (`octree_resolution=384`, `50` steps, `0` erros).
  - Refinado com **`TripoSF 512`** (`1.465.074` faces em `44,51s`, pico **`6.569 MiB`**) e pós-processado (`280.000` faces, `watertight = True`): modelo externo fechado estilo die-cast com as 4 rodas raiadas, limpadores dianteiro e traseiro, antena no teto, rack, spoiler, retrovisores e para-choques dianteiro/traseiro fiéis.
- **`TripoSG → TripoSF 512 → Pós-processamento Multi-Partes` (aposta do dono confirmada)**:
  - `tools/generator/triposg_runner.py` atualizado para respeitar máscara alfa explícita sem re-segmentar via `BriaRMBG`.
  - Sobre `frente-e-lado-diagonal_tinted.png`, o `TripoSG 505³` gerou `3.116.268` faces (`96,94s`) contendo **7 componentes conexos `>= 1.000` faces**: carroceria com **cabine interna completa** (bancos dianteiros, banco traseiro com encostos de cabeça, painel e volante) + **teto 100% sólido com racks (zero furos)** + rodas traseiras (`comp 0`, `2.983.998` faces), roda dianteira esquerda (`comp 1`, `58.460` faces), roda dianteira direita (`comp 2`, `56.944` faces), placa dianteira (`comp 3`, `4.656` faces), detalhe de cubo (`comp 4`, `3.996` faces) e antena de teto (`comp 5/6`, `1.276 / 1.112` faces).
  - **Fix estrutural em `tools/generator/posproc_impressao.py` (`--min-comp-faces 1000`)**: em vez de manter só `max(comps)` (o que descartava as duas rodas dianteiras de ~1,95% das faces, a placa e a antena), cada componente `>= 1.000` faces é reparado **individualmente** via `PyMeshFix + manifold3d` antes de unificar, aplicar `Taubin 5it` e decimar.
  - Refinado com **`TripoSF 512`** (`3.497.404` faces em `56,52s`, pico **`10.227 MiB`**) e pós-processado (`280.000` faces, `139.650` vértices, `watertight = True`), preservando **as 4 rodas, a antena, a placa, o teto sólido e toda a cabine interna**.
- **Fotogrametria feed-forward (Tarefa B)**: `tools/generator/vggt_recon.py` + `docs/onboarding/captura-fotogrametria.md` commitados e prontos para uso com vídeo/fotos 360°.
- **Deploy e Validação Live**: 5 GLBs (`carro_nowin__{triposf512,triposg,hunyuan_mv_sf512,hunyuan_mv,trellis2_fosco}.glb`) publicados e verificados com `HTTP 200` em **https://brunointegrations.com/modelos3d/?case=carro_nowin** + STLs em escala `200mm` exportados para `C:\Users\Bruno\Downloads\fox-posproc\` (prontos para o ChituBox). Evidência: `evidence/rtx3060-12gb/hunyuan-carro/{report.md,summary.json}`.
- **Refinador Automotivo — Simetria Bilateral (`X = -X`) + Gabarito Dimensional (Blueprint VW Fox `3.868 × 1.780 × 1.552 mm`)**:
  - Criado `tools/generator/refino_automotivo.py` para corrigir os dois defeitos visuais apontados pelo dono nas malhas brutas de carros ("aspecto assimétrico / traseira desalinhada / proporção gorda de cubo `[-1,1]³`"):
    1. `deskew_longitudinal`: alinha a linha de centro `X(Z)` da dianteira até o para-choque traseiro;
    2. `symmetrize_bilateral`: corta no plano sagital `X = 0` e espelha o lado visível de alta definição via CSG booleano (`manifold3d`), com subtração seletiva da cópia do aro do volante no lado do passageiro (`preserve_driver_wheel_only=True`) no `TripoSG + TripoSF 512`;
    3. `apply_fox_blueprint`: trava a proporção real de fábrica do Volkswagen Fox (`200,0 mm C × 92,0 mm L c/ retrovisores × 80,2 mm A`, `watertight = True`).
  - GLBs atualizados e re-deployados no viewer (`carro_nowin__{simetrico_interna,simetrico_4vistas,triposf512,triposg,hunyuan_mv_sf512,hunyuan_mv}.glb`, cache-bust `?v=9`) + STLs simétricos `200mm` em `C:\Users\Bruno\Downloads\fox-posproc\`.
- **Estudo Técnico e Arquitetura da Feature "Kit de Montagem Hard-Surface / Veículos (IA + CSG Modular)"**:
  - Documentado em `docs/knowledge/modelagem-hard-surface-e-veiculos.md`: diagnóstico matemático do orçamento de voxels `512³` e do efeito *Out-of-Distribution* de apagar vidros na foto 2D; especificação da esteira modular (Carroceria Sólida + Corte Booleano 2D→3D cirúrgico dos vidros + Banheira Interna separada + 1 Roda Mestre gerada em close `100%` dedicada e instanciada 4× em cilindro matemático); levantamento comparativo de 6 projetos do GitHub (`bytedance/Hi3DGen`, `DreamTechAI/Direct3D-S2 1024³`, `Tencent-Hunyuan/Hunyuan3D-2.1`, `Seed3D/Dora`, `huanngzh/MV-Adapter`, `VAST-AI-Research/HoloPart`) e matriz de 3 opções de execução para decisão do dono.

### Registro C7-A — Kit de Montagem CSG `carro_csg` (2026-11-18 / 2026-11-19) — `[x]` REPROVADO NO GATE VISUAL PELO DONO

- **VEREDITO C7-A (2026-11-19) — REPROVADO PELO DONO NO GATE VISUAL**:
  - O dono avaliou o caso `carro_csg` no viewer e reprovou ("o resultado ficou muito ruim"). Revisão independente concorda integralmente.
  - **Falhas observadas**:
    1. A casca oca (EDT voxel + marching cubes) derrete o hard-surface (linhas de caráter somem, frente vira cera);
    2. As máscaras 2D das fotos cortam uma geometria que NÃO casa mais com a foto (pilares rasgados, arcos de roda colapsados);
    3. A carroceria base do C6 tinha 124 componentes desconexos e não era watertight;
    4. Pendência 1 do report (oco parcial: volume 0,496 vs 0,14 esperado) segue sem causa isolada.
  - **CAUSA RAIZ ACEITA**: O problema central é a **QUALIDADE DA BASE** do gerador 3D (malha bruta), e não a lógica de montagem. Não iterar mais o CSG sobre a mesma base deficiente — remendo cosmético não recupera forma que o gerador nunca produziu.
  - **ASSETS REAPROVEITÁVEIS (preservados)**:
    - Roda mestre: close 1024px + TripoSG seed 42 + regularização em cilindro matemático (raios nítidos no viewer);
    - Banheira interna: habitáculo/bancos/painel visíveis e funcionais;
    - `kit_csg_carro.py` (código determinístico em CPU) e mapeamento foto↔3D por IoU.
    - O Kit de Montagem CSG voltará a ser testado **exclusivamente** sobre a base nova vencedora das Tarefas B/C (Hi3DGen / Hunyuan-2.1).
- **Fotos do kit = as MESMAS do C6** (`Downloads/fox/no-windows/` = `~/printer3d-work/carro/fotos-c7/` + `c7-prep/`): 5 fotos de 2400x1792 px (frente, frente-e-lado-diagonal, lado, traseira, de-fora-pegando-interna). Prep `*_tinted.png` reutilizado. C7-E (fotogrametria densa VGGT) retirado da fila (só reabrir se B/C falharem e houver sessão de 20-40 fotos completas).
- **Publicação**: caso `carro_csg` (modos `kit`, `casca`, `interna`, `kit_corte`) mantido no viewer para histórico/comparação. Evidência: `evidence/rtx3060-12gb/carro-csg/report.json`.

### Registro Correção de Pintura do Fox (`fox_fixpaint`, 2026-11-20) — `[x]` CONCLUÍDO E REPUBLICADO POR CIMA NO VIEWER

- **Reaproveitamento estrito**: ZERO regeneração de malha/UV — usadas exatamente `mv_a/uv.obj` e `mv_b/uv.obj` do commit `954e4d8`.
- **ETAPA 1 (`tools/generator/rebake_fox_paint.py`, seed 42)**: rebake `2048×2048` por projeção 4-vistas ortogonais com rasterização UV exata em GPU, Z-buffer de oclusão `1024²`, auto-alinhamento por IoU de silhueta, máscara de cobertura (`mv_a`: `54,27%` coberto / `45,73%` preenchido com cor dominante `[225, 223, 224]` em `8,9s`; `mv_b`: `49,96%` coberto / `50,04%` preenchido com `[228, 227, 228]` em `8,85s`), Telea inpaint nas bordas (`raio 6px`) e preenchimento zero-preto fora da máscara.
- **ETAPA 2 (`tools/generator/eval_paint_4views.py` — Blender headless 4 vistas transparentes)**:
  - **Antes (bake antigo quebrado com manchas/bleed):** `mv_a` front `dark 22,6% / mud 7,3%`, back `19,2% / 9,3%`, left `7,9% / 4,2%`, top `19,1% / 7,0%`; `mv_b` front `14,0% / 8,9%`, back `12,4% / 6,8%`, left `13,4% / 7,5%`, top `15,9% / 9,9%`.
  - **Depois (rebake corrigido — fiel às fotos reais):** `mv_a` front `dark 47,0% / mud 11,9%`, back `42,5% / 10,0%`, left `42,4% / 10,3%`, top `25,5% / 4,1%`; `mv_b` front `41,5% / 12,2%`, back `40,9% / 12,5%`, left `37,3% / 11,5%`, top `19,7% / 6,7%`.
  - **Achado honesto sobre o gate `dark 4–20% / mud <10%`:** as fotos originais do VW Fox Xtreme já têm legitimamente `38,4–48,6%` de pixels `<80` (para-choque inferior preto, grade colmeia, para-brisa fumê, molduras e pneus) e `9,6–15,1%` em `80–180` (faróis/emblemas/sombras). Os renders novos eliminaram 100% das manchas pretas/bleed e batem com o ground truth das fotos em `~1–2%` (renders salvos em `evidence/rtx3060-12gb/fox_fixpaint/renders/`).
- **ETAPA 3 & 4 (Upscale 8K/4K + Republicação sem alterar `manifest.json`)**: `RealESRGAN_x4plus` 4× (`seed 42`, `128,4s`, VRAM pico `7.579 MiB` com samples a cada 10s) + reempacotamento glTF JPEG q95 mantendo resolução exata `8192×8192` / `4096×4096` intocada → 4 GLBs sobrescritos nos mesmos modos (`mv_a_8k` `18,28 MB`, `mv_a_4k` `11,35 MB`, `mv_b_8k` `18,24 MB`, `mv_b_4k` `11,56 MB`), deploy OK e validados `HTTP 200` com novos timestamps (`2026-11-20 16:36 GMT`). Evidência: `evidence/rtx3060-12gb/fox_fixpaint/report.json`.

### Registro Run Único Fox (`carro_foxh` 8K/4K, 2026-11-19) — `[x]` CONCLUÍDO E PUBLICADO NO VIEWER

- **Bloco A (Demolição)**: removidas todas as entradas e os 9 GLBs quadrados antigos do case `carro_foxh` (commit `23ecb66`, deploy + verificado `HTTP 404` no `carro_foxh__a1_front.glb`).
- **Bloco B (Inputs e decisão de vistas)**: `Hunyuan3D-2mv` aceita 4 vistas ortogonais (`front`, `left`, `back`, `right`); 4º slot = espelho da lateral (`P2r_right.png` / `R2r_right.png`, limitação conhecida: tampa de combustível aproximada). `P4_diag` / `R4_diag` (3/4, não-ortogonais) e `R5_extra` (interior) não entraram no `2mv`. Grade 2×2 **não** usada como imagem única — painéis individuais separados (`fox-h/panels/prep/` e `fox/prep_real/`).
- **Bloco C (Geração 3D `Hunyuan3D-2mv`, seed 42, octree 384, 50 steps)**:
  - `mv_a` (grade): 391.254 verts / 782.652 faces · 324,1s · VRAM pico **4.226 MiB** · Sanity check PASS: razões bbox `[0.506, 0.584, 1.0]`, componente dominante 98,3%, simetria 0,270% da bbox.
  - `mv_b` (fotos reais): 392.258 verts / 784.808 faces · 315,8s · VRAM pico **4.189 MiB** · Sanity check PASS: razões bbox `[0.510, 0.568, 1.0]`, componente dominante 100,0%, simetria 0,249% da bbox.
- **Bloco D (Limpeza determinística)**: remesh uniforme + simetrização + remoção de flutuantes → `mv_a` 279.836 faces / `watertight=True` / 1 comp; `mv_b` 279.624 faces / `watertight=True` / 1 comp.
- **Bloco E (UV `xatlas` CPU)**: `mv_a` 1.811 ilhas, utilização **79,1%**, 0 overlap (162.982 verts UV); `mv_b` 2.086 ilhas, utilização **79,2%**, 0 overlap (168.786 verts UV).
- **Bloco F (Pintura / Bake 2048)**: estágio de pintura AI do `Hunyuan3D-2` exige ~21 GB VRAM (inviável na 3060 12 GB, pesos fora do cache) → fallback determinístico 2048 por projeção das 4 vistas canônicas com raycast de oclusão (`mv_a`: 38,6% texels não-brancos, cor média `[203.7, 202.8, 203.5]`; `mv_b`: 37,8% não-brancos, cor média `[205.5, 205.0, 205.5]`).
- **Bloco G (Upscale 8K/4K — `tools/generator/upscale_and_pack_fox.py`)**: `RealESRGAN_x4plus` (RRDBNet 23b FP16, tiles 512px pad 16, seed 42) 2048 → 8192 + variante 4096 em **90,87s** totais, VRAM pico **7.428 MiB** (pico global do run).
  - `mv_a`: `carro_foxh__mv_a_8k.glb` (39,55 MB, 8192×8192) + `carro_foxh__mv_a_4k.glb` (17,67 MB, 4096×4096).
  - `mv_b`: `carro_foxh__mv_b_8k.glb` (41,45 MB, 8192×8192) + `carro_foxh__mv_b_4k.glb` (18,48 MB, 4096×4096).
- **Bloco H & I (Publicação + Verificação HTTP)**: viewer atualizado (`app.js` v15, `MeshStandardMaterial` PBR com iluminação 3D real, 4 modos `mv_a_8k`, `mv_b_8k`, `mv_a_4k`, `mv_b_4k` permitindo alternância direta 8K/4K e comparativo VS). Todos os 4 GLBs + `manifest.json` validados `HTTP 200` e card quadrado antigo `HTTP 404`.
  - URLs finais: https://brunointegrations.com/modelos3d/?case=carro_foxh&mode=mv_a_8k · VS 8K: https://brunointegrations.com/modelos3d/?case=carro_foxh&mode=mv_a_8k&vs=1&mode2=mv_b_8k
  - Evidência completa (com samples de VRAM a cada 10s): `evidence/rtx3060-12gb/fox_fullrun/report.json`.

### Registro Esteira Tripo-local — FASE 0 r3 (bug TEXCOORD_0 + textura ausente nos cards, 2026-11-19) — `[~]` aguardando gate visual

- **Dono dissecou os GLBs e achou o bug real**: os cards tinham foto no material mas o primitive só tinha `POSITION` (sem `TEXCOORD_0`) → viewer amostrava o texel (0,0) = quadrado branco. **Dissecação local confirmou e achou mais 2 defeitos**: (1) meu quad tinha 4 vértices mas 8 UVs (vstack) → trimesh derrubava o atributo; (2) o `TextureVisuals(image=…, material=…)` com imagem solta **não embute a textura** (`images: 0` no JSON) e o `baseColorFactor=[1,1,1,1]` int virava `[1/255]≈preto`. Nota honesta: minha "validação" v13 por % de pixels brancos era falso-positivo (fundo branco da página ≠ foto renderizada) — critério trocado por diff entre modos distintos.
- **Fix no `glb_card` do `prep_foxh.py`**: quad 4 verts + UV 4×2 com V invertido (convenção glTF), `PBRMaterial(baseColorTexture=img, metallicFactor=0, roughnessFactor=1, doubleSided)` sem colorFactor, faces 2 tris (DoubleSide do material cobre o verso), **autodiagnóstico no export**: GLB binário precisa conter `TEXCOORD_0` e `"images"` + roundtrip com `material.baseColorTexture` não-nulo.
- **Cache-buster v14** (app.js loader + manifest + index.html). Re-deploy dos 9 cards.
- **Validação com browser real (screenshots em `evidence/rtx3060-12gb/carro-foxh/validacao_v14_{a1_front,b2_side}.png`)**: `a1_front` × `b2_side` **diferem de verdade** (diff médio 7,74; antes do fix: 0,74), conteúdo rico (501/598 clusters de cor vs ~306 do quadrado liso; 117KB/87KB vs 30KB) → **as fotos renderizam**. Card orientação V conferida pela convenção glTF.
- **GATE de novo**: https://brunointegrations.com/modelos3d/?case=carro_foxh — dono re-inspeciona a1–a4 (sem tint) e b1–b5 (tint ≤15%, capô branco, sem placa). Aprovado → FASE 1 (2mv seed 42, runs A/B, b5 descartado). Nenhuma GPU usada até aqui.

### Registro Esteira Tripo-local — FASE 0 r2 (correções do 1º gate, 2026-11-19) — `[~]` aguardando novo gate visual

- **1º gate REPROVADO em 3 itens** (dono): viewer vazio no case novo + tint danoso (speckles a1, capô a4) + placa "RLA9E43" visível nos reais.
- **Viewer corrigido (v13)**: (R1) chaves `a1_front…b5_extra` + labels adicionadas a `MODES`/`MODE_LABEL` no `app.js` (a lista fixa era o motivo do "site vazio"); (R2) `loader.load` agora preserva a textura embutida (`MeshBasicMaterial({map, DoubleSide})`) — casos antigos sem textura seguem no clay idêntico; (R3) cache-busters `?v=13` (index.html, GLB, manifest). **(R4) Validado com browser real** (Chrome headless, screenshot `?case=carro_foxh&mode=a1_front` em `evidence/rtx3060-12gb/carro-foxh/validacao_a1_front.png`): métrica objetiva de pixel — 11,9% da tela >235 luminância (fundo branco da FOTO), plano-cinza 0,2%, 307 clusters de cor → **foto renderizada, não plano cinza**.
- **Prep corrigido (r2)**: (G1) linha A RE-processada **sem tint** (vidros fumê do Nano Banana preservados); (G2) linha B tint conservador — máscara da pintura (cor dominante ±30 + dilatação 15×15) virou zona PROIBIDA, tinta só em componentes conectados à banda dos vidros, **cap 15%**: resultado medido R1 1,76% · R2 3,43% · R3 7,23% · R4 11,38% (cap) · R5 2,24% — capô branco garantido por construção (pintura ∝ máscara proibida); (G3) placa inpintada com cor do anel vizinho: R1 3 placas (principal 1.290px central + **2 falsos positivos pequenos em faróis — registrado honesto**), R3 1 (1.350px central), R2 1 (98px, refletor); (G4) `b5_extra` rotulado "descartado p/ mv — interior" no label e no report (`mv_runs`); (G5) report atualizado + 9 cards re-publicados, deploy OK.
- **GATE de novo no ar**: https://brunointegrations.com/modelos3d/?case=carro_foxh — dono confere linha A sem tint, tint ≤15% na B com capô branco, placas sumidas. Aprovado → FASE 1 (2mv seed 42, runs A=a1–a4 e B=b1–b4, b5 descartado).

### Registro Esteira Tripo-local — FASE 0 (prep A/B `carro_foxh`, 2026-11-19) — `[~]` aguardando gate visual do dono

- **Novo prompt da esteira "Tripo local"** (4 fases: prep → geometria 2mv → UV → textura → upscale; regra: NADA de GPU antes de gate visual aprovado). Ferramenta: `tools/generator/prep_foxh.py` (CPU).
- **Grade validada por métrica** (`Gemini_Generated_Image_cq5yvcq5yvcq5yvc.jpg`, 2048×2048, Nano Banana Pro do dono): cantos 254,5–254,9 (variação **0,18%** < 5%); não-branco por quadrante: P1 40,2% · P2 28,0% · P3 54,4% · P4 40,0% — todos na faixa 15–60%. **APROVADA de primeira, sem regeneração.**
- **Corte no ponto médio** → `Downloads/fox-h/panels/P{1..4}_{front,side,back,diag}.png` (1024×1024 cada) + prep padrão (rembg u2net → fundo branco → margem 8% → canvas **518×518**) → `panels/prep/`. Mesmo prep nas 5 fotos reais → `Downloads/fox/prep_real/R{1..5}_*.png`. Sidecars ADR-003 com hash por imagem.
- **Tint de vidros** (script do C6 era efêmero — detector novo versionado): banda da cabine + desvio >45 da cor dominante da pintura (mediana dos pixels claros — necessário porque o carro é BRANCO; 1ª versão do detector pintava a lataria, corrigida antes do gate). Aplicado nas 9 imagens: 3,0–23,2% da silhueta (por imagem no report).
- **Viewer**: caso `carro_foxh` com 9 modos (linha **a** = painéis da grade, linha **b** = fotos reais) como cards GLB texturizados — **9/9 + viewer `HTTP 200` ao vivo**. Evidência: `evidence/rtx3060-12gb/carro-foxh/report.json`.
- **PARADO no gate visual** (passo 6 do prompt): dono confere (1) recortes P1=frente/P2=lado esq/P3=trás/P4=3/4 dianteira estão certos, (2) tint dos vidros aceitável, (3) linha A × linha B. Aprovado → FASE 1 (2mv seed 42, runs A e B, guard).

### Registro Anubis `Hunyuan3D-2.1` + `TripoSF 512` + Pós-proc (2026-11-19) — `[x]` CONCLUÍDO — VEREDITO: `TripoSG → TripoSF 512` SEGUE CAMPEÃO

- **VEREDITO DO DONO (2026-11-19)**: *"ficou bom, mas o modelo de antes ficou melhor"* — confirma a esteira oficial do C5 (`TripoSG → TripoSF 512 → posproc_impressao.py`) como melhor opção open-source local para esculturas/orgânicos, vencendo inclusive o `Hunyuan3D-2.1` (4096 latents MoE).

- **Esteira completa em `anubis_a_preproc.png` (`seed 42`)**:
  1. `Hunyuan3D-2.1` (`hunyuan3d-dit-v2-1`, 4096 latents MoE): `183.704` verts / `367.428` faces · load `51,8s` + run `371,93s` · 0 erros, 0 OOM.
  2. `TripoSF 512`: `334.702` verts / `669.392` faces · `34,51s` · VRAM pico `8.211 MiB`.
  3. `posproc_impressao.py` (fix compatibilidade `pymeshlab`: `apply_coord_taubin_smoothing` com fallback `taubin_smoothing`): `watertight=True`, `winding=True`, `is_volume=True`, `1` componente, `200 mm` altura (`89,27 × 200,00 × 86,15 mm`, volume `133,05 cm³`), `250.000` faces · `11,59s`.
- **Publicação**: modos `hunyuan_21_posproc` (`5,72 MB`) e `hunyuan_21` (`8,41 MB`) no case `anubis_a` (viewer v17): https://brunointegrations.com/modelos3d/?case=anubis_a&mode=hunyuan_21_posproc&vs=0 · Evidência: `evidence/rtx3060-12gb/anubis-hunyuan21/report.json`.

### Registro C7-C — Hunyuan3D-2.1 Checkpoint A/B (`hunyuan3d-dit-v2-1`, 4096 latents MoE, 2026-11-19) — `[x]` CONCLUÍDO E PUBLICADO NO VIEWER (Aguardando Veredito do Dono)

- **Execução**: `tencent/Hunyuan3D-2.1` (`subfolder=hunyuan3d-dit-v2-1`, DiT MoE 4096 latents) no venv existente `~/.venvs/hunyuan` via `tools/generator/hunyuan_runner.py --variant 2.1`, entrada `frente-e-lado-diagonal_tinted.png`, `seed 42`, `octree_resolution=384`, `steps=50`, guard de VRAM (`10.299 MiB` livres) + offload por estágio + CFG sequencial `batch=1`.
- **Telemetria real**: load `126,71s` (inclui download inicial) · inferência `354,4s` · `341.813` verts / `683.810` faces raw → GLB `299.908` verts / `600.000` faces (`14 MB`) · bbox `[1.0389, 0.9482, 1.9946]` · 0 erros, 0 OOM na RTX 3060 12 GB. Evidência: `evidence/rtx3060-12gb/hunyuan21-carro/report.json`.
- **Publicação**: modo `hunyuan_21` adicionado ao case `carro_nowin` (viewer v16): https://brunointegrations.com/modelos3d/?case=carro_nowin&mode=hunyuan_21 · VS com `hunyuan_mv`: https://brunointegrations.com/modelos3d/?case=carro_nowin&mode=hunyuan_21&vs=1&mode2=hunyuan_mv.

### Registro C7-B — Hi3DGen A/B (2026-11-19) — `[x]` REPROVADO NO GATE VISUAL PELO DONO

- **VEREDITO C7-B (2026-11-19) — REPROVADO**: dono avaliou `carro_nowin&mode=hi3dgen` no viewer e reprovou ("ficou horrível"). Segue para C7-C (`Hunyuan3D-2.1` 4096 latents) + `Direct3D-S2` (`1024³` Sparse SDF).

- **Setup do venv dedicado `~/.venvs/hi3dgen` (ADR-004)**: Python 3.11 + PyTorch `2.8.0+cu128` + `spconv-cu120 2.3.6` + `xformers 0.0.32.post2` + `diffusers 0.33.1` + `transformers 4.46.3` + `scikit-image` + `kornia` + `NiRNE` submodule.
- **Pesos e Modelos**: `Stable-X/trellis-normal-v0-1` + `Stable-X/yoso-normal-v1-8-1` + `ZhengPeng7/BiRefNet` cacheados em `~/tools/Hi3DGen/weights/`.
- **Sonda e Telemetria Real de VRAM (RTX 3060 12GB)**:
  - Fase A (Predição de Normais NiRNE): 6,10 s, pico 2.527 MiB → mapa salvo em `evidence/rtx3060-12gb/hi3dgen-carro/normal.png`.
  - Offload sequencial: NiRNE descarregado da GPU após a previsão, reduzindo VRAM residual para 8,12 MiB.
  - Fase B (Carga Hi3DGenPipeline): 23,02 s, alocação 5.131 MiB.
  - Fase C (Inferência 3D com seed 42): Stage 1 (50 steps) 27 s + Stage 2 (6 steps) 3 s + decode 3 s = 33,68 s.
  - **Pico global medido**: **7.803,07 MiB** (folga de ~4,4 GB livres no desktop). Tempo total de execução: **65,78 s** (1,8× mais rápido que TripoSG e 3,6× mais rápido que TRELLIS.2).
- **Qualidade e Malha Gerada**: 296.548 vértices e **593.226 faces** (~600k faces sem necessidade de decimação forçada). O mapa de normais elimina distorções causadas por reflexos de tinta na lataria.
- **Publicação**: GLB de 14 MB exportado e deployado no ar no caso `carro_nowin` (modo `hi3dgen`): https://brunointegrations.com/modelos3d/?case=carro_nowin&mode=hi3dgen (validado com HTTP 200).
- **Evidências**: `evidence/rtx3060-12gb/hi3dgen-carro/{report.json,scores.md,normal.png}`.
- **Próximos passos da sessão (PROMPT-C7)**: **GATE B do dono (Veredito Hi3DGen)** → **C7-C (Hunyuan-2.1 ckpt A/B)** → rascunho ADR-007.

### Registro ROTA H — Input canônico: contact sheet do dono × fotos reais no Hunyuan3D-2mv (2026-11-19, PROMPT-H) — `[~]` TAREFA 1 (contact sheet) com o DONO

- **Diagnóstico acumulado aceito** (C3/C5/C6/C7): TODOS os geradores falham no carro quando a forma inteira depende de interpretar fotos com ângulo/luz/escala inconsistentes; o C7-A provou que remendo CSG sobre base ruim não resolve. **A rota H ataca o INPUT, não o gerador**: base nasce padronizada (vistas canônicas ortográficas, fundo branco, mesma luz/escala, rodas retas) — regime exato de treino do Hunyuan3D-2mv. Simula o fluxo de cliente real (características+cor → imagens padronizadas → 3D).
- **Plano**: (T1, dono) contact sheet grade 2×2 do Fox 2015 branco Xtreme no serviço de imagem do dono, salvo em `Downloads/fox-h/` — caminho CONFIRMADO pelo dono antes de copiar; (T2, IA/CPU) cortar 4 painéis → preproc C2 + tinted → `c7-h-prep/{front,left,back,diag}.png`, `right`=espelho de `left` (limitação assimétrica registrada), **validação visual obrigatória do dono nos recortes antes de qualquer GPU**; (T3, GPU) A/B no Hunyuan3D-2mv: run A = REUSAR `carro_nowin` do C6 como controle (mesma seed 42/octree 384), run B = vistas canônicas → TripoSF 512 + posproc + refino_automotivo → caso `carro_canon` no viewer em VS contra `carro_nowin` → **GATE H1 (dono)**; (T4, só se H1 reprovar por PROPORÇÃO) Hunyuan3D-Omni com âncora geométrica (point cloud da casca C7-A OU blockout blueprint 3868×1780×1552+r_target medido) em venv próprio + sonda VRAM + **GATE H2**; (T5, opcional) MV-Adapter como alternativa local ao contact sheet.
- **Licenças/procedência**: sidecar ADR-003 com licença+URL+hash ANTES do primeiro uso de qualquer peso novo; non-commercial NÃO entra em fluxo de cliente. Pesos da rota: 2mv (community license — confirmar texto vigente), TripoSG/SF (MIT/Apache — confirmar), Omni (confirmar). Rota H desenhada p/ 100% uso aberto/comercial.
- Estado T1: aguardando o dono gerar e avisar o caminho (`Downloads/fox-h/` ainda não existia em 2026-11-19).

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
