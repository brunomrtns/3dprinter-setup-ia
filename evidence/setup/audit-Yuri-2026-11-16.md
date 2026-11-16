# Auditoria de Ambiente — 2026-11-16 10:57 -03

**Executor:** agente (tools/setup/collect-audit.sh) · **Método:** comandos reais, outputs colados abaixo — nenhum output inventado (AGENTS.md §1.5).

## Sumário

| Item | Comando | Status | Resultado-chave |
|---|---|---|---|
| WSL | `(dentro do WSL)` | ✅ | WSL2 (WSL2) |
| Distro | `lsb_release`/`os-release` | ✅ | Ubuntu 26.04.1 LTS (kernel 6.18.58.1-microsoft-standard-WSL2) |
| Blender | `blender --version` | ✅ | Blender 5.0.1 |
| GPU (WSL) | `nvidia-smi --query-gpu=...` | ✅ | NVIDIA GeForce RTX 5060 Ti, 621.24, 8151 MiB, 6671 MiB |
| Python 3.11 | `python3.11 --version` | ✅ | Python 3.11.18 @ /usr/bin/python3.11 |
| Git | `git --version` | ✅ | git version 2.53.0 |
| Disco WSL | `df -h /` | ✅ | /dev/sdd       1007G   18G  939G   2% / |
| venv printer3d-ia | `torch; cuda.is_available()` | ✅ | 2.11.0+cu128 True |
| Guard (perfil) | `tools/setup/py.sh tools/generator/gpu_guard.py` | — | rodar separadamente e colar aqui |

## Outputs Reais

### Distro / kernel

```bash
$ (. /etc/os-release && echo $PRETTY_NAME); uname -r
Ubuntu 26.04.1 LTS
6.18.58.1-microsoft-standard-WSL2
```

### GPU (nvidia-smi completo)

```
Mon Nov 16 10:57:13 2026       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 620.73.02              KMD Version: 621.24        CUDA UMD Version: 13.5     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA GeForce RTX 5060 Ti     On  |   00000000:07:00.0  On |                  N/A |
|  0%   41C    P3             18W /  180W |    1217MiB /   8151MiB |      6%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|    0   N/A  N/A              33      G   /Xwayland                             N/A      |
+-----------------------------------------------------------------------------------------+
```

### Guard de VRAM (perfil de máquina, ADR-006)

```
$ tools/setup/py.sh tools/generator/gpu_guard.py || python3.11 tools/generator/gpu_guard.py
[gpu_guard] perfil de máquina: rtx5060ti-8gb → guard 6500 MiB (medido Fase A 2026-11-15 (VRAM livre 6803 MiB com desktop ativo; guard 6500 confirmado seguro; benchmark do TripoSR pendente na Fase B))
[gpu_guard] VRAM used=1217 MiB free=6676 MiB threshold=6500 MiB
[gpu_guard] OK para despachar job GPU
```

### Python / venv / git

```bash
$ python3.11 --version; git --version
Python 3.11.18
git version 2.53.0
$ ~/.venvs/printer3d-ia/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
2.11.0+cu128 True
```

### Disco

```bash
$ df -h /
/dev/sdd       1007G   18G  939G   2% /
```

## Pendências

- [ ] preencher conforme os outputs acima (o que falhou vai aqui com o erro REAL)
