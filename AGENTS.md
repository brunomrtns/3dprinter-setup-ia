# AGENTS.md — Contrato Canônico de Operação dos Agentes

Este documento é a autoridade central e **vinculante** para qualquer agente de IA (OpenCode, Claude Code, Antigravity, etc.) operando neste repositório. O dono (Bruno) **alterna entre agentes** — nenhum estado, decisão ou contexto pode depender de qual agente está no comando.

---

## 1. Princípios Não-Negociáveis

1. **Agnóstico ao agente.** Todos os agentes leem os mesmos docs (`docs/`), usam os mesmos comandos canônicos e persistem estado exclusivamente em `PROGRESS.md` e `HANDOFF.md`. Memória de sessão/conversa **não é fonte de verdade**.
2. **Estado vive em arquivos, NUNCA na conversa.** Se não está em arquivo no repo, não existe. Toda sessão começa lendo `PROGRESS.md` e termina atualizando-o.
3. **Documentação antes de código.** Nenhuma funcionalidade é implementada sem estar descrita no `docs/roadmap.md` (fase + critérios de aceite) e, quando houver decisão estrutural, em um ADR (`docs/decisions/`).
4. **"Código que roda" ≠ concluído.** Concluído (`[x]`) exige: validação determinística executada + evidência real salva em `evidence/` + `PROGRESS.md` atualizado. Demonstração visual não substitui gate objetivo.
5. **Auditoria é real.** Proibido inventar output de comando, versão, medida ou número. O que falhar é registrado como pendência `[!]` com o erro real, causa provável e o que será preciso para resolver — e a sessão segue adiante.
6. **Ambiente dual Windows + WSL.** O host é Windows 11; a carga pesada (Blender/bpy, CUDA, IA generativa) roda **exclusivamente no WSL2 Ubuntu**. Padrão de invocação: `wsl blender -b -P <script.py> -- <args>` e `wsl /home/bruno/.venvs/printer3d-ia/bin/python <script.py>`. Caminhos Windows→WSL: `C:\foo` → `/mnt/c/foo` (helper `convert_to_wsl_path()` quando houver tooling, padrão do projeto gamedev-setup-ia).
7. **PROIBIDO commit sem push.** Cada marco concluído = commit convencional + `git push` imediato no remote. Ao final de qualquer etapa: `git status` limpo + `git log origin/main..HEAD` vazio. Commit só-local é **falha de sessão**.
8. **Uma fase por vez.** Não instalar dependências, pesos de IA ou escrever código fora do escopo da fase corrente do `docs/roadmap.md` (ex.: TRELLIS/torch só na Fase 1; código de pipeline não existe na Fase 0).
9. **GPU é recurso compartilhado e serializado.** A RTX 3060 12GB é disputada entre Windows (desktop, navegador, overlays) e WSL. Antes de qualquer job pesado: guard de VRAM (`nvidia-smi --query-gpu=memory.free --format=csv`). Jobs de GPU **nunca** rodam em paralelo entre si — fila serial única (ver `docs/architecture.md`).
10. **Local-first + procedência obrigatória.** Nenhum arquivo de terceiro sai da máquina. Todo asset que entra no sistema ganha sidecar de procedência (origem/autor/licença/triage) antes de qualquer operação — ver `docs/knowledge/licencas-e-procedencia.md`. Remix de asset 🔴/🟡 jamais é publicado.
11. **PT-BR nos docs.** Direto, técnico, sem marketing. Commits: conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`) com subject curto e descritivo.
12. **Autonomia com responsabilidade.** Executar passos rotineiros sem pedir permissão. Interromper o dono SOMENTE para: decisão destrutiva, credenciais/pagamentos, ambiguidade real de escopo, ou aprovação de resultado (gates de fase).

---

## 2. Estrutura Canônica de Diretórios

```text
3dprinter-setup-ia/
├── AGENTS.md                  # Este contrato
├── PROGRESS.md                # Checklist vivo — fonte da verdade do estado
├── HANDOFF.md                 # Contexto de retomada para qualquer agente
├── README.md                  # Visão geral e comandos canônicos
├── docs/
│   ├── architecture.md        # Módulos, pipeline comum, contratos, guard de VRAM
│   ├── roadmap.md             # Fases com critérios de aceite objetivos
│   ├── decisions/             # ADRs — registro de decisões estruturais
│   ├── knowledge/             # Base técnica para qualquer IA já saber operar
│   │   ├── stl-e-malhas.md
│   │   ├── impressao-resina.md
│   │   ├── blender-headless.md
│   │   ├── wsl-gpu.md
│   │   └── licencas-e-procedencia.md
│   └── operations/
│       └── environment-audit.md   # Auditoria com OUTPUTS REAIS (nunca inventar)
├── tools/                     # Ferramentas determinísticas (por fase)
│   ├── forja/                 # Fase 2 — ops bpy (reparo, booleana, oco, deform...)
│   ├── generator/             # Fase 1 — plugins TRELLIS/TripoSR + benchmark
│   ├── pose/                  # Fase 3 — auto-rig + biblioteca de poses JSON
│   └── validation/            # Gates objetivos (manifold, espessura, mm, volume)
├── evidence/                  # Evidências reais (logs, JSONs de teste, capturas)
└── data/                      # Entradas/saídas de trabalho (ignorado pelo git)
```

---

## 3. Fluxo Padrão de Sessão (todo agente, toda vez)

1. Ler `PROGRESS.md` → `HANDOFF.md` → `docs/roadmap.md` (fase corrente).
2. Executar a tarefa da fase. Passos rotineiros não pedem permissão.
3. Validar com comando determinístico quando aplicável; salvar evidência em `evidence/`.
4. Atualizar `PROGRESS.md` (e `HANDOFF.md` se o contexto de retomada mudou).
5. Commit convencional + `git push`. Verificar: `git status` limpo e `git log origin/main..HEAD` vazio.
6. Ao encerrar: relatório curto ao dono com o que foi feito, pendências reais e próximo gatilho.

---

## 4. Convenções

| Item | Convenção |
|---|---|
| Idioma dos docs | PT-BR, técnico, sem marketing |
| Commits | Conventional commits, subject curto (ex.: `docs: adiciona ADR-004 venv isolado`) |
| Legenda de progresso | `[x]` concluído · `[~]` em andamento · `[ ]` pendente · `[!]` bloqueado/pendência |
| Datas | ISO `AAAA-MM-DD` |
| Auditorias | Comando + output real em bloco de código; sem paráfrase, sem invenção |
| Validação | Gate objetivo = número/exit code verificável (ex.: "arestas non-manifold = 0"), não "parece bom" |
| Arquivos gerados | Malhas/pesos/renders em `data/`/`output/` (git-ignored); evidências de texto em `evidence/` (commitadas) |

---

## 5. Definition of Done (geral)

Uma tarefa só vira `[x]` quando **todas** as aplicáveis forem verdade:

- [ ] Executada de verdade (não parcial, não "deveria funcionar");
- [ ] Validador determinístico passou (exit 0 / métrica dentro do gate);
- [ ] Evidência salva em `evidence/` (output real, com data);
- [ ] Docs atualizadas — `PROGRESS.md` sempre; ADR novo se houve decisão estrutural;
- [ ] Commit + push confirmados no remote (`git log origin/main..HEAD` vazio);
- [ ] Sem pendência oculta: o que não passou está como `[!]` em `PROGRESS.md`.

---

## 6. Guardrails Técnicos do Projeto

- **VRAM:** antes de job GPU, rodar o guard (`docs/knowledge/wsl-gpu.md`). Se VRAM livre insuficiente: não iniciar, avisar o dono (futuro: toast do Windows) e/ou aguardar. Serialização estrita de jobs GPU.
- **Procedência:** nenhum asset entra no pipeline sem sidecar JSON de procedência (ADR-003). Triage 🟢 CC0/CC-BY · 🟡 uso pessoal · 🔴 sem licença clara.
- **Integração PrintFlow3D:** endpoints reais em `docs/architecture.md` §6. Nunca subir arquivo sem os metadados mínimos registrados localmente.
- **Isolamento de venv:** este projeto usa `/home/bruno/.venvs/printer3d-ia` (ADR-004). O venv `game-ai3d` do projeto de games é **somente referência** — nunca instalar, atualizar ou reutilizar.
- **Reproducibilidade:** pesos de IA nunca são commitados (`.gitignore`); instalação de pesos é procedimento documentado de cada fase.
