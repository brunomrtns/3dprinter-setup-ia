# ADR-011 — Gerador de Imagem 2D do Pipeline (`FLUX.1-dev FP8` provisório + Provenance Obrigatória)

- **Data:** 2026-11-22 (ratificado 2026-11-23)
- **Status:** **OFICIAL** (`FLUX.1-dev FP8` = gerador oficial 2D do pipeline; A/B `20/20` vs `14/20`)
- **Contexto:** Na Fase C5 do CONCERTO (`RUN mega_v3`), o `stabilityai/sdxl-turbo` (4 steps) mostrou perda severa de aderência a briefings complexos (ex.: omitiu volante vermelho na válvula, tampo de madeira na bancada, corneta na sirene, e os 4 braços + macacão do herói Dez).

---

## 1. Resultado do A/B Controlado (`2026-11-22_ab_gerador_imagem`)

Comparação justa nos mesmos 4 prompts e mesmas seeds do Batch-1 sob o checklist duro de entrada (5 critérios × 4 props = 20 pontos):
- **`stabilityai/sdxl-turbo`** (`4 steps`, `~/.venvs/hunyuan`): **14 / 20**
- **`Comfy-Org/flux1-dev-fp8`** (`20 steps`, `guidance 3.5`, ComfyUI headless `--lowvram --reserve-vram 3.5`, `~/.venvs/comfyui`): **20 / 20** (4/4 dentro do guard de 10.000 MiB: pico `9.743–9.828 MiB`, `42–62 s/imagem`).

---

## 2. Decisão

1. **Gerador principal provisório para conceitos 2D (heróis, NPCs e props hero):** **`FLUX.1-dev FP8`** via `tools/generator/concept_flux.py` (ComfyUI headless, `--lowvram --reserve-vram 3.5`, guard 10 GB, logger VRAM 1 Hz).
2. **Papel do `SDXL-Turbo` (legado mantido no inventário):** mantido para texturas tileáveis rápidas (`--mode tileable`), ícones simples e rascunhos de baixa latência.
3. **Regra vinculante de procedência 2D:** **nenhum PNG entra no pipeline image→3D sem sidecar `provenance.json`** contendo modelo, arquivo de pesos + SHA-256, seed, prompt, pico de VRAM e timestamp.

---

## 3. Condição de Licença (Black Forest Labs)

- `FLUX.1-dev` possui licença **não-comercial** da Black Forest Labs (BFL).
- Uso atual (projeto pessoal / vertical slice do CONCERTO): **permitido**.
- **Se o projeto evoluir para lançamento comercial:** migração direta no mesmo runner `concept_flux.py` para **`FLUX.1-schnell` (Apache 2.0)** ou aquisição de licença comercial BFL.
- **Plano B técnico (VRAM):** caso algum job estoure o guard de `10.000 MiB`, alternar para `--novram` ou `FLUX.1-schnell FP8` (registrado no inventário Lei 8).
