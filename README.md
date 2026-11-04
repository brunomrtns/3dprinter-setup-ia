# 3dprinter-setup-ia

![Fase](https://img.shields.io/badge/FASE-0%20%E2%80%94%20Funda%C3%A7%C3%A3o%20e%20Documenta%C3%A7%C3%A3o-blue)
![Ambiente](https://img.shields.io/badge/ambiente-100%25%20local%20%2B%20WSL2-informational)

Sistema **local**, operado por **agentes de IA**, para modificar modelos 3D prontos (STL/OBJ/FBX) e prepará-los para **impressão 3D em resina (SLA/MSLA)** — com entrega automática no painel [PrintFlow3D](https://github.com/brunomrtns/printflow3d) via API REST.

**Dono:** Bruno · **Hardware:** Windows 11 + WSL2 Ubuntu · RTX 3060 12GB · 64GB RAM · Impressora MSLA (resina)

---

## Objetivo

Pegar modelos 3D prontos de terceiros (origem variada) e **modificá-los localmente**:

- **Reparar e validar** malha (manifold, espessura mínima, escala em mm, volume);
- **Aplicar operações determinísticas**: booleanas (cortar/furar/acoplar), oco com furo de dreno, remesh/decimate, mirror/symmetrize, escala, deformações (twist, entalhe, desgaste);
- **Gerar peças novas** por IA generativa local image→3D e acoplá-las ao modelo base;
- **Rigar e posar** personagens humanoides (auto-rig bípede + biblioteca de poses JSON) exportando STL estático na pose;
- **Entregar** o resultado no PrintFlow3D (`POST /api/models/upload` ou `PUT /api/models/{id}/file`), que recalcula volume/custo.

## Por que 100% local

Os modelos de origem são de terceiros, com licenças variadas. Nada sai da máquina: sem upload para nuvem, sem API paga, sem telemetria. Em contrapartida, **procedência é obrigatória**: todo asset que entra no sistema registra origem (URL/autor), licença e log de transformações — o PrintFlow3D não captura esses campos (gap conhecido, ver `docs/knowledge/licencas-e-procedencia.md`).

## Arquitetura (resumo)

3 módulos + 1 pipeline comum — detalhes e contratos em [`docs/architecture.md`](docs/architecture.md):

| Módulo | O que faz | Motor |
|---|---|---|
| **Forja de Modificação** | Catálogo de operações determinísticas de malha | Blender headless (WSL) |
| **Gerador de Peças** | IA generativa local image→3D, multi-modo (plugins) | TRELLIS (plano) · TripoSR (legado) |
| **Estúdio de Pose** | Auto-rig bípede (18 ossos) + biblioteca de poses JSON | Blender headless + numpy |

Todo resultado, de qualquer módulo, passa pelo **pipeline comum**: `entrada → REPARO → OPERAÇÕES → VALIDAÇÃO (gates objetivos) → PREVIEW RENDER → entrega no PrintFlow3D`.

## Stack prevista (instalada a partir da Fase 1)

| Camada | Tecnologia |
|---|---|
| Host / GPU | Windows 11 + WSL2 Ubuntu 26.04 · RTX 3060 12GB (CUDA via driver Windows) |
| Automação 3D | Blender 5.0.1 headless (`bpy`) — já presente no WSL |
| IA generativa | TRELLIS (MIT, modo principal planejado) · TripoSR (legado, já funcional) |
| Runtime Python | venv próprio `/home/bruno/.venvs/printer3d-ia` (isolado do `game-ai3d`) |
| Entrega | PrintFlow3D — API REST local |

## Estrutura de pastas

```text
3dprinter-setup-ia/
├── AGENTS.md                  # Contrato canônico para qualquer agente de IA
├── PROGRESS.md                # Checklist vivo — pontapé de qualquer sessão
├── HANDOFF.md                 # Retomada por qualquer agente
├── README.md
├── docs/
│   ├── architecture.md        # Módulos, pipeline, contratos, guard de VRAM
│   ├── roadmap.md             # Fases com critérios de aceite objetivos
│   ├── decisions/             # ADRs (decisões de arquitetura)
│   ├── knowledge/             # Base técnica (STL/malhas, resina, blender, WSL/GPU, licenças)
│   └── operations/            # Auditorias de ambiente com outputs reais
├── tools/                     # Ferramentas (SEM código na Fase 0)
│   ├── forja/                 # Fase 2: ops bpy determinísticas
│   ├── generator/             # Fase 1: plugins TRELLIS/TripoSR
│   ├── pose/                  # Fase 3: auto-rig + biblioteca de poses
│   └── validation/            # Gates objetivos do pipeline comum
└── evidence/                  # Evidências de validação (logs, resultados, capturas)
```

## Comandos canônicos

> Placeholders — definidos e validados nas fases 1–3. Não instalar nada na Fase 0.

```bash
# Blender headless (WSL) — padrão de toda op da Forja (Fase 2)
wsl blender -b -P tools/forja/<op>.py -- --input <arquivo> --output <arquivo>

# Python do venv do projeto (Fase 1)
wsl /home/bruno/.venvs/printer3d-ia/bin/python <script.py> <args>

# Benchmark de geradores image→3D (Fase 1)
wsl /home/bruno/.venvs/printer3d-ia/bin/python tools/generator/benchmark.py   # a criar

# Guard de VRAM antes de job pesado
wsl nvidia-smi --query-gpu=memory.free,memory.total --format=csv
```

## Governança (leia antes de operar)

- [`AGENTS.md`](AGENTS.md) — contrato vinculante, agnóstico a agente (o dono alterna OpenCode/Claude/Antigravity).
- [`PROGRESS.md`](PROGRESS.md) — estado real do projeto; legenda `[x]` feito · `[~]` em andamento · `[ ]` pendente · `[!]` bloqueado.
- [`docs/roadmap.md`](docs/roadmap.md) — **uma fase por vez**; instalar pesos/modelos de IA só na fase que manda.
- Regra crítica: **commit sem push é falha**.

## Estado atual

**Fase 0 — Fundação e Documentação** concluída tecnicamente (ver [`PROGRESS.md`](PROGRESS.md)), aguardando aprovação do dono para liberar a Fase 1 (venv isolado + TRELLIS + benchmark TripoSR vs TRELLIS).
