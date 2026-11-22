# Inventário de Pesos Locais (Lei 8 / ADR-010)

> Gerado automaticamente por `tools/generator/inventario_pesos.py` em **2026-11-22 22:01 UTC** (somente leitura — zero downloads).
> **Total inventariado:** **45 arquivos** (`>= 5 MiB`) · **61.68 GiB** · **Duplicidades por SHA-256:** **2**.

## Resumo por Família

| Família | Arquivos | Tamanho Total | Venv / Runner Principal |
|---|---:|---:|---|
| DINOv2 | 1 | 1.13 GiB | `~/.venvs/printer3d-ia / hunyuan / trellis2` |
| DINOv3 (TRELLIS.2) | 1 | 1.13 GiB | `~/.venvs/trellis2 · pipeline/retexture_trellis.py` |
| faster-whisper-large-v3 | 1 | 2.88 GiB | `cache HF compartilhado` |
| faster-whisper-tiny | 1 | 72.0 MiB | `cache HF compartilhado` |
| Hunyuan3D (dit/paint/mv) | 8 | 12.57 GiB | `~/.venvs/hunyuan · pipeline/paint_quality.py & hunyuan_runner.py` |
| rembg (BiRefNet) | 1 | 423.9 MiB | `~/.venvs/printer3d-ia · tools/generator/preprocess_input.py` |
| rembg (u2net/isnet) | 1 | 167.8 MiB | `~/.venvs/printer3d-ia · tools/generator/preprocess_input.py` |
| rembg / BriaRMBG | 7 | 1.73 GiB | `~/.venvs/triposg & ~/.venvs/printer3d-ia` |
| SDXL-Turbo (2D) | 4 | 6.46 GiB | `~/.venvs/hunyuan · concept_bridge (game-concerto)` |
| siglip-so400m-patch14-384 | 1 | 3.27 GiB | `cache HF compartilhado` |
| TRELLIS (v1) | 1 | 140.8 MiB | `~/.venvs/printer3d-ia · legado/descontinuado` |
| TRELLIS.2 | 11 | 16.67 GiB | `~/.venvs/trellis2 · pipeline/retexture_trellis.py (MR PBR)` |
| TripoSF | 1 | 682.2 MiB | `~/venvs/triposf · tools/generator/triposf/triposf_runner.py` |
| TripoSG | 3 | 7.40 GiB | `~/.venvs/triposg · tools/generator/triposg_runner.py` |
| TripoSR | 1 | 1.56 GiB | `~/.venvs/printer3d-ia · tools/generator/triposr_runner.py` |
| UniRig | 2 | 5.42 GiB | `cache HF compartilhado` |

## Duplicidades Detectadas (mesmo SHA-256 em caminhos físicos distintos)

- `dcb2e45127cccbf1…` (1.13 GiB): `~/.cache/huggingface/hub/models--camenduru--dinov3-vitl16-pretrain-lvd1689m/snapshots/3c276edd87d6f6e569ff0c4400e086807d0f3881/model.safetensors`, `~/tools/TRELLIS.2/MODELS/dinov3/model.safetensors`
- `9ab37426bf4de056…` (423.9 MiB): `~/.cache/huggingface/hub/models--ZhengPeng7--BiRefNet/snapshots/e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4/model.safetensors`, `~/tools/TRELLIS.2/MODELS/RMBG-2.0/model.safetensors`

## Tabela Completa de Pesos (Read-Only + SHA-256)

| Família | Caminho | Origem / HF Repo | Tamanho | SHA-256 (16 hex) | Venv / Runner |
|---|---|---|---:|---|---|
| DINOv2 | `~/.cache/torch/hub/checkpoints/dinov2_vitl14_reg4_pretrain.pth` | `facebook/dinov2*` | 1.13 GiB | `36e4deffbaef061a` | `~/.venvs/printer3d-ia / hunyuan / trellis2` |
| DINOv3 (TRELLIS.2) | `~/.cache/huggingface/hub/models--camenduru--dinov3-vitl16-pretrain-lvd1689m/snapshots/3c276edd87d6f6e569ff0c4400e086807d0f3881/model.safetensors` | `camenduru/dinov3-vitl16-pretrain-lvd1689m` | 1.13 GiB | `dcb2e45127cccbf1` | `~/.venvs/trellis2 · pipeline/retexture_trellis.py` |
| faster-whisper-large-v3 | `~/.cache/huggingface/hub/models--Systran--faster-whisper-large-v3/snapshots/edaa852ec7e145841d8ffdb056a99866b5f0a478/model.bin` | `Systran/faster-whisper-large-v3` | 2.88 GiB | `69f74147e3334731` | `cache HF compartilhado` |
| faster-whisper-tiny | `~/.cache/huggingface/hub/models--Systran--faster-whisper-tiny/snapshots/d90ca5fe260221311c53c58e660288d3deb8d356/model.bin` | `Systran/faster-whisper-tiny` | 72.0 MiB | `dcb76c6586fc06cb` | `cache HF compartilhado` |
| Hunyuan3D (dit/paint/mv) | `~/.cache/huggingface/hub/models--tencent--Hunyuan3D-2/snapshots/9cd649ba6913f7a852e3286bad86bfa9a2d83dcf/hunyuan3d-paint-v2-0/unet/diffusion_pytorch_model.bin` | `tencent/Hunyuan3D-2*` | 3.41 GiB | `2efb4438e649e1ce` | `~/.venvs/hunyuan · pipeline/paint_quality.py & hunyuan_runner.py` |
| Hunyuan3D (dit/paint/mv) | `~/.cache/huggingface/hub/models--tencent--Hunyuan3D-2/snapshots/9cd649ba6913f7a852e3286bad86bfa9a2d83dcf/hunyuan3d-paint-v2-0/unet/diffusion_pytorch_model.safetensors` | `tencent/Hunyuan3D-2*` | 3.41 GiB | `1c5ce434ba976b30` | `~/.venvs/hunyuan · pipeline/paint_quality.py & hunyuan_runner.py` |
| Hunyuan3D (dit/paint/mv) | `~/.cache/huggingface/hub/models--tencent--Hunyuan3D-2/snapshots/9cd649ba6913f7a852e3286bad86bfa9a2d83dcf/hunyuan3d-delight-v2-0/unet/diffusion_pytorch_model.safetensors` | `tencent/Hunyuan3D-2*` | 3.23 GiB | `0ce61d15a43d11ba` | `~/.venvs/hunyuan · pipeline/paint_quality.py & hunyuan_runner.py` |
| Hunyuan3D (dit/paint/mv) | `~/.cache/huggingface/hub/models--tencent--Hunyuan3D-2/snapshots/9cd649ba6913f7a852e3286bad86bfa9a2d83dcf/hunyuan3d-paint-v2-0/text_encoder/pytorch_model.bin` | `tencent/Hunyuan3D-2*` | 1.27 GiB | `c3e254d7b6135349` | `~/.venvs/hunyuan · pipeline/paint_quality.py & hunyuan_runner.py` |
| Hunyuan3D (dit/paint/mv) | `~/.cache/huggingface/hub/models--tencent--Hunyuan3D-2/snapshots/9cd649ba6913f7a852e3286bad86bfa9a2d83dcf/hunyuan3d-delight-v2-0/text_encoder/model.safetensors` | `tencent/Hunyuan3D-2*` | 649.3 MiB | `bc1827c465450322` | `~/.venvs/hunyuan · pipeline/paint_quality.py & hunyuan_runner.py` |
| Hunyuan3D (dit/paint/mv) | `~/.cache/huggingface/hub/models--tencent--Hunyuan3D-2/snapshots/9cd649ba6913f7a852e3286bad86bfa9a2d83dcf/hunyuan3d-paint-v2-0/vae/diffusion_pytorch_model.bin` | `tencent/Hunyuan3D-2*` | 319.2 MiB | `1b4889b6b1d4ce7a` | `~/.venvs/hunyuan · pipeline/paint_quality.py & hunyuan_runner.py` |
| Hunyuan3D (dit/paint/mv) | `~/.cache/huggingface/hub/models--tencent--Hunyuan3D-2/snapshots/9cd649ba6913f7a852e3286bad86bfa9a2d83dcf/hunyuan3d-delight-v2-0/vae/diffusion_pytorch_model.safetensors` | `tencent/Hunyuan3D-2*` | 159.6 MiB | `3e4c08995484ee61` | `~/.venvs/hunyuan · pipeline/paint_quality.py & hunyuan_runner.py` |
| Hunyuan3D (dit/paint/mv) | `~/.cache/huggingface/hub/models--tencent--Hunyuan3D-2/snapshots/9cd649ba6913f7a852e3286bad86bfa9a2d83dcf/hunyuan3d-paint-v2-0/vae/diffusion_pytorch_model.safetensors` | `tencent/Hunyuan3D-2*` | 159.6 MiB | `abcec86e499e1ce9` | `~/.venvs/hunyuan · pipeline/paint_quality.py & hunyuan_runner.py` |
| rembg (BiRefNet) | `~/.cache/huggingface/hub/models--ZhengPeng7--BiRefNet/snapshots/e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4/model.safetensors` | `ZhengPeng7/BiRefNet` | 423.9 MiB | `9ab37426bf4de056` | `~/.venvs/printer3d-ia · tools/generator/preprocess_input.py` |
| rembg (u2net/isnet) | `~/.rembg/models/u2net/u2net.onnx` | `danielgatis/rembg` | 167.8 MiB | `8d10d2f3bb75ae3b` | `~/.venvs/printer3d-ia · tools/generator/preprocess_input.py` |
| rembg / BriaRMBG | `~/.rembg/models/bria-rmbg/bria-rmbg.onnx` | `briaai/RMBG-1.4 / 2.0` | 976.9 MiB | `5b486f08200f513f` | `~/.venvs/triposg & ~/.venvs/printer3d-ia` |
| rembg / BriaRMBG | `~/.cache/huggingface/hub/models--briaai--RMBG-1.4/snapshots/da1d078376e6691105a5530a374a010627fc60b5/model.pth` | `briaai/RMBG-1.4 / 2.0` | 168.5 MiB | `893c16c340b1ddaf` | `~/.venvs/triposg & ~/.venvs/printer3d-ia` |
| rembg / BriaRMBG | `~/.cache/huggingface/hub/models--briaai--RMBG-1.4/snapshots/da1d078376e6691105a5530a374a010627fc60b5/pytorch_model.bin` | `briaai/RMBG-1.4 / 2.0` | 168.4 MiB | `59569acdb281ac9f` | `~/.venvs/triposg & ~/.venvs/printer3d-ia` |
| rembg / BriaRMBG | `~/.cache/huggingface/hub/models--briaai--RMBG-1.4/snapshots/da1d078376e6691105a5530a374a010627fc60b5/model.safetensors` | `briaai/RMBG-1.4 / 2.0` | 168.2 MiB | `46ef7fe46f2ae284` | `~/.venvs/triposg & ~/.venvs/printer3d-ia` |
| rembg / BriaRMBG | `~/.cache/huggingface/hub/models--briaai--RMBG-1.4/snapshots/da1d078376e6691105a5530a374a010627fc60b5/onnx/model.onnx` | `briaai/RMBG-1.4 / 2.0` | 168.0 MiB | `8cafcf770b06757c` | `~/.venvs/triposg & ~/.venvs/printer3d-ia` |
| rembg / BriaRMBG | `~/.cache/huggingface/hub/models--briaai--RMBG-1.4/snapshots/da1d078376e6691105a5530a374a010627fc60b5/onnx/model_fp16.onnx` | `briaai/RMBG-1.4 / 2.0` | 84.1 MiB | `9fdfdb41866d872e` | `~/.venvs/triposg & ~/.venvs/printer3d-ia` |
| rembg / BriaRMBG | `~/.cache/huggingface/hub/models--briaai--RMBG-1.4/snapshots/da1d078376e6691105a5530a374a010627fc60b5/onnx/model_quantized.onnx` | `briaai/RMBG-1.4 / 2.0` | 42.3 MiB | `a6648479275dfd0e` | `~/.venvs/triposg & ~/.venvs/printer3d-ia` |
| SDXL-Turbo (2D) | `~/.cache/huggingface/hub/models--stabilityai--sdxl-turbo/snapshots/71153311d3dbb46851df1931d3ca6e939de83304/unet/diffusion_pytorch_model.fp16.safetensors` | `stabilityai/sdxl-turbo` | 4.78 GiB | `48fa46161a745f48` | `~/.venvs/hunyuan · concept_bridge (game-concerto)` |
| SDXL-Turbo (2D) | `~/.cache/huggingface/hub/models--stabilityai--sdxl-turbo/snapshots/71153311d3dbb46851df1931d3ca6e939de83304/text_encoder_2/model.fp16.safetensors` | `stabilityai/sdxl-turbo` | 1.29 GiB | `ec310df2af79c318` | `~/.venvs/hunyuan · concept_bridge (game-concerto)` |
| SDXL-Turbo (2D) | `~/.cache/huggingface/hub/models--stabilityai--sdxl-turbo/snapshots/71153311d3dbb46851df1931d3ca6e939de83304/text_encoder/model.fp16.safetensors` | `stabilityai/sdxl-turbo` | 234.7 MiB | `660c6f5b1abae9dc` | `~/.venvs/hunyuan · concept_bridge (game-concerto)` |
| SDXL-Turbo (2D) | `~/.cache/huggingface/hub/models--stabilityai--sdxl-turbo/snapshots/71153311d3dbb46851df1931d3ca6e939de83304/vae/diffusion_pytorch_model.fp16.safetensors` | `stabilityai/sdxl-turbo` | 159.6 MiB | `02ee4bd18e5d16e7` | `~/.venvs/hunyuan · concept_bridge (game-concerto)` |
| siglip-so400m-patch14-384 | `~/.cache/huggingface/hub/models--google--siglip-so400m-patch14-384/snapshots/9fdffc58afc957d1a03a25b10dba0329ab15c2a3/model.safetensors` | `google/siglip-so400m-patch14-384` | 3.27 GiB | `ea2abad2b7f8a9c1` | `cache HF compartilhado` |
| TRELLIS (v1) | `~/.cache/huggingface/hub/models--microsoft--TRELLIS-image-large/snapshots/25e0d31ffbebe4b5a97464dd851910efc3002d96/ckpts/ss_dec_conv3d_16l8_fp16.safetensors` | `microsoft/TRELLIS-image-large` | 140.8 MiB | `1c76d4a40519aa2d` | `~/.venvs/printer3d-ia · legado/descontinuado` |
| TRELLIS.2 | `~/.cache/huggingface/hub/models--microsoft--TRELLIS.2-4B/snapshots/af44b45f2e35a493886929c6d786e563ec68364d/ckpts/slat_flow_imgshape2tex_dit_1_3B_1024_bf16.safetensors` | `microsoft/TRELLIS.2-4B` | 2.41 GiB | `580401269059a339` | `~/.venvs/trellis2 · pipeline/retexture_trellis.py (MR PBR)` |
| TRELLIS.2 | `~/.cache/huggingface/hub/models--microsoft--TRELLIS.2-4B/snapshots/af44b45f2e35a493886929c6d786e563ec68364d/ckpts/slat_flow_imgshape2tex_dit_1_3B_512_bf16.safetensors` | `microsoft/TRELLIS.2-4B` | 2.41 GiB | `8371aa1c5d13be79` | `~/.venvs/trellis2 · pipeline/retexture_trellis.py (MR PBR)` |
| TRELLIS.2 | `~/.cache/huggingface/hub/models--microsoft--TRELLIS.2-4B/snapshots/af44b45f2e35a493886929c6d786e563ec68364d/ckpts/slat_flow_img2shape_dit_1_3B_1024_bf16.safetensors` | `microsoft/TRELLIS.2-4B` | 2.41 GiB | `07cd0596f634c5ad` | `~/.venvs/trellis2 · pipeline/retexture_trellis.py (MR PBR)` |
| TRELLIS.2 | `~/.cache/huggingface/hub/models--microsoft--TRELLIS.2-4B/snapshots/af44b45f2e35a493886929c6d786e563ec68364d/ckpts/slat_flow_img2shape_dit_1_3B_512_bf16.safetensors` | `microsoft/TRELLIS.2-4B` | 2.41 GiB | `ec5e0917ef9b7e25` | `~/.venvs/trellis2 · pipeline/retexture_trellis.py (MR PBR)` |
| TRELLIS.2 | `~/.cache/huggingface/hub/models--microsoft--TRELLIS.2-4B/snapshots/af44b45f2e35a493886929c6d786e563ec68364d/ckpts/ss_flow_img_dit_1_3B_64_bf16.safetensors` | `microsoft/TRELLIS.2-4B` | 2.41 GiB | `ca01377c485bec41` | `~/.venvs/trellis2 · pipeline/retexture_trellis.py (MR PBR)` |
| TRELLIS.2 | `~/tools/TRELLIS.2/MODELS/dinov3/model.safetensors` | `microsoft/TRELLIS.2-4B` | 1.13 GiB | `dcb2e45127cccbf1` | `~/.venvs/trellis2 · pipeline/retexture_trellis.py (MR PBR)` |
| TRELLIS.2 | `~/.cache/huggingface/hub/models--microsoft--TRELLIS.2-4B/snapshots/af44b45f2e35a493886929c6d786e563ec68364d/ckpts/shape_dec_next_dc_f16c32_fp16.safetensors` | `microsoft/TRELLIS.2-4B` | 904.6 MiB | `e3b718d3e43e4f87` | `~/.venvs/trellis2 · pipeline/retexture_trellis.py (MR PBR)` |
| TRELLIS.2 | `~/.cache/huggingface/hub/models--microsoft--TRELLIS.2-4B/snapshots/af44b45f2e35a493886929c6d786e563ec68364d/ckpts/tex_dec_next_dc_f16c32_fp16.safetensors` | `microsoft/TRELLIS.2-4B` | 904.5 MiB | `97ea69addea2ecd9` | `~/.venvs/trellis2 · pipeline/retexture_trellis.py (MR PBR)` |
| TRELLIS.2 | `~/.cache/huggingface/hub/models--microsoft--TRELLIS.2-4B/snapshots/af44b45f2e35a493886929c6d786e563ec68364d/ckpts/shape_enc_next_dc_f16c32_fp16.safetensors` | `microsoft/TRELLIS.2-4B` | 676.0 MiB | `f37c5ff5b983b68e` | `~/.venvs/trellis2 · pipeline/retexture_trellis.py (MR PBR)` |
| TRELLIS.2 | `~/.cache/huggingface/hub/models--microsoft--TRELLIS.2-4B/snapshots/af44b45f2e35a493886929c6d786e563ec68364d/ckpts/tex_enc_next_dc_f16c32_fp16.safetensors` | `microsoft/TRELLIS.2-4B` | 676.0 MiB | `dd109f75f84b90fa` | `~/.venvs/trellis2 · pipeline/retexture_trellis.py (MR PBR)` |
| TRELLIS.2 | `~/tools/TRELLIS.2/MODELS/RMBG-2.0/model.safetensors` | `microsoft/TRELLIS.2-4B` | 423.9 MiB | `9ab37426bf4de056` | `~/.venvs/trellis2 · pipeline/retexture_trellis.py (MR PBR)` |
| TripoSF | `~/tools/TripoSF/ckpts/pretrained_TripoSFVAE_256i1024o.safetensors` | `VAST-AI/TripoSF` | 682.2 MiB | `7aa6e79a46cd3589` | `~/venvs/triposf · tools/generator/triposf/triposf_runner.py` |
| TripoSG | `~/.cache/huggingface/hub/models--VAST-AI--TripoSG/snapshots/2c1c516d22d58db486a058d98d31bb6177344e06/transformer/diffusion_pytorch_model.safetensors` | `VAST-AI/TripoSG` | 5.36 GiB | `9192b5923f7b605b` | `~/.venvs/triposg · tools/generator/triposg_runner.py` |
| TripoSG | `~/.cache/huggingface/hub/models--VAST-AI--TripoSG/snapshots/2c1c516d22d58db486a058d98d31bb6177344e06/image_encoder_dinov2/model.safetensors` | `VAST-AI/TripoSG` | 1.13 GiB | `399fba97a95f22c3` | `~/.venvs/triposg · tools/generator/triposg_runner.py` |
| TripoSG | `~/.cache/huggingface/hub/models--VAST-AI--TripoSG/snapshots/2c1c516d22d58db486a058d98d31bb6177344e06/vae/diffusion_pytorch_model.safetensors` | `VAST-AI/TripoSG` | 925.7 MiB | `a2e667c24927a5a3` | `~/.venvs/triposg · tools/generator/triposg_runner.py` |
| TripoSR | `~/.cache/huggingface/hub/models--stabilityai--TripoSR/snapshots/5b521936b01fbe1890f6f9baed0254ab6351c04a/model.ckpt` | `stabilityai/TripoSR` | 1.56 GiB | `429e2c6b22a09239` | `~/.venvs/printer3d-ia · tools/generator/triposr_runner.py` |
| UniRig | `~/.cache/huggingface/hub/models--VAST-AI--UniRig/snapshots/36842e2b5947e9e60f89275b83208c8e74071c63/skin/articulation-xl/model.ckpt` | `VAST-AI/UniRig` | 4.07 GiB | `9d40cf42fb9d4c10` | `cache HF compartilhado` |
| UniRig | `~/.cache/huggingface/hub/models--VAST-AI--UniRig/snapshots/36842e2b5947e9e60f89275b83208c8e74071c63/skeleton/articulation-xl_quantization_256/model.ckpt` | `VAST-AI/UniRig` | 1.34 GiB | `d8cf9b42d56e7bc3` | `cache HF compartilhado` |

## Regra Operacional (ADR-010 — Lei 8)

1. Antes de baixar qualquer peso novo, execute `python3 tools/generator/inventario_pesos.py` e confira esta tabela.
2. Se o peso já existir no disco, reutilize via cache HF compartilhado (`~/.cache/huggingface/hub/`) ou symlink — **nunca crie uma segunda cópia física**.
3. Todo novo peso autorizado pelo dono deve ser registrado aqui imediatamente após o download.
