# C3 — Notas de instalação na rtx3060-12gb (estado real de 2026-11-16 ~22:51)

> **Documento de handoff**: foi escrito por um agente que chegou perto do limite de quota e entregou o resto. Tudo abaixo é MEDIDO/REAL (logs brutos em `~/printer3d-work/logs-c3/` na máquina — copiados em parte para esta pasta).

## Estado no momento do handoff

| Item | Estado |
|---|---|
| PROMPT-07 (abrir Fase C + C2) | ✅ CONCLUÍDO, na main (commits `faa50bd`, `62fabe9`, `e4ab93a`) |
| testset_preproc | ✅ 10/10 em `~/printer3d-work/testset_preproc/` + sidecars |
| venv trellis2 (`~/.venvs/trellis2`) | ✅ torch 2.8.0+cu128 + xformers 0.0.32.post2 + requirements-lock do fork (menos triton-windows) + utils3d pinado |
| Extensões compiladas (venv trellis2) | ✅ flex_gemm 1.0.0 · cumesh 0.0.1 · o_voxel 0.0.1 · nvdiffrast 0.4.0 · ❌ nvdiffrec_render (falha no link `-lnvrtc`; **não é necessário** — o runner é shape-only e pula textura) |
| venv triposg (`~/.venvs/triposg`) | ✅ torch 2.8.0+cu128 · **diffusers 0.33.1** (0.43 quebra import) · **transformers 4.57.3** (5.x quebra diffusers 0.33) · numpy 1.26.4 · pymeshlab · **diso 0.1.4** (compilado com toolkit) |
| Pesos TRELLIS.2-4B (15,1 GiB) | ✅ cache HF (`microsoft/TRELLIS.2-4B`) |
| Pesos TripoSG (7,4 GiB) | ✅ cache HF (`VAST-AI/TripoSG`) — org correto é **VAST-AI**, não VAST-AI-Research |
| DINOv3 (cond model) | ✅ via mirror **camenduru/dinov3-vitl16-pretrain-lvd1689m** → `~/tools/TRELLIS.2/MODELS/dinov3/` (oficial facebook/… é **GATED**; aceitar licença Meta + `hf auth login` é o caminho canônico — mirror documentado aqui) |
| RMBG-2.0 (rembg interno) | ✅ substituído por **ZhengPeng7/BiRefNet** (público, autor original) → `~/tools/TRELLIS.2/MODELS/RMBG-2.0/` (briaai/RMBG-2.0 é GATED; impacto mínimo — entradas já vêm com fundo branco do C2) |
| CUDA toolkit 12.8 | ✅ `~/cuda-12.8` (runfile, sem driver) + **PATCH OBRIGATÓRIO**: `include/crt/math_functions.h` — 6 declarações (rsqrt/sinpi/cospi float+double) ganharam ` noexcept` p/ glibc 2.42 do Ubuntu 26.04 (backup em `logs-c3/math_functions.h.bak`; sem o patch, TODA compilação de extensão falha) |
| gcc | ⚠️ sistema traz gcc 15 (quebra pybind11 do torch 2.8) — **usar `CC=gcc-14 CXX=g++-14`** (pacote instalado) |
| Smoke TripoSR→TripoSG | ✅ **OK**: caneca preproc → 959.744 verts / 1.919.528 faces / 76,6s / load 10s / 0 erros (`logs-c3/smoke-triposg*.log`) |
| Smoke TRELLIS.2 | ✅ **OK em 512³** (2026-11-16 ~23:59): caneca preproc → 925.437 verts / 1.996.815 faces (raw 2.566.098, simplificado p/ teto 2M) / run 82,4s / load 206,6s / 0 erros (`logs-c3/smoke-trellis2-512d.log`, mesh em `~/printer3d-work/c3-bench/smoke/trellis2/`). **1024_cascade: OOM mesmo após fixes** — ver §Atualização abaixo |
| Benchmark completo (10×4) | ❌ não rodado |
| Renders/galeria/publish | ❌ não rodados |

## Atualização 2026-11-16 ~meia-noite (agente Devin) — bugs reais corrigidos no smoke TRELLIS.2

Sequência de falhas reais encontradas e resolvidas (todas MEDIDAS, logs em `logs-c3/`):

1. **`BiRefNet_config.py`/`handler.py` ausentes** no mirror local `~/tools/TRELLIS.2/MODELS/RMBG-2.0` → `OSError ... does not appear to have a file named BiRefNet_config.py`. O repo ZhengPeng7/BiRefNet no HF tem esses arquivos (trust_remote_code); baixados para a pasta local.
2. **`pipeline.preprocess_image(True)`** — chamada inválida (o método recebe `Image`, não bool); linha removida do runner. O `preprocess_image` oficial já faz rembg+crop — mantido (comportamento padrão do gerador).
3. **Faltava `pipeline.cuda()`** após `from_pretrained` — em low_vram isso só define `_device='cuda'`; sem isso rembg/cond rodavam em CPU e `BiRefNet.__call__` (que hardcoda `.to("cuda")`) estourava mismatch de device.
4. **`flex_gemm` vs fork**: `SubMConv3dFunction._compute_neighbor_cache()` do FlexGEMM instalado exige arg `needs_grad` (commit upstream "implement sparse conv fwd path"); fork não passava. **Patch em `~/tools/TRELLIS.2/trellis2/modules/sparse/conv/conv_flex_gemm.py`** (2 call sites → `x.feats.requires_grad`). Fora do repo — se o clone for refeito, refazer o patch.
5. **OOM no decode/upsample — causa raiz: AUTOGRAD LIGADO.** O pipeline oficial executa tudo sob `@torch.no_grad()` (`run()`); nosso runner chamava `decode_shape_slat`/`sample_shape_slat_cascade` direto → cada conv (~450MB/conv medido via SPARSE_DEBUG) retinha ativações → 10GB alloc aos ~19 convs → OOM com tensores de só 13-32MB. Fix: `torch.set_grad_enabled(False)` após preprocess no runner. Com isso o decode 512³ passou.
6. **`decode_shape_slat` é helper de baixo nível** — quem chama `decode_latent` faz antes: `decoder.low_vram=True` + `from_latent.to(device)` + `output_layer.to(device)`. Replicado no runner (sem isso `from_latent` fica em CPU → mismatch de device).
7. **`PYTORCH_CUDA_ALLOC_CONF`** do runner agora espelha o fork: `expandable_segments:True,garbage_collection_threshold:0.65,max_split_size_mb:128` (pipeline_worker.py + app.py).
8. **512³ funciona; 1024_cascade ainda OOM** — após no_grad, o gargalo migrou para o estágio HR do cascade (`sample_shape_slat_cascade` → attention do flow 1.3B com até 49152 tokens). Testando `--max-tokens 24576` como mitigação; se OOM persistir, **benchmark TRELLIS.2 roda em 512³** (decisão honesta documentada — oficial exige 24GB).

Runner ganhou args: `--res {512,1024}` (default 512) e `--max-tokens` (default 49152). Relatório inclui `res_mode`/`resolucao`/`max_tokens`.

## Código novo (NA BRANCH/MAIN — commit pendente no momento do handoff)

- `tools/generator/trellis2_runner.py` — shape-only 1024_cascade (skip tex_slat), ATTN_BACKEND=xformers, simplifica >2M faces, REPORT_JSON no stdout
- `tools/generator/triposg_runner.py` — diffusers TripoSGPipeline via snapshot local + `trust_remote_code=True` (scheduler é classe custom do repo — precisa do `triposg` no sys.path), fp16, 50 steps, cfg 7.0, seed 42; RMBG-1.4 do cache HF (briaai/RMBG-1.4 é público) com fallback documentado
- `tools/generator/trellis2_plugin.py` / `triposg_plugin.py` — vram_min_free_mib 9.000 / 8.000, `venv_py` apontando pros venvs próprios
- `tools/generator/base_plugin.py` — **edição mínima**: novo atributo de classe `venv_py` (default = VENVPY antigo; backward compat) usado no subprocess
- `tools/generator/run_comparativo_c3.py` — estágios `gerar|render|publish`, modos `trellis2,triposg,trellis,triposr`, entrada `~/printer3d-work/testset_preproc/<caso>_preproc.png`, scoring REUTILIZADO de run_benchmark (import), saída `~/printer3d-work/c3-bench/` + evidência em `evidence/fase-c/comparativo-3060/`

## Armadilhas descobertas (não reinventar)

1. **Background via nohup MORRE** quando a sessão wsl.exe termina — rodar downloads/compilações em FOREGROUND com timeout longo;
2. **`/tmp` do WSL se limpa** entre sessões — fontes clonadas em `~/printer3d-work/ext-sources/` (FlexGEMM, CuMesh, nvdiffrast, nvdiffrec);
3. Compilar extensão exige: `export CUDA_HOME=$HOME/cuda-12.8 PATH=$CUDA_HOME/bin:$PATH TORCH_CUDA_ARCH_LIST="8.6" MAX_JOBS=8 CC=gcc-14 CXX=g++-14`;
4. `TripoSGPipeline.from_pretrained("VAST-AI/TripoSG")` direto FALHA (scheduler custom) — usar snapshot_download local + trust_remote_code;
5. `prepare_image` do TripoSG aceita **path**, não PIL;
6. Guard por gerador (explícito no plugin): trellis 10.000 · trellis2 9.000 · triposg 8.000 · triposr 6.000 — padrão já usado na Fase 1.

## Próximos passos (para o agente que continuar)

1. `git pull` na main; ler este arquivo + `AGENTS.md` + `PROGRESS.md` + `docs/roadmap.md` §Fase C;
2. Re-rodar smoke do TRELLIS.2:
   `cd ~/printer3d-work && TRELLIS2_HOME=~/tools/TRELLIS.2 ~/.venvs/trellis2/bin/python <repo>/tools/generator/trellis2_runner.py --image ~/printer3d-work/testset_preproc/local_caneca_preproc.png --output-dir ~/printer3d-work/c3-bench/smoke/trellis2 --seed 42`
   — erros prováveis: import de renderizador (nvdiffrec ausente) → se o import de `trellis2.pipelines` exigir, instalar `pip install ~/printer3d-work/ext-sources/nvdiffrec --no-build-isolation` com os mesmos exports e investigar o link `-lnvrtc`; se `decode_shape_slat` reclamar de decoder em CPU, mover `self.models['shape_slat_decoder'].to('cuda')` antes;
3. Smoke OK → `tools/setup/py.sh tools/generator/run_comparativo_c3.py gerar` (roda os 4 modos; relatório por caso em `~/printer3d-work/c3-bench/<caso>/<modo>/report.json`); depois `render`, depois `publish`;
4. Commit convencional + push a cada marco; evidência em `evidence/fase-c/comparativo-3060/`;
5. Atualizar PROGRESS.md/HANDOFF.md (C3 concluído → gatilho = veredito do dono → ADR-007);
6. Baselines trellis/triposr usam os plugins da Fase 1 (printer3d-ia venv) — não reinstalar nada;
7. GPU livre ~10,6 GiB em repouso (desktop do dono em uso normal consome 1,2–2,2 GiB — guard por plugin resolve).
