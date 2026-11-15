# ADR-006 — Suporte multi-máquina: caminhos portáveis, perfis de máquina e venv por nome

**Status:** Aceito · **Data:** 2026-11-14 · **Fase:** 1 (onboarding multi-máquina)

## Contexto

O projeto ganhará um segundo contribuidor, numa outra máquina (Windows 11, WSL2 a instalar, RTX 5060 Ti 8GB Blackwell/sm_120). Até aqui comandos e docs assumiam `/home/bruno/...` e "a RTX 3060 12GB" — verdadeiro só no PC de referência. Números medidos numa máquina não valem na outra (a TRELLIS fecha em 12.070 MiB de pico; a GPU nova tem 8 GB no total), e o usuário Linux dentro do WSL de cada máquina será diferente.

## Decisão

1. **Nada de username em comandos canônicos.** O venv canônico é sempre `~/.venvs/printer3d-ia` no WSL local (nome fixo, caminho absoluto varia). Helper `tools/setup/py.sh` resolve o python correto em qualquer máquina; `~` substitui `/home/<usuario>` em toda doc/comando;
2. **Convenção dual-shell:** agente rodando no Windows usa prefixo `wsl`; agente dentro do WSL roda direto. Ambos válidos e equivalentes — tabela canônica no `README.md`;
3. **Perfis de máquina** em `docs/operations/machine-profiles/` (`rtx3060-12gb.md` = medidas reais do PC de referência; `rtx5060ti-8gb.md` = alvo marcado "A VALIDAR" até o colega medir). Números "A VALIDAR" são **proibidos de serem tratados como medidos** (AGENTS.md §1.5);
4. **Guard de VRAM paramétrico:** `tools/generator/gpu_guard.py` lê o limite do perfil de máquina (env `PRINTER3D_GUARD_MIN_FREE_MIB`, env `PRINTER3D_MACHINE_PROFILE`, ou default 10.000 MiB = comportamento histórico da 3060). Comportamento na 3060 permanece idêntico;
5. **Evidências namespaced por máquina** (`evidence/rtx5060ti-8gb/...`) — detalhes de governança em AGENTS.md §Contribuidores.

## Consequências

- Onboarding de máquina nova não exige editar o repo para "caber" nela: scripts de `tools/setup/` checam e criam o ambiente localmente;
- Risco de contaminação de métricas entre máquinas é bloqueado por construção (perfis + evidências separadas);
- Benchmark comparado entre máquinas só com os dois `results.json` lado a lado — nunca misturar numa média;
- O default da 3060 (10.000 MiB) fica congelado como fallback: qualquer regressão no mecanismo paramétrico não muda o comportamento do PC de referência.
