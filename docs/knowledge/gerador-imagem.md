# Geradores de Imagem 2D (Conceito) — `3dprinter-setup-ia` & CONCERTO

> Referência técnica dos dois geradores locais de conceito 2D operacionais na RTX 3060 12 GB (WSL), sob a **Lei 8 / ADR-010** (disco único, zero downloads fora da porta do repo) e **guard de VRAM de 10.000 MiB**.

---

## 1. Os 2 Geradores Oficiais

| Gerador | Status | Backend / Venv | Peso no Inventário | Tempo médio (`768×768`) | Quando usar |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **`FLUX.1-dev FP8`** | **Novo candidato principal** (em A/B vs SDXL-Turbo) | ComfyUI headless (`--lowvram`) · `~/.venvs/comfyui` · `tools/generator/concept_flux.py` | `~/tools/comfyui/models/checkpoints/flux1-dev-fp8.safetensors` (`Comfy-Org/flux1-dev`, all-in-one FP8 + CLIP-L + T5-XXL + VAE, ~16,06 GiB) | ~45–75 s (20 steps) | **Heróis, NPCs, props complexos e anatomia/briefing detalhado** (ex.: Dez com 4 braços + macacão remendado, Porca flutuante limpa, props hero do Caldeiral). Aderência de prompt muito superior ao SDXL-Turbo. |
| **`SDXL-Turbo`** | **Legado rápido** (validado em Kit 4.0 e Batch-1) | Diffusers CUDA · `~/.venvs/hunyuan` · `game-concerto/tools/art/ai_generator/concept_bridge.py` | `~/.cache/huggingface/hub/models--stabilityai--sdxl-turbo` (`6,46 GiB`) | ~20 s (4 steps) | Texturas tileáveis rápidas (`--mode tileable`), rascunhos de silhueta simples, ícones e props geométricos simples sem composição anatômica complexa. |

---

## 2. Política de Licença (Obrigatória no ADR-011)

- **`FLUX.1-dev`:** licença **não-comercial** da Black Forest Labs (BFL).
  - Uso atual (vertical slice / projeto pessoal do dono): **OK**.
  - Se o CONCERTO evoluir para lançamento comercial: migração direta e barata para **`FLUX.1-schnell` (Apache 2.0)** no mesmo workflow ComfyUI (`concept_flux.py --ckpt flux1-schnell-fp8.safetensors --steps 4 --guidance 1.0`) ou aquisição de licença comercial BFL.
- **`SDXL-Turbo`:** licença Stability AI Community (uso comercial permitido abaixo do teto de receita comunitária).

---

## 3. Instalação pela Porta do Repo & Uso Headless

Instalação única (ComfyUI + venv dedicada + download resumível + SHA-256):
```bash
bash tools/setup/install_comfyui.sh --download-flux
```

Geração de 1 imagem com provenance automática (`<saida>.provenance.json` + SHA-256 + pico de VRAM):
```bash
~/.venvs/comfyui/bin/python tools/generator/concept_flux.py \
  --prompt "weathered brass clockwork valve pedestal, isolated, pure white background, 3/4 view" \
  --seed 42 --size 768 --steps 20 --guidance 3.5 \
  --out /tmp/valvula_flux.png
```

Geração em lote (1 único boot do ComfyUI headless, encerrando e liberando 100% da VRAM ao fim):
```bash
~/.venvs/comfyui/bin/python tools/generator/concept_flux.py --batch-json jobs.json
```

---

## 4. Guard de VRAM (10.000 MiB na RTX 3060 12 GB)

- `concept_flux.py` sobe o ComfyUI com `--lowvram` (offload automático por bloco entre RAM e VRAM) e monitora `nvidia-smi` a 1 Hz durante toda a inferência.
- Regra de serialização: nunca rodar `concept_flux.py` em paralelo com `TripoSG`, `Hunyuan3D-Paint` ou `TRELLIS.2`.
- **Plano B técnico:** se o `flux1-dev-fp8` exceder `10.000 MiB` de VRAM mesmo com `--lowvram`, registrar `[!]` e alternar para `flux1-schnell-fp8` / `--novram` conforme `ADR-011`.
