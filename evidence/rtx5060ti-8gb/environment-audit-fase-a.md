# Auditoria de Ambiente — Fase A (Base)

**Data:** 2026-11-15 · **Executor:** agente de configuração (OpenCode) · **Método:** comandos reais executados e colados abaixo — **nenhum output inventado**.

**Máquina:** ASUS TUF GAMING B550M-PLUS · AMD Ryzen 7 5700X (8 núcleos / 16 threads) · 32 GB RAM · Windows 11 Pro 26H2 (build 26300)

## Sumário

| Item | Comando | Status | Resultado-chave |
|---|---|---|---|
| Blender (WSL) | `wsl blender --version` | — | não instalado (normal nesta fase) |
| GPU/CUDA (WSL) | `wsl nvidia-smi` | ✅ | RTX 5060 Ti 8GB, CUDA UMD 13.5, 6803 MiB livres |
| GPU (Windows) | `nvidia-smi` | ✅ | Driver 621.24 WDDM; ~1,0–1,4 GB já em uso pelo desktop |
| CUDA utilizável (venv) | `torch.cuda.is_available()` | — | não instalado (normal nesta fase) |
| Python (Windows) | `python --version` | — | não instalado (normal nesta fase; alias da Microsoft Store) |
| Python (WSL, sistema) | `wsl python3 --version` | ✅ | 3.14.4 (⚠️ ver Pendências #1) |
| Python 3.11 (WSL) | `wsl python3.11 --version` | ✅ | 3.11.18 em `/usr/bin/python3.11` (instalado nesta fase via PPA deadsnakes) |
| Git (WSL) | `wsl git --version` | ✅ | 2.53.0 (já vinha no Ubuntu 26.04) |
| Git — identidade | `git config --global --list` | ✅ | **configurada nesta fase**: `user.name=yuriiyuriiyurii91-afk`, `user.email=yuriiyuriiyurii91@gmail.com`, `init.defaultBranch=main` |
| Disco C: (Windows) | `Win32_LogicalDisk` | ✅ | 814,8 GB livres / 930,4 GB |
| Disco WSL (ext4) | `wsl df -h /` | ✅ | 955 GB livres / 1007 GB |
| WSL2 | `wsl --list --verbose` | ✅ | Distro única `Ubuntu-26.04`, WSL2, Running |
| Hipervisor/virtualização | `Win32_ComputerSystem` | ✅ | `HypervisorPresent = True` (após: SVM no BIOS + componente "Plataforma da Máquina Virtual" ativado) |

**Conclusão para a Fase A: base pronta.** WSL2 + Ubuntu 26.04.1 LTS + GPU visível dentro do WSL + Python 3.11 disponível + git configurado. Sem bloqueios para a próxima fase.

---

## Outputs Reais

### WSL — versão e distro

```
PS> wsl --list --verbose
  NAME        STATE     VERSION
* Ubuntu-26.04 Running   2
```

```
PS> wsl -d Ubuntu-26.04 bash -lc 'grep PRETTY_NAME /etc/os-release; uname -r'
PRETTY_NAME="Ubuntu 26.04.1 LTS"
6.18.58.1-microsoft-standard-WSL2
```

### GPU — vista do WSL (nvidia-smi)

```
PS> wsl -d Ubuntu-26.04 nvidia-smi
Sun Nov 15 09:48:55 2026
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 620.73.02              KMD Version: 621.24        CUDA UMD Version: 13.5     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
|   0  NVIDIA GeForce RTX 5060 Ti     On  |   00000000:07:00.0  On |                  N/A |
| 0%   43C    P3             18W /  180W |    1121MiB /   8151MiB |      7%      Default |
+-----------------------------------------------------------------------------------------+
| Processes:  G  /Xwayland
```

### GPU — vista do Windows (mesma GPU, prova do compartilhamento de VRAM)

```
PS> nvidia-smi
Sat Nov 14 23:08:12 2026
| NVIDIA-SMI 621.24  KMD Version: 621.24  CUDA UMD Version: 13.5
|   0  NVIDIA GeForce RTX 5060 Ti   WDDM  |  00000000:07:00.0  On
|    1376MiB /   8151MiB  (desktop em uso no momento da medição)
```

> Evidência do guard de VRAM: com o desktop ativo, ~1,0–1,4 GB dos 8 GB já estão consumidos por processos do Windows.

### Guard de VRAM — comando canônico (output real)

```
PS> wsl -d Ubuntu-26.04 nvidia-smi --query-gpu=memory.free,memory.total,memory.used --format=csv
memory.free [MiB], memory.total [MiB], memory.used [MiB]
6803 MiB, 8151 MiB, 1090 MiB
```

### CUDA utilizável dentro de venv

```
não instalado (normal nesta fase) — PyTorch/TRELLIS/TripoSR ficam para a fase seguinte
```

### Python — Windows vs WSL

```
PS> python --version          # Windows
Python was not found (alias da Microsoft Store; sem Python instalado no Windows)

PS> wsl -d Ubuntu-26.04 python3 --version     # WSL, sistema (default)
Python 3.14.4

PS> wsl -d Ubuntu-26.04 python3.11 --version  # instalado nesta fase
Python 3.11.18
/usr/bin/python3.11
```

Instalação do 3.11 nesta fase (Ubuntu 26.04 não traz 3.11 no repositório oficial):

```
# PPA deadsnakes adicionado como root no WSL
add-apt-repository -y ppa:deadsnakes/ppa
apt-get install -y python3.11 python3.11-venv python3.11-dev
# Candidate disponível: 3.11.18-1+resolute1
```

### Git

```
PS> wsl -d Ubuntu-26.04 git --version   # WSL
git version 2.53.0

PS> git --version                        # Windows
git: não reconhecido (não instalado no Windows — normal nesta fase; o projeto roda no WSL)
```

**Identidade (configurada nesta fase, output real):**

```
PS> wsl -d Ubuntu-26.04 git config --global --list
user.name=yuriiyuriiyurii91-afk
user.email=yuriiyuriiyurii91@gmail.com
init.defaultbranch=main
```

### Disco

```
PS> Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
DeviceID  Livre(GB)  Total(GB)
C:        814,8      930,4
```

```
PS> wsl -d Ubuntu-26.04 df -h /
Filesystem      Size  Used Avail Use% Mounted on
/dev/sdd       1007G  1.3G  955G   1% /
(/dev/sdd = VHD ext4 do WSL)
```

---

## Pendências (nenhuma bloqueia a fase seguinte)

| # | Item | Causa real | Plano |
|---|---|---|---|
| 1 | `[~]` Python default do WSL é 3.14.4 | Projeto pinna Python 3.11; 3.14 é recente demais para wheels CUDA | Fase seguinte: criar o venv do projeto com `/usr/bin/python3.11` (já disponível) |
| 2 | `[ ]` Blender, PyTorch, TRELLIS, TripoSR não instalados | Escopo da Fase A é só a base | Instalar na fase seguinte, conforme instruções |

## Conclusão para a Fase Seguinte

- Sem bloqueio real: WSL2 funcional (`HypervisorPresent=True`), Ubuntu 26.04.1 LTS rodando, CUDA visível dentro do WSL (RTX 5060 Ti 8 GB, 6803 MiB livres no guard), Python 3.11.18 disponível, identidade git configurada, disco folgado (955 GB no VHD, 814,8 GB no C:).
- A fase seguinte começa criando o venv com `/usr/bin/python3.11` (Pendência #1) e instalando Blender/PyTorch/TRELLIS — conforme o roadmap do projeto.
