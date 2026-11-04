# ADR-004 — venv próprio isolado (`printer3d-ia`), nunca o `game-ai3d`

**Status:** Aceito · **Data:** 2026-11-03 · **Fase:** 0 (execução na Fase 1)

## Contexto

O projeto de games (gamedev-setup-ia) mantém o venv `/home/bruno/.venvs/game-ai3d` (Python 3.11.16, torch 2.5.1+cu121, PIL/numpy/trimesh/requests — audit 2026-11-03) que **já funciona** com CUDA na 3060, inclusive rodando TripoSR. A tentação é reutilizá-lo aqui. Porém: a Fase 1 instala TRELLIS, que chega com dependências pesadas e versionadas de forma rígida (torch específico, extensões CUDA, kernels) com alto risco de conflito com o stack pinado do projeto de games.

## Decisão

1. Este projeto cria e usa **exclusivamente** o venv `/home/bruno/.venvs/printer3d-ia` no WSL (Fase 1);
2. O venv `game-ai3d` é **somente referência** (padrões, versões conhecidas, prova de que CUDA funciona) — **proibido** instalar, atualizar ou apagar pacotes nele a partir deste projeto;
3. Pesos de IA ficam fora do repo (`.gitignore`) e fora de `/mnt/c` — filesystem nativo do WSL (ver `docs/knowledge/wsl-gpu.md` §5).

## Consequências

- Custo de disco: um segundo stack torch+CUDA (~dez GB com pesos TRELLIS). Aceito — disco real do WSL: 866 GB livres (audit);
- Blast radius zero entre projetos: OOM, dependência quebrada ou downgrade no venv novo nunca derruba o pipeline de games, e vice-versa;
- Reprodutibilidade por projeto: cada repo documenta e pinna seu próprio `requirements.txt`/lock sem negociar com o outro;
- A duplicação de downloads de pesos compartilháveis entre projetos (se um dia doer) será tratada com cache dedicado — não com venv compartilhado.
