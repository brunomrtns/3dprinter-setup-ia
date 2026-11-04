# Auditoria de Ambiente — Fase 0

**Data:** 2026-11-03 · **Executor:** agente fundador (OpenCode) · **Método:** comandos reais executados e colados abaixo — **nenhum output inventado** (regra: AGENTS.md §1.5).

## Sumário

| Item | Comando | Status | Resultado-chave |
|---|---|---|---|
| Blender (WSL) | `wsl blender --version` | ✅ | Blender 5.0.1 (`/usr/bin/blender`) |
| GPU/CUDA (WSL) | `wsl nvidia-smi` | ✅ | RTX 3060 12GB, CUDA 13.5, 10853 MiB livres |
| GPU (Windows) | `nvidia-smi` | ✅ | Driver 621.01 WDDM; ~1.2 GB já em uso pelo desktop |
| CUDA utilizável (venv ref.) | `torch.cuda.is_available()` | ✅ | `True` (torch 2.5.1+cu121 no game-ai3d) |
| Python (Windows) | `python --version` | ✅ | 3.13.15 |
| Python (WSL, sistema) | `wsl python3 --version` | ✅ | 3.14.4 (⚠️ ver Pendências #1) |
| Python 3.11 (WSL) | `wsl python3.11 --version` | ✅ | 3.11.16 em `/usr/bin/python3.11` |
| Git (WSL) | `wsl git --version` | ✅ | 2.53.0 |
| Git (Windows) / identidade | `git config user.*` | ✅ | 2.56.0.windows.2 · configurado nesta sessão (ver §Git) |
| Disco C: (Windows) | `Win32_LogicalDisk` | ✅ | 199,2 GB livres / 930,5 GB |
| Disco WSL (ext4) | `wsl df -h /` | ✅ | 866 GB livres / 1007 GB |
| WSL2 | `wsl -l -v` | ✅ | Distro única `Ubuntu`, WSL2, Running |
| venv game-ai3d (referência) | `ls ~/.venvs` | ✅ | Existe, Python 3.11.16 — **não usado por este projeto** (ADR-004) |

**Conclusão para a Fase 1: nenhum bloqueio real.** Todos os pré-requisitos (Blender, CUDA no WSL, disco, interpretador 3.11) estão verificados.

---

## Outputs Reais

### WSL — versão e distro

```
PS> wsl -l -v
  NAME      STATE     VERSION
* Ubuntu    Running   2
```

```
PS> wsl bash -lc 'grep PRETTY_NAME /etc/os-release; uname -r'
PRETTY_NAME="Ubuntu 26.04 LTS"
6.18.33.2-microsoft-standard-WSL2
```

### Blender (WSL) — caminho crítico da Forja (Fase 2)

```
PS> wsl blender --version
Blender 5.0.1
```

### GPU — vista do WSL (nvidia-smi)

```
PS> wsl nvidia-smi
Tue Nov  3 22:14:28 2026
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 620.67.01              KMD Version: 621.01        CUDA UMD Version: 13.5     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id        Disp.A  | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |             Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================+
|   0  NVIDIA GeForce RTX 3060        On  |  00000000:05:00.0  On  |                  N/A |
|  0%   35C    P8             12W /  170W |    1263MiB /  12288MiB |     22%      Default |
+-----------------------------------------+------------------------+----------------------+

Processes: No running processes found (dentro do WSL)
```

### GPU — vista do Windows (mesma GPU, prova do compartilhamento de VRAM)

```
PS> nvidia-smi
Tue Nov  3 22:14:28 2026
| NVIDIA-SMI 621.01   Driver-Model: WDDM |  ...  CUDA Version (UMD): 13.5
|   0  NVIDIA GeForce RTX 3060      WDDM |  00000000:05:00.0  On  |
|  0%   35C    P8     12W / 170W   |   1261MiB /  12288MiB |  26%   Default |

Processes (C+G, resumo — lista real completa no momento da auditoria):
  chrome.exe · explorer.exe · WindowsTerminal.exe · ShellExperienceHost.exe
  NVIDIA Overlay.exe (x2) · NVIDIA Broadcast.exe (x2) · OpenCode.exe
  Spotify.exe · WhatsApp.Root.exe · msedgewebview2.exe (x2) · SystemSettings.exe ...
```

> Evidência direta do requisito de guard de VRAM (`docs/knowledge/wsl-gpu.md`): com o desktop em repouso, ~1.2 GB dos 12 GB já estão consumidos por processos do Windows.

### Guard de VRAM — comando canônico (output real)

```
PS> wsl nvidia-smi --query-gpu=memory.free,memory.total,memory.used --format=csv
memory.free [MiB], memory.total [MiB], memory.used [MiB]
10853 MiB, 12288 MiB, 1258 MiB
```

### CUDA utilizável dentro de venv (referência `game-ai3d` — sem depender dele)

```
PS> wsl bash -lc "~/.venvs/game-ai3d/bin/python -c 'import torch; print(torch.__version__); print(torch.cuda.is_available())'"
2.5.1+cu121
True
```

### Python — Windows vs WSL

```
PS> python --version          # Windows
Python 3.13.15

PS> wsl python3 --version     # WSL, sistema (default)
Python 3.14.4

PS> wsl bash -lc 'python3.11 --version; which python3.11; ls /usr/bin/python3.*'
Python 3.11.16
/usr/bin/python3.11
/usr/bin/python3.11  /usr/bin/python3.11-config  /usr/bin/python3.14  /usr/bin/python3.9  ...
```

### Git

```
PS> git --version             # Windows
git version 2.56.0.windows.2

PS> wsl git --version         # WSL
git version 2.53.0
```

**Identidade:** `user.name`/`user.email` estavam AUSENTES em todos os escopos (global/system). Configurado nesta sessão:
`user.name=Bruno Martins`, `user.email=brunomartinsss@gmail.com` (identidade pública do dono no GitHub), `init.defaultBranch=main`.

### Disco

```
PS> Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
DeviceID  FreeGB  TotalGB
C:        199,2   930,5
```

```
PS> wsl df -h /; wsl df -h /home
Filesystem      Size  Used Avail Use% Mounted on
/dev/sdd       1007G   91G  866G  10% /
(dev/sdd = VHD ext4 do WSL — onde os ~13 GB de pesos TRELLIS da Fase 1 devem morar)
```

### venv `game-ai3d` (referência apenas — ADR-004)

```
PS> wsl bash -lc 'ls -la ~/.venvs/; ~/.venvs/game-ai3d/bin/python --version; ls ~/.venvs/game-ai3d/lib/'
total 12
drwxr-xr-x  3 bruno bruno 4096 Oct 15 21:41 .
drwxr-x--- 16 bruno bruno 4096 Oct 20 01:14 ..
drwxr-x---  6 bruno bruno 4096 Oct 15 21:42 game-ai3d
Python 3.11.16
python3.11
```

---

## Pendências (nenhuma bloqueia a Fase 1)

| # | Item | Causa real | Plano |
|---|---|---|---|
| 1 | `[~]` Python default do WSL é 3.14.4 | TRELLIS tipicamente pinna Python ≤3.11 (stack torch próprio); 3.14 é recente demais para wheels CUDA | Fase 1: criar o venv `printer3d-ia` com `/usr/bin/python3.11` (já disponível, mesma família do game-ai3d) |
| 2 | `[~]` Requisito real de VRAM do TRELLIS ainda desconhecido NESTE ambiente | Números de README de terceiros (~90s/1024³) não são medição local | Fase 1: benchmark mede `vram_pico_mib` e tempo por caso; guard usa o valor medido |
| 3 | `[ ]` Aviso de VRAM insuficiente é só log (sem toast do Windows) | Decisão de design adiada (não há dor ainda) | Se doer na prática: toast via PowerShell `BurntToast` ou equivalente — a definir em fase futura |

## Conclusão para a Fase 1

- Sem bloqueio real: WSL2+CUDA funcionando (provado por `torch.cuda.is_available()=True`), Blender 5.0.1 no WSL, disco folgado (866 GB no VHD), interpretador 3.11 disponível, remote git com SSH operacional (`Hi brunomrtns!`).
- A Fase 1 começa criando `/home/bruno/.venvs/printer3d-ia` com Python 3.11 (Pendência #1) e instalando TRELLIS — ver `docs/roadmap.md` §Fase 1.
