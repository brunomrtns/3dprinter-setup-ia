# STL e Malhas — Manifold, Non-Manifold e Reparo

> Guia técnico para qualquer agente operar malhas 3D neste projeto sem adivinhar.

## 1. O que é uma malha

Malha poligonal = **vértices** + **arestas** + **faces** (triângulos em STL). A topologia (como faces compartilham arestas) é o que distingue uma malha sólida de uma "casca furada".

## 2. Manifold vs Non-Manifold

Uma malha é **manifold** (ou *watertight*, hermética) quando:

- Toda aresta é compartilhada por **exatamente 2 faces**;
- Não há buracos (arestas com só 1 face = borda aberta);
- Não há arestas não-manifold (3+ faces na mesma aresta);
- Não há vértices não-manifold (leques de faces desconectados no mesmo vértice);
- Normais consistentes (sem faces "de dentro para fora" intercaladas).

Por que importa **aqui**: o slicer de resina fatia a malha assumindo que ela delimita um volume fechado. Malha non-manifold produce: fatiamento com falha, camadas furadas, casca sem volume (custo errado no PrintFlow3D) e resina presa no interior.

Casos separados:
- **Non-manifold** = topologia quebrada (o gate principal do pipeline);
- **Autointerseção** = topologia pode estar "fechada" mas a superfície se atravessa (booleanas falham silenciosamente; impressão sai com artefatos). O reparo padrão do pipeline resolve ambas via voxel remesh.

## 3. Por que IA generativa entrega malha quebrada (quase sempre)

Geradores image→3D (TripoSR, TRELLIS etc.) não modelam topologia — eles **implícitam uma superfície** (SDF/occupancy) e extraem a casca com marching cubes. Consequências típicas:

- **Casca não hermética**: buracos na base ou em regiões de baixa confiança;
- **Componentes flutuantes** ("floaters"): fragmentos desconectados ao redor do objeto;
- **Paredes de 1 face**: detalhes mais finos que a resolução do grid viram lâminas sem espessura;
- **Densidade irregular**: triângulos gigantes ao lado de micro-triângulos;
- **Normais invertidas** em bolsões internos;
- **Autointerseções** em partes finas (dedos, orelhas, antenas).

Por isso o pipeline comum aplica **REPARO obrigatório** em TODO output de gerador antes de qualquer operação (ADR-001): o gerador nunca entrega direto pro slicer.

## 4. STL: o formato que esconde erros

STL **não tem topologia** — cada triângulo é um registro independente (3 vértices + normal). Qualquer malha, por mais quebrada, "salva" em STL sem erro. Os problemas só aparecem no slicer. OBJ/FBX/GLB carregam topologia e materiais; use STL só como formato de entrega final pro slicer.

**STL não tem unidade** (`unitless`): o número é interpretado como mm por convenção dos slicers. Ver `impressao-resina.md` §5 e o gate de dimensões em mm.

## 5. Reparo padrão do pipeline (ordem canônica)

1. **Delete loose**: descarta faces/vértices/arestas soltas e componentes minúsculos (floaters);
2. **Merge by distance**: solda vértices duplicados (tolerância pequena, ex. 0.0001 da escala do modelo);
3. **Fill holes**: fecha bordas abertas;
4. **Recalc normals**: orienta todas as faces para fora;
5. **Voxel remesh**: quando os passos acima não bastam, re-voxeliza (ex. 0.5–1% do tamanho do objeto) e reconstrói a casca — resolve autointerseções e topologia patológica de uma vez, ao custo de suavizar detalhes finos;
6. **Boolean union**: quando o asset tem múltiplos sólitos que precisam virar UM sólido (ex. peça gerada acoplada à base pela Forja).

## 6. Como validar (gates objetivos do `tools/validation/`)

Contagem verificável, nunca "parece fechado":

- **Blender (3D-Print Toolbox, headless)**: `non_manifold_edges == 0`, `non_manifold_verts == 0`, `loose_verts == 0`, bordas abertas = 0;
- **trimesh (venv do projeto)**: `mesh.is_watertight == True` e `mesh.is_winding_consistent == True`;
- **Volume finito e positivo**: bounding box + volume coerentes com o esperado em mm;
- **Exit code** do validador = 0 → passa o gate; qualquer número acima do limiar → falha com o número no log.

Referências internas: `docs/architecture.md` §2.4 (gates do pipeline) · `blender-headless.md` (como rodar esses checks em script).
