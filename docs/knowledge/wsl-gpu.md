# WSL e GPU (CUDA, VRAM compartilhada, Guard)

> Realidade do ambiente (audit 2026-11-03): Windows 11 + WSL2 Ubuntu 26.04, kernel 6.18.33.2-microsoft-standard-WSL2, RTX 3060 12 GB, driver NVIDIA 621.01 (Windows) / 620.67.01 (vista do WSL), CUDA UMD 13.5, torch 2.5.1+cu121 com `cuda.is_available() == True` no venv de referência.

## 1. Como CUDA funciona no WSL2

- O driver NVIDIA é instalado **só no Windows**. O WSL2 recebe a stack CUDA via mapeamento (`/usr/lib/wsl/lib/`), incluindo o `nvidia-smi`;
- **Não instale driver da NVIDIA dentro do WSL** — quebra o mapeamento;
- O `nvidia-smi` visto no WSL mostra a MESMA GPU do Windows (mesmos 12 GB, mesmos processos somados);
- Docker/CUDA toolkit: só quando uma fase exigir (nenhuma exige até a Fase 1; TRELLIS usa torch+CUDA wheel).

## 2. VRAM é UM único pool disputado

A RTX 3060 tem 12288 MiB **totais**, e o desktop Windows já consome por padrão. Medição real em repouso (2026-11-03): **1258 MiB em uso** por Chrome, NVIDIA Overlay/Broadcast, OpenCode, Spotify, Windows Shell — restando ~10.8 GB. Durante um job de IA, abrir um jogo ou uma aba pesada de navegador pode derrubar o job com OOM — e vice-versa: job de IA pode travar a tela do Windows.

Implicações operacionais:

1. **Nunca orçar 12 GB para um job** — orçar no máximo ~10–10.5 GB e exigir folga no guard;
2. Jobs de GPU são **SERIALIZADOS** (fila única — AGENTS.md §1.9): dois jobs simultâneos = OOM quase garantido e métricas de benchmark (VRAM pico) invalidadas;
3. Falha típica de OOM no WSL: `CUDA error: out of memory` do torch, ou o processo morto sem mensagem. O orquestrador trata OOM como falha de job reenfileirável, não como bug de código.

## 3. Guard de VRAM (requisito de design do projeto)

Comando canônico (roda antes de CADA job GPU):

```bash
wsl nvidia-smi --query-gpu=memory.free,memory.total,memory.used --format=csv
# Output real (2026-11-03, desktop em repouso):
# memory.free [MiB], memory.total [MiB], memory.used [MiB]
# 10853 MiB, 12288 MiB, 1258 MiB
```

Comportamento definido em `docs/architecture.md` §4:
- `memory.free >= requisito_do_job` → despacha;
- `memory.free < requisito` → job fica `queued`, dono é avisado (futuro: toast do Windows) e/ou polling aguarda liberação;
- Requisito por modo é **medido na Fase 1** (benchmark), nunca assumido de README de terceiros.

## 4. Medição de VRAM pico (métrica da Fase 1)

Amostragem periódica durante o job (o próprio wrapper do job):

```bash
wsl nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -l 1
```

Registrar `vram_pico_mib` no `GenerationReport` de cada caso do benchmark. Com fila serial, o pico é atribuível ao job certo.

## 5. Disco e I/O

- Os pesos de IA (~13 GB TRELLIS na Fase 1) vivem no filesystem nativo do WSL (ext4) — não em `/mnt/c`;
- Disco do WSL (audit): 1007 GB de VHD, **866 GB livres**; C: do Windows: 199 GB livres — folga real para a Fase 1;
- O VHD do WSL cresce mas não encolhe sozinho (compactar com `wsl --shutdown` + `Optimize-VHD` se um dia fizer falta).

## 6. Checagens rápidas (copiar e colar)

```bash
wsl nvidia-smi                                        # estado geral da GPU
wsl nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits   # só o número (guard)
wsl bash -lc '~/.venvs/printer3d-ia/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available())"'  # sanity do venv (Fase 1+)
```
