# TripoSR no venv printer3d-ia — notas de instalação (outputs reais)

**Data:** 2026-11-03 · Clone: `~/tools/TripoSR` @ `107cefd` (2026-06-04) · Pesos: `stabilityai/TripoSR` (cache HF)

## Deps

- `requirements.txt` oficial pinna `transformers==4.35.0`, `trimesh==4.0.5` etc. — **conflito com TRELLIS** no mesmo venv. Verificação do código real (`tsr/`): **transformers não é importado** (o encoder CLIP vem embutido no `model.ckpt`); trimesh 5.2.0 funciona. Instalado apenas `omegaconf==2.3.0` (+antlr4) — sem pins conflitantes. `einops`/`rembg`/`imageio`/`xatlas` já presentes via TRELLIS basic.
- `gradio` ignorado (runner headless não usa).

## torchmcubes — escada de fallback (documentada)

1. **Tentativa oficial:** `pip install git+https://github.com/tatsy/torchmcubes.git` → **EXIT=1**, "Encountered error while generating package metadata" (extensão CUDA/C++ exige nvcc, ausente no WSL — log: `torchmcubes-build.log`).
2. **Backend alternativo:** shim `torchmcubes` sobre `skimage.measure.marching_cubes` (já no venv), em `~/printer3d-work/shim/torchmcubes/`, injetado **via PYTHONPATH apenas nos runs TripoSR** (nunca instalado no venv — não polui TRELLIS). Semântica idêntica à esperada por `tsr/models/isosurface.py` (verts em coords de grid, faces int64).
   - Bug da 1ª execução (NameError np no shim) corrigido; 2ª execução verde.

## Primeira geração ponta a ponta (T.png, mesma imagem do TRELLIS)

```json
{"mode": "triposr", "model": "stabilityai/TripoSR", "seed": null,
 "tempo_load_s": 7.77, "tempo_preproc_s": 9.37, "tempo_run_s": 1.1, "tempo_extract_s": 4.25,
 "tempo_total_s": 25.35, "vertices": 70096, "faces": 140152,
 "watertight_bruto": true, "winding_consistent": true, "device": "cuda:0", "cuda_ok": true}
```

**VRAM (poller 1 Hz):** baseline 1.116 MiB used → **pico 4.256 MiB** → contraste direto com TRELLIS (pico 11.947 MiB).

Renders: `preview_a.png` (377 KB) / `preview_b.png` (392 KB) — mesma câmera/luz do TRELLIS (`tools/generator/render_preview.py`).

## Observações para o benchmark

- TripoSR é **reconstrução determinística** (sem seed) — retry determinístico trivial.
- `watertight_bruto: true` é esperado: mesh sai de marching cubes em grid denso (casca fechada por construção); TRELLIS (FlexiCubes) tipicamente entrega non-watertight. O scoring mede isso honestamente nos dois.
- `model.renderer.set_chunk_size(8192)` padrão do run.py oficial mantido.
