# Auditoria de Ambiente — 2026-11-14 23:38 -03

**Executor:** agente (tools/setup/collect-audit.sh) · **Método:** comandos reais, outputs colados abaixo — nenhum output inventado (AGENTS.md §1.5).

## Sumário

| Item | Comando | Status | Resultado-chave |
|---|---|---|---|
| WSL | `(dentro do WSL)` | ✅ | WSL2 (WSL2) |
| Distro | `lsb_release`/`os-release` | ✅ | Ubuntu 26.04 LTS (kernel 6.18.33.2-microsoft-standard-WSL2) |
| Blender | `blender --version` | ✅ | Blender 5.0.1 |
| GPU (WSL) | `nvidia-smi --query-gpu=...` | ✅ | NVIDIA GeForce RTX 3060, 621.01, 12288 MiB, 10021 MiB |
| Python 3.11 | `python3.11 --version` | ✅ | Python 3.11.16 @ /usr/bin/python3.11 |
| Git | `git --version` | ✅ | git version 2.53.0 |
| Disco WSL | `df -h /` | ✅ | /dev/sdd       1007G  121G  836G  13% / |
| venv printer3d-ia | `torch; cuda.is_available()` | ✅ | 2.5.1+cu121 True |
| Guard (perfil) | `tools/setup/py.sh tools/generator/gpu_guard.py` | — | rodar separadamente e colar aqui |

## Outputs Reais

### Distro / kernel

```bash
$ (. /etc/os-release && echo $PRETTY_NAME); uname -r
Ubuntu 26.04 LTS
6.18.33.2-microsoft-standard-WSL2
```

### GPU (nvidia-smi completo)

```
Sat Nov 14 23:38:48 2026       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 620.67.01              KMD Version: 621.01        CUDA UMD Version: 13.5     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA GeForce RTX 3060        On  |   00000000:05:00.0  On |                  N/A |
|  0%   33C    P0             35W /  170W |    2092MiB /  12288MiB |      1%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|  No running processes found                                                             |
+-----------------------------------------------------------------------------------------+
```

### Guard de VRAM (perfil de máquina, ADR-006)

```
$ tools/setup/py.sh tools/generator/gpu_guard.py || python3.11 tools/generator/gpu_guard.py
[gpu_guard] perfil de máquina: rtx3060-12gb → guard 10000 MiB (medido (audit 2026-11-03 + benchmark 2026-11-04))
[gpu_guard] VRAM used=2092 MiB free=10019 MiB threshold=10000 MiB
[gpu_guard] OK para despachar job GPU
```

### Python / venv / git

```bash
$ python3.11 --version; git --version
Python 3.11.16
git version 2.53.0
$ ~/.venvs/printer3d-ia/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
2.5.1+cu121 True
```

### Disco

```bash
$ df -h /
/dev/sdd       1007G  121G  836G  13% /
```

## Pendências

- [ ] preencher conforme os outputs acima (o que falhou vai aqui com o erro REAL)
