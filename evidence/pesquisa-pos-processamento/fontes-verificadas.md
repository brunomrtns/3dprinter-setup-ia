# Fontes verificadas — pesquisa de pós-processamento (2026-11-18)

> Log de auditoria real (AGENTS.md §1.5): cada ferramenta citada em `docs/knowledge/pos-processamento-ferramentas.md` e no ADR-008 foi verificada na fonte primária nesta data. Nada citado de memória.

## Método

1. **Levantamento**: busca em GitHub, documentação oficial e fóruns (Reddit r/resinprinting, Blender Artists, Britmodeller, devtalk.blender.org);
2. **Verificação primária**: leitura do README de cada candidato; leitura do arquivo de licença via `raw.githubusercontent.com` quando a página não exibia o tipo; consulta à API pública do GitHub (estrelas, último push, archived — 3 consultas OK antes do rate limit anônimo de 60/h se esgotar; demais repos verificados por fetch das páginas); **Instant Meshes**: repo clonado (`git clone --depth 1`) e código-fonte lido para confirmar CLI.

## Repos — o que foi verificado e como

| Repo | Verificado | Método | Resultado |
|---|---|---|---|
| `hjwdzh/ManifoldPlus` | Licença + CLI | README/LICENSE | "© 2020 Jingwei Huang, Stanford — This software is distributed for free for non-commercial use only." CLI: `./ManifoldPlus --input input.obj --output output.obj --depth 8`; entrada triangle soup OBJ/OFF → saída OBJ watertight; dormante (~27 commits, 2020) |
| `wildmeshing/fTetWild` | Licença + CLI + atividade | README + API GitHub | MPL-2.0 (LICENSE.MPL2); 615 estrelas, último push **2026-09-23**; entrada `.off/.obj/.stl/.ply`; booleanas `--op INT` (0 union / 1 intersection / 2 difference) + `--csg` JSON; saída `.msh` tetraédrica (sem flag documentada de superfície-only) |
| `elalish/manifold` | Licença + bindings + adoção | README + LICENSE | Apache-2.0; bindings Python `manifold3d` (PyPI); "you need manifold meshes as input" (booleana não definida p/ non-manifold; `Merge` conserta casos leves); adoção citada: Blender, OpenSCAD, trimesh, Godot, Nomad Sculpt; autor: "Please avoid saving to STL files!" |
| `trimesh.boolean` (docs) | Engine Manifold no trimesh do projeto | `trimesh.org/trimesh.boolean.html` (trimesh **5.2.1** = versão do venv) | "Run an operation on a set of meshes using the Manifold engine" |
| `cnr-isti-vclab/PyMeshLab` | Licença + filtros | raw LICENSE + docs | "GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007"; filtros Taubin Smooth, Mesh Boolean: Difference (exata), métrica Hausdorff; Python 3.12 suportado |
| `wjakob/instant-meshes` | Licença + **CLI** | **clonado e lido** (`--depth 1`) | LICENSE.txt: BSD-3 (Copyright 2015 Wenzel Jakob, Daniele Panozzo, Marco Tarini, Olga Sorkine-Hornung); `src/main.cpp` linhas 43/93 (`--deterministic`, `--faces`) e help nas linhas 152/161 ("Desired face count of the output mesh") |
| `zeux/meshoptimizer` (+gltfpack) | Licença + atividade | site oficial + releases | MIT ("permissively licensed under MIT"); gltfpack CLI; release 2026-09-25 |
| `sn4k3/UVtools` | Licença + CLI + atividade | README | AGPL-3.0; v6.0.3 (2026), ~1,7 mil estrelas, 1.506 commits; Windows 10+/Linux/macOS 13+; `UVtoolsCmd print-issues`/`convert`; detecção/reparo de ilhas, overhangs, resin traps, suction cups, touching bounds; ~40 formatos de slicer |
| `MeshInspector/MeshLib` | Licença | site oficial | "Free For Educational Use, Free for non-commercial use" + licença comercial paga; Offset Shell/hollowing/thickening |
| `oormicreations/BlendShell` | Licença + atividade | API GitHub | MIT; 47 estrelas; último push 2020-11-24 (referência de algoritmo, não dependência ativa) |
| `buaacyw/MeshAnythingV2` | Licença + limites | raw LICENSE.txt + README | LICENSE.txt: "S-Lab License 1.0 / Copyright 2023 S-Lab"; teto duro 1.600 faces; ~8 GB e 45s em A6000; entrada malha densa (MC 128/256) ou point cloud (N,6); experimental |
| `NVlabs/EdgeRunner` | Licença + atividade | API GitHub | licença **NOASSERTION** (custom NVIDIA); 316 estrelas; último push **2024-12-22**; LICENSE.txt vazio via raw nos caminhos testados — **a abrir antes de qualquer uso** |
| `Tencent-Hunyuan/bpt` | Licença + requisitos | raw License + README | "TENCENT HUNYUAN 3D 2.0 COMMUNITY LICENSE AGREEMENT ... DOES NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA"; ~12 GB VRAM fp16; >8k faces; ~2 min/malha; pesos "lite" (point cloud) no HF |
| `Tencent-Hunyuan/Hunyuan3D-2` | Licença + VRAM | raw LICENSE + README | Mesma Community License; "6 GB VRAM for shape generation and 16 GB for shape and texture generation in total"; 2.1: 10 GB shape / 21 GB textura (divergência com watchlist do roadmap registrada) |
| `zhan-xu/RigNet` | Licença | página do repo | GPLv3 (SIGGRAPH 2020); licença comercial via UMass TTO; addons comunitários Blender (V-Sekai, brignet) |
| `mlstr0m/requad` | Licença | página do repo | GPL-3.0 ("powered by QuadWild bi-MDF"); Quadify Ultra (comunidade) roda no Blender 5.0 |

## Fóruns / guias (contexto de uso)

- `formlabs.com/blog/minimum-wall-thickness-3d-printing` — paredes mínimas SLA ~0,8–1,0 mm (guias de fabricante);
- `britmodeller.com` (fórum, 2026-08) — tela 12K: pixel 0,019–0,024 mm; camada default 0,05 mm;
- `reddit.com/r/resinprinting`, `r/3Dprinting` — fluxo comunitário IA→resina: gerar → reparar/watertight → slicer (escala/rotação/suportes) → UVtools (QC) → imprimir;
- `tripo3d.ai/blog` — guia de watertight para modelos gerados por IA (contexto de problema, não dependência).

## Dados internos citados

- `PROGRESS.md` C5 (2026-11-17): TripoSF 512 não-watertight, 8–18 componentes-ilha, winding inconsistente (anubis_a_512), ~616–631k faces, pico 7,2–7,5 GB; 1024³ bloqueado a 10.057 MiB; pipeline oficial decidido pelo dono;
- `docs/knowledge/impressao-resina.md` §3: parede oca 2,0 mm / relevo 0,5 mm / pino 1,5–2,0 mm / estrutural ≥ 2,0 mm;
- `docs/architecture.md` §2.1: catálogo de ops da Forja (boolean_*, hollow_drain, etc.);
- Jubarte B2: regra dos 2% validada; campo espessura pct5 com aviso < 2,4 mm.

## Limitações registradas (honestidade §1.5)

- Rate limit da API anônima do GitHub (60/h) esgotou durante a verificação em lote — fTetWild, EdgeRunner e BlendShell retornaram dados de API; os demais repos foram verificados por fetch das páginas/README/raw (estrelas/datas exatas não capturadas para todos);
- EdgeRunner: tipo exato da licença não confirmado (LICENSE.txt vazio no raw nos caminhos testados) — tratado como restritivo até leitura do arquivo;
- Medidas de VRAM/tempo dos modelos IA (MeshAnythingV2 ~8 GB/45s; BPT ~12 GB; Hunyuan3D 6/16 GB) vêm dos READMEs oficiais — não reproduzidas localmente (pesos não instalados — regra de uma fase por vez).
