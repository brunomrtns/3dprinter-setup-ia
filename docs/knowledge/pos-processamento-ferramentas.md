# Pós-Processamento de Peças Geradas por IA — Ferramentas e Esteira

> Base técnica para qualquer IA já saber operar a esteira de pós-processamento deste projeto. Complementa `stl-e-malhas.md` (topologia/reparo) e `impressao-resina.md` (regras de printabilidade). Pesquisa verificada em 2026-11-18 — log de verificação das fontes em `evidence/pesquisa-pos-processamento/fontes-verificadas.md`. A decisão estrutural (adoção da esteira v1) está proposta no **ADR-008** (status: Proposto, aguardando o dono).

## 1. Detalhe milimétrico × impressão em resina

O hardware MSLA resolve XY com pixel de ~0,019–0,024 mm (tela 12K) e Z com camada de 0,02–0,05 mm, mas o limite prático é o traço curado sobreviver à força de descolagem e ao manuseio. Por isso as regras do projeto (`impressao-resina.md` §3) são ordens de magnitude maiores que o pixel:

| Feature | Mínimo prático |
|---|---|
| Parede de peça oca | 2,0 mm |
| Detalhe em relevo | 0,5 mm de altura |
| Pino/furo de encaixe | 1,5–2,0 mm |
| Parte estrutural fina (dedo, antena) | ≥ 2,0 mm ou suporte dedicado |

Guias de fabricante citam paredes mínimas de ~0,8–1,0 mm para SLA em geral; o projeto usa números mais conservadores porque o caso de uso é miniatura decorativa/manipulada.

**O que a malha do pipeline oficial realmente contém:** o refino TripoSF 512 reconstrói a superfície a partir de um grid de 512³ — o passo implícito é aproximadamente a maior dimensão da peça dividida por 512 (≈ 0,39 mm numa peça de 200 mm; ≈ 0,20 mm numa de 100 mm). É o degrau de silhueta registrado como inerente no PROGRESS (C5). Consequência: microdetalhe sub-0,4 mm não existe na malha atual; aproximar o zoom revela a quantização do grid, não falta de filtro. Mais resolução hoje = TripoSF 1024³, medido a 10.057 MiB — **BLOQUEADO pelo guard de 10.000 MiB** (perfil rtx3060-12gb).

**O que quebra a impressão não é a densidade de faces — são as consequências geométricas:**
- pontas finas (dedos, espinhos) viram ilhas isoladas por camada → precisam de suporte;
- saliências < 0,5 mm de espessura se soltam no pós-cura;
- cavidades fechadas viram armadilha de resina → risco de rachar/explodir na pós-cura;
- planos grandes paralelos à placa geram sucção no peel;
- malha não-watertight fatia errado ou não fatia — **a saída do TripoSF 512 é NÃO-watertight** (8–18 componentes-ilha; winding inconsistente no anubis_a_512 — PROGRESS C5). Reparo antes de tudo, sempre (`stl-e-malhas.md` §5).

Para jogos/animação o microdetalhe nem é desejável na geometria: ele migra para **normal map** (baking a partir da malha densa). A mesma peça densa serve aos dois destinos — muda a última milha da esteira.

## 2. Ferramentas por etapa (licença e CLI verificadas na fonte, 2026-11-18)

### 2.1 Reparo, hermeticidade e booleana robusta

| Ferramenta | Licença | Execução | Papel |
|---|---|---|---|
| PyMeshFix (em uso) | GPL-3.0 | Python | Primeira passada da Forja (validada na Fase 1) |
| **manifold3d** (elalish/manifold) | Apache-2.0 | Python (PyPI) | Motor de booleana para as ops `boolean_*` do catálogo: o trimesh 5.2.1 do projeto expõe engine `manifold` em `trimesh.boolean` (documentação oficial). Exige malha manifold na entrada (reparo antes); saída manifold garantida. Autor recomenda evitar STL como formato intermediário — trafegar OBJ/3MF internamente; STL só na entrega final |
| **fTetWild** (wildmeshing) | MPL-2.0 | CLI C++ / pytetwild (PyPI) | Reparo pesado de última instância (entrada suja obj/stl/ply; booleanas `--op`/`--csg`); saída tetraédrica `.msh` — extrair superfície |
| ManifoldPlus (hjwdzh) | **Não-comercial** (Stanford) | CLI C++ | Hermeticidade 1-comando (`--depth 8`); dormante ~2020. VEDAR em fluxo com venda de peças; se usado, registrar no `transform_log` do sidecar (ADR-003) |
| PyMeshLab (CNR) | GPL-3.0 | Python (PyPI) | ~300 filtros: booleana exata, **Taubin**, **Hausdorff** (gate de suavização) |

### 2.2 Suavização, remesh, retopologia e decimação

| Ferramenta | Licença | Papel |
|---|---|---|
| Forja atual (`python -m forja repair --smooth N --voxel X --max-tris Y`) | — | Suavização Laplaciana, voxel remesh e decimate já implementados (Blender headless, CPU) |
| **PyMeshLab Taubin** | GPL-3.0 | Suavização com preservação de volume (λ 0,5 / μ −0,53 / 5–10 it. — calibrar no anubis); gate: Hausdorff antes/depois com teto configurável |
| **Instant Meshes** (wjakob) | BSD-3-Clause | Retopo quad-dominante; **CLI confirmada no código-fonte** (`--faces <n>`, `--deterministic` — src/main.cpp); ramal jogos + decimação calibrada |
| QuadWild + requad / Quadify Ultra | GPL-3.0 | Retopo quad de alta qualidade; requad = extensão Blender; Quadify Ultra roda no Blender 5.0 |
| meshoptimizer / gltfpack | MIT | Otimização de GLB para engines (simplify, vertex cache); release ativo 2026-09 |
| xatlas (em uso) | MIT | UV unwrap — já no venv `printer3d-ia` |

Decimação para impressão é contra-intuitiva mas útil: abaixo do passo do grid (~0,2–0,4 mm) as faces só descrevem ruído — malha enxuta fatia mais rápido sem perder detalhe útil. Alvo calibrado pela resolução da impressora (aresta típica ~0,3–0,5 mm na maior dimensão), com gate de Δ bbox/volume < 1%.

### 2.3 Resina: oco, dreno e QC pós-slice

- **Oco + dreno** continua sendo op da Forja (`hollow_drain`, Fase 2 — parede 2–3 mm, furo 2–3 mm no ponto mais baixo; racional em `impressao-resina.md` §2). Referências de algoritmo: BlendShell (MIT, plugin Blender de oco com furos, 2020) e MeshLib (SDK Python com Offset Shell/thickening; **gratuito só para não-comercial**).
- **UVtools** (sn4k3, AGPL-3.0, ativo — v6.0.3/2026): analisa o **ARQUIVO FATIADO** (não a malha) e detecta/repara exatamente as falhas que quebram miniatura: ilhas flutuantes, overhangs sem suporte, armadilhas de resina, copos de sucção. CLI: `UVtoolsCmd print-issues <arquivo-fatiado>` e `convert` (~40 formatos de slicer). Encaixa como **gate objetivo pós-slice**: zero ilhas críticas/armadilhas/sucção = exit 0. Uso correto do AGPL: binário CLI separado no fluxo, sem linkar código no repo.

### 2.4 IA de refinamento de malha (watchlist — espírito do ADR-005)

Todas experimentais; nenhum substitui a esteira determinística hoje:

| Modelo | Licença (verificada) | Limite prático |
|---|---|---|
| MeshAnythingV2 (ICCV 2025) | S-Lab 1.0 (pesquisa) | Teto de 1.600 faces (~300× menor que a saída do pipeline); ~8 GB/45s (A6000); fluxo dos autores passa por serviço em nuvem (Rodin) — contra o local-first |
| EdgeRunner (NVlabs, ICLR 2025) | Custom NVIDIA (NOASSERTION — abrir LICENSE antes de qualquer uso) | ~4.000 faces; sem push desde 2024-12 |
| BPT (Tencent) | Tencent Hunyuan Community | ~12 GB fp16 → guard de 10.000 MiB BLOQUEARIA; pesos "lite" só point-cloud; licença exclui EU/UK/Coreia do Sul |
| Hunyuan3D-2 / Paint (Tencent) | Tencent Hunyuan Community | 6 GB shape / 16 GB shape+textura — textura local é o único gap real do pipeline, mas 16 GB não cabe no guard; README 2.0 (16 GB total) diverge do ~21 GB de textura do 2.1 citado no watchlist do roadmap |

### 2.5 Animação (futuro — Fase 3)

- **RigNet** (SIGGRAPH 2020, GPLv3; addons comunitários Blender): prevê esqueleto + skin a partir da malha; licença comercial exige negociação com a UMass. Uso pessoal local OK; registro no sidecar se usado.
- O caminho canônico continua sendo a Fase 3 (auto-rig bípede próprio, 18 ossos, poses JSON). Retopo quad (2.2) é pré-requisito de skin de qualidade.

## 3. Esteira v1 proposta (decisão no ADR-008)

Entrada: malha final do pipeline oficial (`tools/generator/pipeline_imagem3d.sh`) + sidecar ADR-003. Toda a esteira é **CPU-only** e 100% local. Cada etapa tem gate com número (padrão dos gates do projeto) e appenda o `transform_log`.

| # | Etapa | Ferramenta | Gate objetivo | Estado |
|---|---|---|---|---|
| 1 | Reparo pesado | Forja (`repair`) → fTetWild no fallback | watertight ∧ winding ∧ 0 non-manifold | Existe; fallback novo (Fase 2) |
| 2 | União de componentes | `trimesh.boolean` engine manifold3d + regra dos 2% (já validada na Jubarte B2) | 1 componente conexo (ou lista aprovada pelo dono) | Novo (Fase 2) |
| 3 | Suavização leve | PyMeshLab Taubin | Hausdorff ≤ teto; espessura pct5 não piora | Novo; calibrar no anubis |
| 4 | Decimação p/ impressão | Blender decimate ou Instant Meshes | Δ bbox/volume < 1% | Novo; opcional |
| 5 | Espessura | campo espessura da Forja (raycast, pct5) + Solidify | pct5 ≥ 2,4 mm (aviso) / ≥ 2,0 mm estrutural | Parcial (Solidify é pendência registrada) |
| 6 | Escala mm | `--target-height` (existe) | bbox em mm na faixa configurada | Existe |
| 7 | Oco + dreno | op `hollow_drain` (catálogo §2.1 da arquitetura) | 1+ furo passante ≥ 3 mm; parede ≥ 2 mm | Fase 2 (spec pronta) |
| 8 | Preview + orientação | render da Forja + decisão do dono | PNG canônico | Existe |
| 9 | Slice + QC | slicer do dono → `UVtoolsCmd print-issues` | 0 ilhas críticas / armadilhas / sucção (exit 0) | Novo; gate final |

**Ordem importa:** união (2) antes do oco (7) — oco sobre malha unida evita paredes internas fantasmas; decimação (4) antes do oco — parede interna calculada na geometria final; QC (9) fecha o loop com evidência pós-slice, complementando os gates de malha.

**Ramais por destino:**
- **Jogos** (a partir da etapa 3, antes do oco): Instant Meshes (`--faces` no alvo do engine) → xatlas → bake normal/AO (Blender headless) → gltfpack → GLB;
- **Animação** (futuro): retopo quad (requad/QuadWild) + rig da Fase 3 + poses JSON.

## 4. Fontes (abertas em 2026-11-18 — verificação completa em `evidence/pesquisa-pos-processamento/fontes-verificadas.md`)

- Repos: `github.com/hjwdzh/ManifoldPlus` · `github.com/wildmeshing/fTetWild` (+ `pypi.org/project/pytetwild`) · `github.com/elalish/manifold` (+ `manifold3d` PyPI) · `github.com/cnr-isti-vclab/PyMeshLab` · `github.com/wjakob/instant-meshes` (clonado; LICENSE.txt + src/main.cpp lidos) · `github.com/zeux/meshoptimizer` · `github.com/sn4k3/UVtools` · `github.com/MeshInspector/MeshLib` · `github.com/oormicreations/BlendShell` · `github.com/buaacyw/MeshAnythingV2` · `github.com/NVlabs/EdgeRunner` · `github.com/Tencent-Hunyuan/bpt` · `github.com/Tencent-Hunyuan/Hunyuan3D-2` · `github.com/zhan-xu/RigNet` · `github.com/mlstr0m/requad`
- Docs/refs: `trimesh.org/trimesh.boolean.html` · `pymeshlab.readthedocs.io` · `meshoptimizer.org` · `meshlib.io/documentation` · `formlabs.com/blog/minimum-wall-thickness-3d-printing` · `britmodeller.com` (pixel 12K 0,019–0,024 mm; camada 0,05 mm) · `reddit.com/r/resinprinting` (fluxo comunitário IA→resina) · `tripo3d.ai/blog` (guia watertight)
- Interno: `stl-e-malhas.md` · `impressao-resina.md` · `architecture.md` §2.1/§2.4 · `PROGRESS.md` (C3/C5) · `HANDOFF.md`
