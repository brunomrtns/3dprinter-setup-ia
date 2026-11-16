# Perfil de máquina — rtx5060ti-8gb (máquina do 2º contribuidor)

> ✅ **Fase A e Fase B MEDIDAS** (auditorias reais de 2026-11-15 e 2026-11-16 — `evidence/rtx5060ti-8gb/`). Nada nesta página é promissório: todo número tem evidência. Perfil integrado pelo dono via PR #1 (revisão: 2 correções aplicadas — evidência namespaced e meta do benchmark).

## Identidade

| Campo | Valor (medido) |
|---|---|
| Hardware | ASUS TUF GAMING B550M-PLUS · AMD Ryzen 7 5700X (8c/16t) · 32 GB RAM |
| SO | Windows 11 Pro 26H2 (build 26300) + WSL2 (HypervisorPresent=True) |
| Distro | `Ubuntu-26.04` — Ubuntu 26.04.1 LTS, kernel 6.18.58.1-microsoft-standard-WSL2 |
| GPU | NVIDIA GeForce RTX 5060 Ti, **8151 MiB total**, arquitetura **Blackwell (sm_120)** |
| Driver (Windows) | **621.24 WDDM** (KMD) |
| Driver (visto do WSL) | NVIDIA-SMI **620.73.02** · CUDA UMD **13.5** |
| VRAM em repouso (desktop Windows) | **1,0–1,4 GB usados** (1090–1376 MiB nas medições) → livre no WSL: **6803 MiB** (Fase A) |
| Python 3.11 | `/usr/bin/python3.11` — **3.11.18** (PPA deadsnakes; default do sistema é 3.14.4, não usar para CUDA) |
| Git | 2.53.0 no WSL · identidade configurada (`user.name=yuriiyuriiyurii91-afk`) |
| Discos | C: 814,8 GB livres · VHD WSL: 955 GB livres (Fase A) / 939 GB (Fase B) |
| Blender | **5.0.1 headless** (tarball oficial em /opt + symlink; medido Fase B, `check-blender.sh` OK) |
| venv do projeto | `~/.venvs/printer3d-ia` — py3.11.18 · **torch 2.11.0+cu128** · `cuda.is_available()=True` · capability **(12, 0)** (medido Fase B, `check-gpu.sh` OK) |

## Guard de VRAM

| Parâmetro | Valor |
|---|---|
| VRAM total | 8151 MiB (medido) |
| Desktop Windows em repouso/ativo | 1,0–1,4 GB (medido; 1090–1217 MiB nas coletas) |
| VRAM livre medida no WSL | **6803 MiB** (Fase A) · **6676–6691 MiB** (Fase B, durante jobs) |
| `min_free_mib` (guard) | **6500 MiB — CONFIRMADO** e **validado em produção**: liberou todos os 10 jobs do benchmark com 6687–6691 MiB livres; pico do TripoSR 4385 MiB ficou bem abaixo do threshold |
| Ativação | `PRINTER3D_MACHINE_PROFILE=rtx5060ti-8gb` (ativo no `~/.bashrc`/`~/.profile` da máquina) |

**Nota operacional desta máquina:** antes de qualquer job de GPU, **fechar navegadores, jogos e apps com overlay NVIDIA** — o desktop já ocupa 1,0–1,4 GB dos 8 GB, e a margem sobre o guard é pequena (~0,3 GB). Diferente da 3060, aqui não há folga para "desktop pesado" durante o job.

## Stack PyTorch — restrição dura da Blackwell

- sm_120 **não** roda nas wheels cu121 legadas (torch 2.5.1+cu121 da 3060 **não** serve aqui);
- **Resolvido (medido Fase B): torch 2.11.0+cu128**, `cuda.is_available()=True`, `get_device_capability()=(12, 0)` ✓;
- Pin importante descoberto no setup (PR #1): **transformers 4.46.2** — a 5.x renomeia keys do ViT e quebra o load do ckpt do TripoSR (evidência em `evidence/rtx5060ti-8gb/setup/pip-triposr-deps-2026-11-16.log`);
- TRELLIS segue inviável nesta GPU (ver abaixo) — as deps nativas dele para sm_120 nem entraram no caminho.

## Gerador desta máquina: **TripoSR** — benchmark local MEDIDO (Fase B, 2026-11-16)

| Modo | Tempo mediana | VRAM pico | Vértices médios | Manifold pós-reparo leve | Erros |
|---|---|---|---|---|---|
| triposr (5060 Ti 8GB) | **14,4 s** (faixa 13,4–31,1) | **4385 MiB** | 74.031 | **9/10** | **0/10** |
| trellis (5060 Ti 8GB) | — | — | — | — | **10/10** (sem mesh — inviável, como previsto) |

- **TRELLIS INVIÁVEL confirmado por execução** (não só por descarte): 10/10 casos sem mesh nesta GPU;
- TripoSR aqui vs 3060 (`evidence/benchmark/`): ~45% mais rápido (mediana 14,4s vs 27,3s), VRAM pico 4385 vs 3588–4385 MiB, mesmo perfil de qualidade (manifold 9/10, sólidos com casca mais grossa);
- Comparação entre máquinas: apenas com os dois `results.json` lado a lado — nunca misturar médias (ADR-006);
- Fontes: `evidence/rtx5060ti-8gb/benchmark/` (results.json, scores.md, gallery.md + 20 renders) e `benchmark-triposr-2026-11-16.log`.

## Pendências desta máquina

- [x] ~~Fase B: Blender, venv (torch cu128), TripoSR + benchmark local~~ — **concluída e integrada (PR #1, merge 2026-11-16)**;
- [ ] Dono vota 👍/👎 na galeria (as duas: `evidence/benchmark/gallery.md` da 3060 e `evidence/rtx5060ti-8gb/benchmark/gallery.md` da 5060 Ti) → ADR-005 (default mode).
  - **Atualização 2026-11-16:** ADR-005 fechado SEM default mode (dono reprovou globalmente os geradores de 1ª geração). A fase C1 (TRELLIS.2 fork nesta máquina) entra pelo roadmap §Fase C.

**Fase C: TRELLIS.2 (fork) e TripoSG — A VALIDAR (proibido citar como medido antes da evidência).**
