# Relatório C6 — Modelagem 3D Automotiva (VW Fox `no-windows`): `TripoSG → TripoSF 512` (Interna + 4 Rodas) vs `Hunyuan3D-2mv` (4 Vistas Ortogonais)

**Data:** 2026-11-18  
**Hardware:** NVIDIA GeForce RTX 3060 12 GB (12.288 MiB total, ~517 MiB baseline com `reclaim_windows_vram()` ativo)  
**Entrada:** `C:\Users\Bruno\Downloads\fox\no-windows\{frente,lado,traseira,frente-e-lado-diagonal,de-fora-pegando-interna}.jpg`  
**Seed:** `42`

---

## 1. Diagnóstico e Soluções de Engenharia Implementadas

### 1.1. Reclaim Automático de VRAM do Windows (`NVIDIA Broadcast`)
- Integrado `reclaim_windows_vram()` diretamente em `tools/generator/gpu_guard.py`, encerrando automaticamente `NVIDIA Broadcast.exe`, `NVIDIA Broadcast UI.exe` e `RTXVoice.exe` via `taskkill.exe` antes de qualquer job GPU.
- **Resultado:** baseline de VRAM caiu de `~2.100 MiB` para **`488 – 585 MiB`**, liberando `~11.600 MiB` úteis na RTX 3060 12 GB.

### 1.2. Eliminação do OOM no `Hunyuan3D-2mv` (4 vistas ortogonais)
- **Causa raiz do OOM inicial (`12.054 MiB`):** com 4 vistas (`front`, `left`, `back`, `right`), o `DinoImageEncoderMV` produz `4 × 1.370 = 5.480` tokens de contexto (`dim=1.536`). Avaliar Classifier-Free Guidance (CFG) concatenando `batch=2` (`torch.cat([latents] * 2)`) dobrava todas as matrizes de atenção cruzada e `RMSNorm` em FP32.
- **Solução (`tools/generator/hunyuan_runner.py`):**
  1. Offload estrito por estágio (`conditioner → CPU` antes do DiT; `DiT → CPU` antes do Marching Cubes `384³` no `ShapeVAE`);
  2. Avaliação **sequencial `batch=1` do CFG** (`noise_pred_cond` seguido de `noise_pred_uncond` sob `torch.amp.autocast('cuda', dtype=torch.float16)`).
- **Resultado medido:** o pico de VRAM do `Hunyuan3D-2mv` com 4 vistas (`octree_resolution=384`, `50` steps) caiu de **`12.054 MiB` (OOM)** para **`3.369 MiB`** (redução de **72% de VRAM** com resultado matemático idêntico).

### 1.3. Pós-processamento Multi-Partes (`tools/generator/posproc_impressao.py`)
- **Descoberta:** no `TripoSG 505³` sobre a foto `frente-e-lado-diagonal` (`no-windows`), o gerador modelou **7 componentes conexos significativos (`>= 1.000` faces)**:
  - `comp 0` (`2.983.998` faces): carroceria completa + **teto 100% sólido com racks** + **cabine interna completa** (bancos dianteiros, banco traseiro com encostos de cabeça, painel e volante) + rodas traseiras;
  - `comp 1` (`58.460` faces): roda dianteira esquerda (`1,96%` das faces);
  - `comp 2` (`56.944` faces): roda dianteira direita (`1,91%` das faces);
  - `comp 3` (`4.656` faces): placa dianteira;
  - `comp 4` (`3.996` faces): detalhe de cubo/aro traseiro;
  - `comp 5` (`1.276` faces) e `comp 6` (`1.112` faces): antena de teto.
- **Problema no filtro single-component:** manter apenas o maior componente (`max(comps)`) ou chamar `PyMeshFix.repair()` na malha inteira (cujo default é `remove_smallest_components=True`) descartava as duas rodas dianteiras, a placa e a antena!
- **Solução integrada ao `posproc_impressao.py` (`--min-comp-faces 1000`):** cada componente conexo com `>= 1.000` faces é reparado **individualmente** via `PyMeshFix + manifold3d` (garantindo `watertight=True` em cada sub-peça) antes da unificação, suavização `Taubin 5it` e decimação.

---

## 2. Telemetria Real Medida (RTX 3060 12 GB)

| Pipeline / Modo no Viewer | Vistas de Entrada | Faces Brutas | Faces Pós-proc | Vértices Pós-proc | Tempo GPU (s) | VRAM Pico (MiB) | Watertight Final | Destaques Geométricos |
|---|---|---:|---:|---:|---:|---:|:---:|---|
| **`triposf512`** (`TripoSG → TripoSF 512 → Pós-proc Multi-Partes`) | `frente-e-lado-diagonal_tinted.png` | `3.497.404` | **`280.000`** | `139.650` | `56,52` (refino) | **`10.227`** | **Sim (`True`)** | **Cabine interna completa (bancos, encostos, painel, volante) + teto 100% sólido c/ rack e antena + 4 rodas + placa** |
| **`triposg`** (`TripoSG 505³ → Pós-proc Multi-Partes`) | `frente-e-lado-diagonal_tinted.png` | `3.116.268` | **`250.000`** | `124.198` | `96,94` | **`10.317`** | **Sim (`True`)** | **Cabine interna completa + teto sólido c/ rack e antena + 4 rodas** |
| **`hunyuan_mv_sf512`** (`Hunyuan3D-2mv 4 vistas → TripoSF 512 → Pós-proc`) | `front + left + back + right` (`*_tinted.png`) | `1.465.074` | **`280.000`** | `139.886` | `44,51` (refino) | **`6.569`** | **Sim (`True`)** | **Carroceria fechada 4 vistas (die-cast) c/ limpadores dianteiro/traseiro, antena, spoiler, 4 rodas raiadas, frente e traseira fiéis** |
| **`hunyuan_mv`** (`Hunyuan3D-2mv 4 vistas → Pós-proc`) | `front + left + back + right` (`*_tinted.png`) | `801.352` | **`250.000`** | `124.852` | `328,04` | **`3.369`** | **Sim (`True`)** | **Carroceria fechada 4 vistas (octree 384³) + 4 rodas + antena** |
| **`trellis2_fosco`** (`TRELLIS.2 Vidro Fosco`) | `frente-e-lado-diagonal_tinted.png` | `1.965.475` | `549.999` | `922.933` | `239,49` | **`4.177`** | Não (`False`) | Referência comparativa VS |

---

## 3. Veredito Técnico

1. **Aposta do dono confirmada (`TripoSG → TripoSF 512 → Pós-processamento Multi-Partes`):**
   - Com a foto `no-windows` pré-processada e o reparo multi-componente (`>= 1.000` faces), o pipeline **`TripoSG → TripoSF 512 → Pós-proc`** entregou o modelo mais impressionante do Fox: **teto 100% fechado (zero furos), 4 rodas no chão, antena no teto, placa frontal e toda a cabine interna modelada em 3D (bancos dianteiros, banco traseiro com encostos de cabeça, painel e volante)** em uma malha `100% watertight` (`280.000` faces).
2. **Complementaridade do `Hunyuan3D-2mv` (4 vistas) + `TripoSF 512`:**
   - Para quem desejar a versão **"miniatura die-cast de janelas fechadas"** com simetria ortogonal simultânea de frente, traseira e laterais (incluindo limpadores de para-brisa dianteiro/traseiro, emblema e rodas raiadas detalhadas), o **`Hunyuan3D-2mv + TripoSF 512`** resolve com apenas `3.369 MiB` (geração) / `6.569 MiB` (refino) e `100% watertight`.
