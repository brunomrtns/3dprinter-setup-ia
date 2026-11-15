# Perfil de máquina — rtx5060ti-8gb (máquina do 2º contribuidor)

> ⚠️ **PERFIL-ALVO: TODO número desta página marcado "A VALIDAR" ainda NÃO FOI MEDIDO.**
> O contribuidor desta máquina rodará `tools/setup/collect-audit.sh` + benchmark do TripoSR e devolverá os valores reais. É **proibido** citar qualquer número daqui como medida (AGENTS.md §1.5: auditoria é real).

## Identidade (alvo declarado — A VALIDAR)

| Campo | Valor | Status |
|---|---|---|
| SO | Windows 11, WSL2 **a instalar** | planejado |
| Distro | Ubuntu (versão a definir na instalação; alvo: LTS com python3.11 disponível) | A VALIDAR |
| GPU | NVIDIA GeForce RTX 5060 Ti, **8 GB VRAM** (8192 MiB total) | especificação de fábrica |
| Arquitetura | **Blackwell — compute capability sm_120** | especificação de fábrica |
| Driver NVIDIA | PC gamer → driver recente **obrigatório** (Blackwell não sobe em driver antigo); instalar/ativar pelo app NVIDIA no Windows; WSL só enxerga (nunca instalar driver dentro do WSL — `docs/knowledge/wsl-gpu.md`) | A VALIDAR (versão exata) |
| Python 3.11 | instalável via `tools/setup/install-python311.sh` | A VALIDAR (caminho/versão) |
| Blender | alvo 5.0.1 headless | A VALIDAR |
| venv do projeto | `~/.venvs/printer3d-ia` | A VALIDAR |

## Stack PyTorch — restrição dura da Blackwell

- sm_120 **não** roda nas wheels cu121 legadas (torch 2.5.1+cu121 da 3060 **não** serve aqui);
- Exige **PyTorch ≥ 2.7 com wheels cu128** (primeiro torch com suporte Blackwell) — versão exata A VALIDAR;
- Dependências nativas (flash-attn, spconv, nvdiffrast — usadas pelo TRELLIS) precisam estar **compiladas para sm_120**; wheels prontas para sm_120 são raras → instalação pelo caminho do TRELLIS é inviável nesta máquina na prática (ver abaixo);
- Prova de sanidade a rodar nesta máquina: `torch.cuda.is_available()` == `True` e `torch.cuda.get_device_capability()` == `(12, 0)` — **A VALIDAR**.

## Guard de VRAM

| Parâmetro | Valor | Status |
|---|---|---|
| VRAM total | 8192 MiB | especificação |
| Desktop Windows em repouso | desconhecido nesta máquina | A VALIDAR |
| `min_free_mib` (guard) | **~6.500 MiB proposto** (8192 − folga de desktop + margem) | **A VALIDAR** — só trocar para o valor medido depois do primeiro benchmark local |
| Ativação | `PRINTER3D_MACHINE_PROFILE=rtx5060ti-8gb` (ou `PRINTER3D_GUARD_MIN_FREE_MIB=<medido>`) | mecanismo já suportado pelo `gpu_guard.py` |

## Gerador desta máquina: **TripoSR** (decisão por descarte)

- **TRELLIS é INVIÁVEL nesta GPU**: pico medido de **12.070 MiB na 3060** (`evidence/benchmark/`) — maior que os 8 GB totais da 5060 Ti. Não é "talvez apertado": fisicamente não cabe;
- **TripoSR é o gerador desta máquina**: pico medido de 3.588 MiB na 3060 (cabe com folga em 8 GB — na 5060 Ti: A VALIDAR). Roda com wheels cu128;
- Benchmark local do TripoSR nesta máquina: tempo/VRAM/vértices **A VALIDAR** — não comparar medianas entre máquinas sem os dois `results.json` lado a lado (ADR-006).

## Pendência única desta máquina

O contribuidor roda a auditoria (Fase B do onboarding: `tools/setup/collect-audit.sh`) e devolve: driver, CUDA, VRAM livre em repouso, python, torch/cu128, Blender, benchmark TripoSR. Com os números reais, esta página troca cada "A VALIDAR" pelo valor medido com data e evidência em `evidence/rtx5060ti-8gb/`.
