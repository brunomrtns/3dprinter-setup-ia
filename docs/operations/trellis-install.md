# Instalação do TRELLIS — registro passo a passo (outputs reais)

**Data:** 2026-11-03/04 · **Executor:** agente Fase 1 · **Regra:** nenhum output inventado (AGENTS.md §1.5)

## Decisão prévia: TRELLIS 1 vs TRELLIS.2 (avaliação curta)

Existe `microsoft/TRELLIS.2` (nov/2025, MIT, 12.6k stars). **Requisito oficial de hardware do README: "An NVIDIA GPU with at least 24GB of memory is necessary. The code has been verified on NVIDIA A100 and H100 GPUs."** A RTX 3060 tem 12 GB — **bloqueio objetivo, sem espaço para trade-off**. Além disso a stack da TRELLIS.2 é mais pesada (setup.sh com flexgemm/cumesh/o-voxel/nvdiffrec compilados, torch 2.6+).

**Escolha: `microsoft/TRELLIS` (TRELLIS 1)** — MIT, compatível com 12 GB (comprovado abaixo), deps wheel-pré-compiladas disponíveis para torch 2.5.1/cu121. TRELLIS.2 reavaliável em hardware futuro (≥24 GB). *Registrado como decisão operacional desta instalação; o ADR-005 seguirá reservado ao resultado do benchmark (default mode), conforme missão.*

## Onde as coisas moram (WSL ext4 — nada de multi-GB no repo)

| Item | Caminho |
|---|---|
| venv | `~/.venvs/printer3d-ia` (Python 3.11.16) |
| Código TRELLIS (clone) | `~/tools/TRELLIS` @ `main`, commit de 2026-10-27 |
| Pesos | `~/ai-models/trellis/TRELLIS-image-large` |
| Encoder SigLIP (cache HF) | `~/.cache/huggingface/hub/models--google--siglip-so400m-patch14-384` |
| TripoSR (clone) | `~/tools/TripoSR` @ `107cefd` |
| Workdir de geração | `~/printer3d-work/` |

## Passo 1 — venv + torch (Etapa 1)

```text
$ /usr/bin/python3.11 -m venv ~/.venvs/printer3d-ia   → Python 3.11.16, pip 26.3
$ pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu121
Successfully installed ... torch-2.5.1+cu121 torchvision-0.20.1+cu121 triton-3.1.0 ...
$ python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
2.5.1+cu121 True                          ← referência do audit confirmada no venv novo
```

## Passo 2 — deps oficiais do TRELLIS (setup.sh `--basic` + extras)

Instalado via pip (equivalente ao `setup.sh` oficial, adaptado a venv — o script oficial assume conda):

- basic: `pillow imageio imageio-ffmpeg tqdm easydict opencv-python-headless scipy ninja rembg onnxruntime trimesh open3d xatlas pyvista pymeshfix igraph transformers` + `utils3d@9a4eb15` (pin oficial) → todos EXIT=0
- `spconv-cu120 2.3.6` (CUDA 12) → EXIT=0
- `xformers==0.0.28.post3` (índice cu121; backend alternativo) → EXIT=0
- **flash-attn 2.7.4.post1 via wheel PRÉ-COMPILADA oficial** (releases GitHub, `cu12torch2.5cxx11abiFALSE cp311`) → EXIT=0, **sem compilação de ~1h** (degrau (a) da escada atingido por atalho legítimo)

### Desvio real 1 — transformers 5.x incompatível com torch 2.5.1

O `pip install transformers` (unpinned, como no setup.sh oficial) trouxe **5.22.1**, que ao importar emitiu:
```text
[transformers] Disabling PyTorch because PyTorch >= 2.6 is required but found 2.5.1+cu121
```
Sem integração torch, o SigLIP (image encoder do pipeline) não carrega. **Correção:** pin `transformers==4.46.3` (era testada do TRELLIS; traz `huggingface-hub 0.36.2`, `tokenizers 0.20.3`). Verificação: `from transformers import SiglipImageProcessor, SiglipVisionModel` → OK com torch 2.5.1.

### Desvio real 2 — kaolin ausente (FlexiCubes)

`import trellis` falhou com `ModuleNotFoundError: No module named 'kaolin'` (uso em runtime: só `kaolin.utils.testing.check_tensor` em `flexicubes.py`; demais usos são em `examples/`, não importados). **Correção:** wheel oficial da NVIDIA para torch 2.5.1/cu121:
```text
$ pip install kaolin==0.17.0 -f https://nvidia-kaolin.s3.us-east-2.amazonaws.com/torch-2.5.1_cu121.html
Successfully installed kaolin-0.17.0 ... numpy-1.26.4 ...
```
(kaolin força `numpy<2` → numpy rebaixado 2.4.6→1.26.4; compatível com torch 2.5.1.)

**Import final:** `[SPARSE] Backend: spconv, Attention: flash_attn` → `IMPORT_TRELLIS_OK`.

## Passo 3 — pesos

```text
$ huggingface-cli download microsoft/TRELLIS-image-large --local-dir ~/ai-models/trellis/TRELLIS-image-large
EXIT=0 · du -sh → 3.1G    (9 safetensors fp16 + pipeline.json — o "~13GB" do briefing era estimativa; real: 3.1 GB)
```

## Passo 4 — primeira geração ponta a ponta (aceite da etapa)

Input: `~/tools/TRELLIS/assets/example_image/T.png` (MIT) · seed 1 · poller VRAM 1 Hz:

```json
{"mode": "trellis", "model": "microsoft/TRELLIS-image-large", "seed": 1,
 "tempo_load_s": 49.87, "tempo_run_s": 32.42, "tempo_total_s": 85.19,
 "vertices": 296908, "faces": 594134, "watertight_bruto": false,
 "winding_consistent": true, "bbox": [0.8777, 0.4223, 0.9977],
 "erros": ["glb_texturizado: ModuleNotFoundError: No module named 'nvdiffrast'"]}
```

2ª execução (cache quente, mesma seed): load 38,34s · run 29,3s · vértices 296.952 (Δ 0,015% — não-determinismo normal de kernels CUDA; bbox idêntico → **determinismo prático suficiente para benchmark com seed fixa**).

**VRAM (poller 1 Hz, real):**
```text
baseline: 1828 MiB used / 10283 free   →   pico: 11947 MiB used / 164 free   →   pós: ~1089 used
```
**Pico de 97% dos 12.288 MiB.** Consequência vinculante: o guard de VRAM (Etapa 4) exige ≥10.000 MiB livres antes de job TRELLIS; desktop carregado (jogo/aba pesada) pode causar OOM real.

Renders padronizados (Blender 5.0.1 headless, Cycles CPU, câmera/luz fixas): `evidence/fase1/first-generation/preview_a.png` (405 KB) e `preview_b.png` (392 KB). Malha completa (23,8 MB OBJ) permanece em `~/printer3d-work/first-gen/trellis/mesh.obj` — SHA-256 em `evidence/.../mesh-sha256.txt`.

## Escada de fallback — degrau nvdiffrast (GLB texturizado)

Tentativa oficial (`git clone NVlabs/nvdiffrast` + `pip install ~/tools/ext/nvdiffrast`):
```text
ERROR: Failed to build 'file:///home/bruno/tools/ext/nvdiffrast' when getting requirements to build wheel
```
Mesmo instalado, o rasterizador CUDA do nvdiffrast compila em runtime via **nvcc — ausente no WSL** (`which nvcc` vazio; toolkit via `apt` exige sudo → decisão do dono). **Pendência `[!]`: GLB texturizado adiado.** O benchmark segue com mesh pura (OBJ) — o scoring é geométrico (manifold/espessura/vértices), textura não é gate; a galeria usa material cinza neutro.

## Reprodução rápida

```bash
wsl bash -lc '~/.venvs/printer3d-ia/bin/python /mnt/c/.../tools/generator/trellis_runner.py \
  --image <png> --output-dir <dir> --seed 1'   # ATTN_BACKEND=flash-attn, SPCONV_ALGO=native (defaults do runner)
```

## Pendências desta etapa

- `[!]` GLB texturizado (nvdiffrast): exige build deps + nvcc/CUDA toolkit no WSL → sudo/apt (dono decide se vale a pena; não bloqueia benchmark nem gates).
- `[~]` numpy pinado em 1.26.4 (kaolin) — monitorar conflito com libs futuras na Fase 2+.
