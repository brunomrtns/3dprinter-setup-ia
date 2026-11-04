# Roadmap — 3dprinter-setup-ia

> Regra vinculante (AGENTS.md §1.8): **uma fase por vez**. Não instalar dependências/pesos nem escrever código de fase futura. Cada fase só abre após os critérios de aceite da anterior estarem `[x]` e o dono aprovar.

Legenda: `[x]` concluído · `[~]` em andamento · `[ ]` pendente · `[!]` bloqueado/pendência

---

## Fase 0 — Fundação e Documentação `[x] concluída — aprovada pelo dono em 2026-11-04`

**Objetivo:** governança, documentação e auditoria de ambiente. Sem instalação de IA, sem código de pipeline.

Critérios de aceite:
- [x] Repo init: clone, `.gitignore`, identidade git configurada, push inicial no remote
- [x] `README.md` (visão, stack prevista, estrutura, comandos canônicos, badge de fase)
- [x] `AGENTS.md` (contrato vinculante, agnóstico a agente)
- [x] `docs/architecture.md` (3 módulos + pipeline comum + contratos + guard de VRAM + integração PrintFlow3D)
- [x] `docs/roadmap.md` (este arquivo)
- [x] `docs/knowledge/` — 5 guias técnicos (stl-e-malhas, impressao-resina, blender-headless, wsl-gpu, licencas-e-procedencia)
- [x] `docs/decisions/` — ADR-001 a ADR-004
- [x] `docs/operations/environment-audit.md` com **outputs reais** dos comandos de auditoria
- [x] Skeleton de pastas `tools/forja|generator|pose|validation` + `evidence/` (sem código)
- [x] `PROGRESS.md` + `HANDOFF.md` refletindo estado real
- [x] Todos os commits pushed (`git log origin/main..HEAD` vazio)
- [x] **Aprovação do dono (👍)** — gate de abertura da Fase 1 · concedida em conversa, 2026-11-04

---

## Fase 1 — Gerador de Peças: venv isolado + TRELLIS + benchmark comparativo `(ESTA — [~] em andamento)`

**Objetivo:** colocar o gerador image→3D multi-modo de pé e escolher o modo default com **dados objetivos**, não impressão.

Escopo:
1. Criar venv próprio `/home/bruno/.venvs/printer3d-ia` no WSL (**isolado** do `game-ai3d` — ADR-004). Nada é instalado no venv de games.
2. Instalar TRELLIS no WSL (Microsoft, MIT; pesos ~13 GB; CUDA na RTX 3060 12GB; 1024³, ~90s/modelo esperado). Registrar procedimento de instalação + evidências.
3. Garantir que o modo legado TripoSR continua funcionando (referência funcional existente).
4. Definir a interface de plugin comum (`generate(image, output, params) -> GenerationReport`) e implementar os dois plugins.
5. **Benchmark automático de 10 casos fixos**: mesmas 10 imagens de entrada em ambos os modos, mesmos gates.
6. **Scoring OBJETIVO automatizado** por caso: `manifold?` (sim/não pós-reparo leve), `espessura mínima ok?`, `tempo (s)`, `VRAM pico (MiB)`, `contagem de vértices` — tabela gerada sem intervenção manual.
7. **Galeria de previews** renderizados (mesmo ângulo/luz para todos) para inspeção visual do dono.
8. Guard de VRAM operacional (`nvidia-smi` query + fila serial) medindo `vram_pico_mib` por job.

Critérios de aceite:
- [ ] venv `printer3d-ia` criado e funcional no WSL; `game-ai3d` intocado (verificar e evidenciar)
- [ ] TRELLIS gera ao menos 1 modelo de ponta a ponta na 3060 local
- [ ] Script de benchmark roda os 10 casos nos 2 modos sem intervenção manual
- [ ] Tabela de scores gerada automaticamente (JSON + Markdown em `evidence/`)
- [ ] Galeria de previews commitada/presente para o dono avaliar
- [ ] Dono aprova por caso (👍/👎) e escolhe o **default mode** → registrado em ADR novo (ADR-005+)

---

## Fase 2 — Forja de Modificação

**Objetivo:** catálogo de operações determinísticas Blender headless, testadas UMA A UMA.

Escopo: cada op do catálogo de `docs/architecture.md` §2.1 vira script `tools/forja/<op>.py` + caso de teste fixo + **validador por op** (gate objetivo: ex. após `hollow_drain`, verificar 1+ furo passante e parede ≥ alvo; após `boolean_attach`, verificar 1 componente conexo).

Critérios de aceite:
- [ ] 100% do catálogo com script + validador + evidência individual em `evidence/`
- [ ] Pipeline comum (reparo → operações → validação) roda ponta a ponta em um caso real
- [ ] DoD por op cumprido (validador exit 0 + evidência + PROGRESS atualizado)

---

## Fase 3 — Estúdio de Pose

**Objetivo:** rigar e posar humanoides localmente, exportando STL estático pronto pro slicer.

Escopo: port do `auto_rig.py` (18 ossos, skinning por proximidade com particionamento anatômico, detecção de anatomia por numpy) para `tools/pose/`; biblioteca de poses JSON versionada (presets: idle, andando, correndo, combate, sentado, …); integração ao pipeline comum (pose → reparo → validação → preview).

Critérios de aceite:
- [ ] Auto-rig aplica esqueleto em malhas de teste humanoides sem erro
- [ ] ≥ 5 presets de pose aplicados e exportados como STL válido nos gates
- [ ] Mesma malha + mesmo preset → resultado reproduzível (determinismo verificado)

---

## Fase 4 — Operador IA + entrega automática

**Objetivo:** pedido em PT-BR → asset entregue no PrintFlow3D sem intervenção manual.

Escopo: agente orquestrador que recebe pedido em linguagem natural (ex.: "fura essa base em M4 e deixa oco com dreno") → monta sequência de ops da Forja/Gerador/Pose → executa pipeline comum → entrega via `POST /api/models/upload` ou `PUT /api/models/{id}/file`; respeita guard de VRAM e fila serial. UI própria **só se houver dor real** (ADR-002) — o painel do dono já é a UI.

Critérios de aceite:
- [ ] Pedido natural → sequência de ops correta em N casos de teste
- [ ] Entrega automática no PrintFlow3D com sidecar de procedência preservado
- [ ] Falhas de VRAM/validação tratadas sem corromper estado (fila + aviso)
