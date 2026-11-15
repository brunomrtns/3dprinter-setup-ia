# Perfil de máquina — rtx5060ti-8gb (máquina do 2º contribuidor)

> ✅ **DADOS DA FASE A MEDIDOS** (auditoria real de 2026-11-15 — `evidence/rtx5060ti-8gb/environment-audit-fase-a.md`). O que ainda não existe nesta máquina (Blender, PyTorch, benchmark do TripoSR) está marcado **"A VALIDAR (Fase B)"** — proibido citá-lo como medida (AGENTS.md §1.5).

## Identidade

| Campo | Valor (medido, audit 2026-11-15) |
|---|---|
| Hardware | ASUS TUF GAMING B550M-PLUS · AMD Ryzen 7 5700X (8c/16t) · 32 GB RAM |
| SO | Windows 11 Pro 26H2 (build 26300) + WSL2 (HypervisorPresent=True) |
| Distro | `Ubuntu-26.04` — Ubuntu 26.04.1 LTS, kernel 6.18.58.1-microsoft-standard-WSL2 |
| GPU | NVIDIA GeForce RTX 5060 Ti, **8151 MiB total**, arquitetura **Blackwell (sm_120)** |
| Driver (Windows) | **621.24 WDDM** (KMD) |
| Driver (visto do WSL) | NVIDIA-SMI **620.73.02** · CUDA UMD **13.5** |
| VRAM em repouso (desktop Windows) | **1,0–1,4 GB usados** (medições: 1090 MiB no guard, 1376 MiB com desktop ativo) → livre no WSL: **6803 MiB** |
| Python 3.11 | `/usr/bin/python3.11` — **3.11.18** (PPA deadsnakes; default do sistema é 3.14.4, não usar para CUDA) |
| Git | 2.53.0 no WSL · identidade configurada (`user.name=yuriiyuriiyurii91-afk`) |
| Discos | C: 814,8 GB livres / 930,4 GB · VHD WSL: 955 GB livres / 1007 GB |
| Blender | **A VALIDAR (Fase B)** — alvo 5.0.1 headless; não instalado na Fase A |
| venv do projeto | **A VALIDAR (Fase B)** — `~/.venvs/printer3d-ia` ainda não criado nesta máquina |

## Guard de VRAM

| Parâmetro | Valor |
|---|---|
| VRAM total | 8151 MiB (medido) |
| Desktop Windows em repouso/ativo | 1,0–1,4 GB (medido; 1090 MiB no momento do guard) |
| VRAM livre medida no WSL | **6803 MiB** |
| `min_free_mib` (guard) | **6500 MiB — CONFIRMADO como seguro** (margem ~303 MiB sobre os 6803 livres medidos) |
| Ativação | `PRINTER3D_MACHINE_PROFILE=rtx5060ti-8gb` (ou `PRINTER3D_GUARD_MIN_FREE_MIB=6500`) |

**Nota operacional desta máquina:** antes de qualquer job de GPU, **fechar navegadores, jogos e apps com overlay NVIDIA** — o desktop já ocupa 1,0–1,4 GB dos 8 GB, e a margem sobre o guard é pequena (~0,3 GB). Diferente da 3060, aqui não há folga para "desktop pesado" durante o job.

## Stack PyTorch — restrição dura da Blackwell

- sm_120 **não** roda nas wheels cu121 legadas (torch 2.5.1+cu121 da 3060 **não** serve aqui);
- Exige **PyTorch ≥ 2.7 com wheels cu128** — versão exata **A VALIDAR (Fase B)**;
- Dependências nativas compiladas para sm_120 são raras → instalação pelo caminho do TRELLIS segue inviável na prática;
- Prova de sanidade na Fase B: `torch.cuda.is_available()` == `True` e `torch.cuda.get_device_capability()` == `(12, 0)` — **A VALIDAR (Fase B)**.

## Gerador desta máquina: **TripoSR** (decisão por descarte, confirmada)

- **TRELLIS INVIÁVEL nesta GPU — confirmado**: pico medido de **12.070 MiB na 3060** (`evidence/benchmark/`) > 8151 MiB totais da 5060 Ti. Não é "apertado": fisicamente não cabe;
- **TripoSR é o gerador desta máquina**: pico medido de **3.588 MiB na 3060** — cabe com folga grande nos ~6,8 GB livres da 5060 Ti (pico real nesta máquina: **A VALIDAR na Fase B** — medir com o `VramPoller`);
- Benchmark local do TripoSR (tempo/VRAM/vértices por caso): **A VALIDAR (Fase B)** — não comparar medianas entre máquinas sem os dois `results.json` lado a lado (ADR-006).

## Pendências desta máquina

- [ ] Fase B: Blender, venv (torch cu128), TripoSR + benchmark local → trocar cada "A VALIDAR (Fase B)" acima pelo valor medido com evidência em `evidence/rtx5060ti-8gb/`.
