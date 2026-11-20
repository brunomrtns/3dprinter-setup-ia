# Pipeline Universal de Pintura Automática PBR (`pipeline/`)

Ferramenta agnóstica de asset para pintar qualquer malha 3D (carros, personagens, criaturas, props) com **BaseColor 8K/4K (JPEG q95)** + **PBR `MetallicRoughness` (2048 PNG)** + **QA automático** + **publicação condicional**, usando **1 config + 1 comando**.

---

## Como pintar qualquer asset novo (3 passos)

### 1. Crie `assets/<id>.json`

O arquivo herda todos os parâmetros aprovados de `pipeline/defaults.json` (`texture_size=2048`, `gutter_px=24`, `cos_lo=0.80`, `cos_hi=0.92`, `w_max=0.80`, `sr_factor=4`, `seed=42`) e sobrescreve apenas o específico do asset.

Existem **3 tiers** de entrada:

#### Tier `"photos"` (múltiplas fotos reais ortogonais — ex.: produto/veículo)
```json
{
  "id": "carro_foxh",
  "variant_id": "mv_b",
  "mesh": "/caminho/para/uv.obj",
  "uv": "/caminho/para/uv.obj",
  "tier": "photos",
  "input_images": ["R1_front.png", "R2_side.png", "R3_back.png", "R2r_right.png"],
  "photo_blend": {
    "views": [
      {"name": "front", "image": "R1_front.png", "init_yaw_deg": 0.0, "init_pitch_deg": 0.0},
      {"name": "left",  "image": "R2_side.png",  "init_yaw_deg": -90.0, "init_pitch_deg": 0.0},
      {"name": "back",  "image": "R3_back.png",  "init_yaw_deg": 180.0, "init_pitch_deg": 0.0},
      {"name": "right", "image": "R2r_right.png","init_yaw_deg": 90.0, "init_pitch_deg": 0.0}
    ]
  },
  "outputs": {
    "mode_8k": "mv_b_8k",
    "mode_4k": "mv_b_4k",
    "glb_names": ["carro_foxh__mv_b_8k.glb", "carro_foxh__mv_b_4k.glb"]
  },
  "qa": { "lap_min": 4000.0, "patch_max_pct": 0.01 }
}
```

#### Tier `"single"` (1 imagem de referência — ex.: personagem, criatura, prop)
```json
{
  "id": "humanoide_dragonborn",
  "variant_id": "pbr",
  "mesh": "/caminho/para/malha.glb",
  "uv": "/caminho/para/malha.glb",
  "tier": "single",
  "input_images": ["/caminho/para/referencia_preproc.png"],
  "outputs": {
    "mode_8k": "pbr_8k",
    "mode_4k": "pbr_4k",
    "glb_names": ["humanoide_dragonborn__pbr_8k.glb", "humanoide_dragonborn__pbr_4k.glb"]
  }
}
```

#### Tier `"none"` (sem foto — gera 4 renders Blender neutros da própria malha)
```json
{
  "id": "meu_prop_sem_foto",
  "variant_id": "pbr",
  "mesh": "/caminho/para/malha.glb",
  "uv": "/caminho/para/malha.glb",
  "tier": "none",
  "input_images": [],
  "outputs": {
    "mode_8k": "pbr_8k",
    "mode_4k": "pbr_4k",
    "glb_names": ["meu_prop_sem_foto__pbr_8k.glb", "meu_prop_sem_foto__pbr_4k.glb"]
  }
}
```

---

### 2. Rode o comando único

```bash
/home/bruno/.venvs/hunyuan/bin/python pipeline/run_asset.py \
  --config assets/<id>.json \
  --out evidence/rtx3060-12gb/pipe_std/<id> \
  --resume \
  --auto-publish
```

**Flags:**
- `--resume`: pula etapas já concluídas cujo `_config_hash` no `report.json` bate com a config atual.
- `--auto-publish`: faz backup de GLBs anteriores (`backup_prev/`), atualiza `manifest.json`, roda `deploy.sh` e valida `HTTP 200` **somente se `qa.json` tiver `overall_pass: true`**.

**Cadeia executada:**
1. `00_preflight` — pré-voo UV (nº de ilhas, área mínima, overlap); se a malha não tiver UV, gera `uv.obj` via `xatlas` preservando 100% da geometria.
2. `01_conditioning` — prepara imagens de referência conforme o `tier`.
3. `02_paint_hunyuan` — `Hunyuan3D-Paint v2-0` (`seed 42`, offload `vae ↔ unet`) + `Real-ESRGAN x4` por vista + **gutter bleed por ilha UV (24px)** + `uv_inpaint`.
4. `03_photo_blend` — apenas `tier == "photos"`: alinhamento silhueta-IoU (gate `IoU >= 0.90`) + blending de detalhes.
5. `04_patch_repair` — reparo genérico 2D (patches claros em regiões escuras + pontos escuros isolados) + coerência 3D em micro-ilhas UV (com guarda fotográfica no tier `"photos"`).
6. `05_trellis_pbr` — `TRELLIS.2-4B` (`Trellis2TexturingPipeline`, `xformers + flex_gemm`, `low_vram=True`) gerando `MetallicRoughness` `2048×2048` PNG sobre o **mesmo layout UV**.
7. `06_pack_glb` — `Real-ESRGAN x4` → BaseColor `8192` e `4096` (JPEG q95, monitor de saturação) + `MetallicRoughness` 2048 PNG → GLBs finais.
8. `07_qa_eval` — renders Blender `Standard + None` (7 vistas + crops padronizados) e geração de `qa.json`.

---

### 3. Leia `qa.json` (interpretação dos gates)

| Gate | Default (`defaults.json`) | O que mede |
|---|---|---|
| `lap_var` | `>= 1200.0` | Variância média do Laplaciano nas 7 vistas renderizadas (nitidez real na malha). |
| `bright_patches` | `<= 0.01%` | % de texels em patches brancos falhos cercados por regiões escuras (meta ~0). |
| `saturation_band` | `[2%, 85%]` | Saturação média HSV da textura final (evita cinza lavado ou supersaturação). |
| `mr_pbr_present` | `true` | Confirma presença do mapa físico `metallicRoughnessTexture` (2048 PNG). |
| `glb_sizes_sane` | `[1, 45] MB` | Garante empacotamento JPEG q95 + MR dentro do orçamento WebGL/VPN. |
| `photo_consistency` | `final_mae < before_mae` | Apenas `tier == "photos"`: MAE médio nas regiões frontais contra fotos reais. |

- **`overall_pass: true`** → elegível para publicação automática (o veredito final visual no viewer continua sendo humano).
- **`overall_pass: false`** → publicação bloqueada automaticamente; versão anterior preservada intacta.
