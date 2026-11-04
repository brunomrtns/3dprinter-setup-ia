# Arquitetura — 3dprinter-setup-ia

> Status: aprovada na Fase 0 · Decisões estruturais em `docs/decisions/` (ADR-001..004)

## 1. Visão Geral

Três módulos produtivos + um pipeline comum obrigatório. Todo resultado — não importa a origem — passa pelos mesmos gates objetivos antes de sair do sistema.

```text
                          ┌────────────────────────────────────────────────┐
                          │              ENTRADA DE ASSETS                 │
                          │   STL / OBJ / FBX  +  SIDECAR DE PROCEDÊNCIA   │
                          │   (origem, autor, licença, triage 🟢🟡🔴, hash) │
                          └───────────────────────┬────────────────────────┘
                                                  │
              ┌───────────────────────────────────┼───────────────────────────────────┐
              ▼                                   ▼                                   ▼
 ┌──────────────────────────┐     ┌─────────────────────────────┐     ┌──────────────────────────────┐
 │   FORJA DE MODIFICAÇÃO   │     │     GERADOR DE PEÇAS        │     │      ESTÚDIO DE POSE         │
 │   (determinístico)       │     │     (IA local, multi-modo)  │     │   (auto-rig + poses JSON)    │
 │                          │     │                             │     │                              │
 │ Blender headless (WSL):  │     │ image →3D via plugins:      │     │ auto_rig (port do gamedev):  │
 │ · reparo de malha        │     │ ┌─────────────────────────┐ │     │ · esqueleto bípede 18 ossos  │
 │ · booleanas              │     │ │ TRELLIS (MIT, plano)    │ │     │ · skinning por proximidade   │
 │   (cortar/furar/acoplar) │     │ ├─────────────────────────┤ │     │   c/ particionamento         │
 │ · oco + furo de dreno    │     │ │ TripoSR (legado)        │ │     │   anatômico (numpy)          │
 │ · espessura mínima       │     │ ├─────────────────────────┤ │     │ · biblioteca de poses JSON   │
 │ · remesh / decimate      │     │ │ slot futuro             │ │     │   (idle/andando/combate/...) │
 │ · mirror / symmetrize    │     │ └─────────────────────────┘ │     │ · rotação de ossos =         │
 │ · escala (mm)            │     │                             │     │   determinístico             │
 │ · deformações (twist,    │     │ Peças NOVAS avulsas que    │     │ · exporta STL ESTÁTICO       │
 │   entalhe, desgaste)     │     │ depois são ACOPPLADAS      │     │   NA POSE, pronto pro slicer │
 │                          │     │ pela Forja (booleana)      │     │                              │
 └────────────┬─────────────┘     └──────────────┬──────────────┘     └──────────────┬───────────────┘
              │                                  │                                   │
              └──────────────────────────────────┼───────────────────────────────────┘
                                                 ▼
                   ┌──────────────────────────────────────────────────────────────┐
                   │                     PIPELINE COMUM (obrigatório)             │
                   │                                                              │
                   │  entrada → REPARO (manifold) → OPERAÇÕES (Forja/Pose) →      │
                   │  VALIDAÇÃO (gates objetivos: manifold ok, espessura mínima,  │
                   │  dimensões em mm, volume) → PREVIEW RENDER → ENTREGA         │
                   └──────────────────────────────┬───────────────────────────────┘
                                                  ▼
                                   ┌───────────────────────────────┐
                                   │   PrintFlow3D (API REST)      │
                                   │   POST /api/models/upload     │
                                   │   PUT  /api/models/{id}/file  │
                                   └───────────────────────────────┘
```

## 2. Contratos de Interface entre Módulos

Regra geral: **todo artefato que atravessa uma fronteira de módulo carrega malha + sidecar de procedência** (ADR-003). Formato do sidecar (JSON, ao lado do arquivo de malha):

```json
{
  "id": "uuid4",
  "source": {
    "url": "https://... ou 'gerado-localmente'",
    "author": "nome ou desconhecido",
    "license": "CC-BY-4.0 | CC0 | personal-use | desconhecida",
    "triage": "verde | amarelo | vermelho",
    "retrieved_at": "2026-11-03"
  },
  "hash_original": "sha256:...",
  "transform_log": [
    { "op": "repair.manifold", "tool": "blender-5.0.1", "params": {}, "ts": "..." },
    { "op": "forge.hollow", "params": { "wall_mm": 2.0, "drain_hole_mm": 3.0 }, "ts": "..." }
  ],
  "units": "mm",
  "generator": null
}
```

### 2.1 Forja de Modificação

| | Contrato |
|---|---|
| **Entrada** | Malha (STL/OBJ/FBX) + sidecar. Params por operação (ex.: `wall_mm`, `drain_hole_mm`, `target_height_mm`). |
| **Saída** | Malha transformada (STL/OBJ) + sidecar com `transform_log` appendado + relatório da op (exit code + métricas). |
| **Execução** | `wsl blender -b -P tools/forja/<op>.py -- --input X --output Y [params]` — determinística, sem UI. |
| **Catálogo** | `repair` · `boolean_cut` · `boolean_hole` · `boolean_attach` · `hollow_drain` · `min_thickness` · `remesh` · `decimate` · `mirror_symmetrize` · `scale_mm` · `deform_twist` · `deform_notch` · `deform_wear` (referência de espírito: `damage_vehicle.py` do gamedev-setup-ia) |

### 2.2 Gerador de Peças (multi-modo)

| | Contrato |
|---|---|
| **Entrada** | Imagem de referência (PNG/JPG) + params (resolução de voxels, seed, modo). |
| **Saída** | Peça NOVA avulsa (OBJ/GLB) + sidecar com `generator = { "mode": "trellis|triposr|...", "model_version": "...", "tempo_s": ..., "vram_pico_mib": ... }`. |
| **Interface de plugin** | Cada modo expõe a MESMA assinatura: `generate(image_path, output_path, params) -> GenerationReport`. Adicionar modo = implementar a interface; nada mais muda (ADR-001). |
| **Pós-geração** | A peça gerada NÃO vai direto ao slicer: entra no pipeline comum (reparo obrigatório — malha de IA generativa vem quebrada, ver `docs/knowledge/stl-e-malhas.md`) e é acoplada ao modelo base pela Forja. |

### 2.3 Estúdio de Pose

| | Contrato |
|---|---|
| **Entrada** | Malha humanoide (OBJ/FBX) + pose (nome de preset JSON ou rotações explícitas por osso). |
| **Saída** | STL **estático na pose** (esqueleto descartado na exportação) + sidecar com `pose_preset` aplicado. |
| **Motor** | Port de `tools/art/auto_rig.py` (gamedev-setup-ia): 18 ossos bípedes, skinning por proximidade com particionamento anatômico, detecção de anatomia via numpy. |
| **Biblioteca de poses** | JSON versionado em `tools/pose/poses/`: cada preset mapeia osso → rotação (euler, rad). Rotação de ossos é determinística — mesma pose + mesma malha = mesmo resultado. |

### 2.4 Pipeline Comum (gates objetivos)

| Etapa | Gate (exit code verificável) |
|---|---|
| REPARO | arestas/vértices non-manifold = 0; casca watertight |
| OPERAÇÕES | op executou sem erro do Blender; bounding box dentro do esperado |
| VALIDAÇÃO | manifold ok · espessura mínima ≥ X mm (ray casting) · dimensões em mm dentro de faixa configurada · volume calculado |
| PREVIEW RENDER | PNG gerado headless (ângulo canônico + iluminação padronizada) |
| ENTREGA | PrintFlow3D respondeu 2xx com id do modelo |

## 3. Padrão de Job Assíncrono

Referência: `mesh_service.py` do PrintFlow3D (thread + status + `update_db`). Aqui o padrão é o mesmo, com uma restrição extra:

- Todo job pesado tem registro com estados `queued → running → succeeded | failed`;
- **Fila ÚNICA e SERIAL para jobs de GPU** — nunca dois jobs GPU simultâneos (ADR-001, §4 do AGENTS.md). Jobs CPU (Blender leve, render software) podem paralelizar entre si, à exceção deoperações sobre o mesmo arquivo;
- O orquestrador (Fase 4) despacha o job GPU do topo da fila somente após o guard de VRAM aprovar.

## 4. Guard de VRAM (requisito de design)

A GPU é compartilhada Windows↔WSL (mesma VRAM física — o WSL enxerga a 3060 inteira, e o desktop Windows disputa os mesmos 12GB; ver `docs/knowledge/wsl-gpu.md`). Auditoria real de 2026-11-03: **1258 MiB já em uso** com o desktop em repouso (Chrome, overlays NVIDIA, OpenCode).

Comando do guard (antes de cada job GPU):

```bash
wsl nvidia-smi --query-gpu=memory.free,memory.total --format=csv
# exemplo real: 10853 MiB, 12288 MiB, 1258 MiB
```

Comportamento:
1. `memory.free` ≥ requisito do job (ex.: TRELLIS 1024³ — valor medido na Fase 1) → despacha;
2. `memory.free` < requisito → job permanece `queued`; sistema avisa o dono (sugestão futura: toast do Windows) e/ou aguarda polling;
3. Durante o job: sampling de `memory.used` para registrar `vram_pico_mib` (métrica do benchmark da Fase 1).

## 5. Deformação / Dano (referência)

O catálogo de deformações da Forja segue o espírito do `damage_vehicle.py` (gamedev-setup-ia): amassados e desgaste aplicados sobre malha PRONTA de forma paramétrica (intensidade, região, seed) — sem regenerar a malha. Twist/entalhe/desgaste entram como ops `deform_*` com validador geométrico próprio.

## 6. Integração PrintFlow3D (endpoints reais, verificados)

| Endpoint | Uso neste projeto |
|---|---|
| `POST /api/models/upload` (multipart: `file`, `folderId`, `tags`) | Publicar resultado novo no painel |
| `PUT /api/models/{id}/file` | Substituir arquivo de um modelo existente — o PrintFlow3D reprocessa volume/custo automaticamente |
| `GET /api/models` | Consultar catálogo (ex.: checar duplicidade antes do upload) |
| `GET /api/folders` | Estrutura de pastas do painel |

**Gap conhecido e desejado que seja permanente aqui:** os importadores do PrintFlow3D NÃO capturam licença/autor. Este projeto é a **fonte da verdade de procedência**: o sidecar local registra origem, licença, triage e o log completo de transformações. A triage pode viajar nas `tags` do upload como metadado auxiliar, mas o registro canônico é local (ADR-003).
