# TripoSF × TripoSG — benchmark RTX 3060 12GB (caso Anubis) — 2026-11-17

## 0. Aviso crítico de escopo (leia antes de comparar)

**TripoSF NÃO é um gerador imagem→3D.** O repo oficial
(https://github.com/VAST-AI-Research/TripoSF, commit clonado 2026-11-17) é um
**VAE de malhas 3D** (SparseFlex): a entrada oficial do `inference.py` é
`--mesh-path <obj>` (point cloud amostrado da malha) → reconstrução. Não existe
comando de imagem no README nem no código.

Adaptação usada (decisão da sessão, pendente de ratificação do dono no gate):
reaproveitamos a **mesma linhagem da imagem do teste do TripoSG** —

```
anubis_{a,b}_preproc.png  (imagens EXATAS do teste TripoSG, intocadas)
   └─> TripoSG  → out/triposg_{a,b}/mesh.obj   (evidência existente, intocada)
          └─> TripoSF → meshes/anubis_{a,b}_{256,512}_triposf.obj  (novo)
```

Ou seja: **"TripoSF vs TripoSG" aqui = malha bruta do TripoSG vs essa mesma
malha re-reconstruída pelo TripoSF.** Não é um duelo de geração a partir da
imagem; é um teste de o quanto o TripoSF preserva/refina a saída do TripoSG.

## 1. Ambiente

- GPU: RTX 3060 12GB (WSL2, driver 620.67.01 / CUDA UMD 13.5), desktop Windows
  consumindo 1,2–2,7 GB durante os testes (incluído nas medidas de pico).
- Venv dedicado `~/venvs/triposf` (python 3.11.16), conforme ordem do dono —
  nota: convenção histórica do projeto é `~/.venvs/` (ADR-004/006).
- Clone: `~/tools/TripoSF` (github.com/VAST-AI-Research/TripoSF).
- Pesos: HuggingFace oficial `VAST-AI/TripoSF` → `vae/pretrained_TripoSFVAE_256i1024o.safetensors`
  (715.361.228 bytes; sha256 `7aa6e79a46cd35893356945edc212d2f733330586f55087160c4a364c4ce9b37`)
  em `~/tools/TripoSF/ckpts/` (como manda o README).
- Desvios de `requirements.txt` (documentados, sem gambiarra no código):
  - `numpy 1.26.4` no lugar de `1.22.2` (pin oficial não tem wheel p/ py3.11).
  - `xformers 0.0.32.post2` no lugar de `flash-attn 2.5.9post1` — backend
    alternativo **nativo do código** via `ATTN_BACKEND/SPARSE_ATTN_BACKEND=xformers`
    (mesma combinação já comprovada no venv trellis2 do C3).
  - `torch-scatter 2.1.2+pt28cu128` (wheel oficial PyG p/ torch 2.8).
  - `spconv-cu120 2.3.6` (idem `spconv`, variante CUDA com wheel).
  - `torch 2.8.0+cu128` (README pede "PyTorch 2.0+").
  - `pip check` final: sem conflitos.

## 2. GUARD de VRAM (regra fixa: 10.000 MiB de pico)

Método: poller `nvidia-smi` a 1Hz (CSV em `vram/`), pico = memória **total
usada** (mesma métrica do C3, inclui desktop Windows). Pico > 10.000 MiB ⇒ job
morto e marcado BLOQUEADO. Pré-despacho: exigidos ≥ 8.000 MiB livres + lock
serial de GPU (mesmo lock do projeto).

### Exemplo oficial (jacket.obj do repo)

| config | sample_points_num | resultado | pico MiB |
|---|---|---|---|
| oficial TripoSFVAE_1024 (saída 1024) | 819.200 (oficial) | **BLOQUEADO pelo guard** | 11.615 |
| oficial c/ resolução de saída 512 | 819.200 (oficial) | **BLOQUEADO pelo guard** | 11.680 |
| saída 512 | 409.600 | OK (24,0s; 586.902 faces) | 8.328 |
| saída 256 | 409.600 | OK (25,5s; 149.486 faces) | 7.962 |
| saída 1024 | 409.600 | **BLOQUEADO pelo guard** | 10.057 |

Diagnóstico (sonda por fases, `probe_fases.py`): o gargalo é o
`LocalPoolPointnet` de entrada — o `forward` oficial do modelo roda esse estágio
sob `autocast float32` interno com TODOS os pontos na memória; com 819.200
pontos isso estoura ~9 GB sozinho, **independente da resolução de saída**
(encoder+decoder medidos em ~3,5 GB alocados). Redução para 409.600 pontos via
`sample_points_num` — **knob oficial documentado no README** ("Optimization
Tips") — resolve 256/512; 1024 permanece bloqueado (README já avisava: ≥12 GB
para 1024³; a 3060-12GB compartilhada com o desktop não tem os 10 GB de pico).

Custo da redução: densidade de amostragem de superfície ½ da oficial — ainda
≈6× o nº de voxels do grid de entrada em todos os casos rodados.

## 3. Benchmark Anubis (entrada = mesh bruta do TripoSG, seed/config oficiais)

Telemetria completa em `report/`, `logs/`, `vram/`; malhas em `meshes/`.

| run | pico VRAM | tempo total | recon | faces | watertight | winding | componentes |
|---|---|---|---|---|---|---|---|
| anubis_a_256 | 5.601 MiB | 24,5s | 3,5s | 156.536 | ✅ | ✅ | 8 |
| anubis_b_256 | 5.703 MiB | 23,5s | 3,8s | 159.532 | ✅ | ✅ | 18 |
| anubis_a_512 | 7.509 MiB | 29,5s | 6,2s | 615.998 | ❌ | ❌ | 7 |
| anubis_b_512 | 7.198 MiB | 28,5s | 6,1s | 630.756 | ❌ | ✅ | 18 |

Referência TripoSG (evidência existente `~/printer3d-work/logs-c3/anubis-triposg.log`,
mesmas imagens): 55,9s de geração por vista (+3,5–9,7s load), 536.792/548.852
faces, watertight ✅, 1 componente, winding ✅. VRAM do TripoSG **não foi medida
na run original do anubis** (log sem telemetria); no C3 (outros casos, mesma
GPU/venv) o pico do TripoSG foi 10.396–12.039 MiB.

## 4. Comparação honesta (qualidade, fidelidade, detalhes)

Renders canônicos do C3 (mesma câmera/luz/ângulos) em `gallery_render/`;
comparativos lado a lado em `gallery_render/comparativo/gate_anubis_{a,b}_{a,b}.png`.

**Qualidade da malha (métrica objetiva):**
- TripoSG bruto: 1 componente, watertight, winding ok — malha "sã" mas com
  **ruído de superfície visível** (ondulações no torso; pontilhado/porosidade
  nas costas e ombros nos renders).
- TripoSF 256: superfície visivelmente mais lisa que o bruto; watertight ✅;
  winding ✅; **porém 8–18 componentes** (fragmentos-ilha pequenos, típicos do
  SparseFlex; não aparecem nos renders, mas existem na malha).
- TripoSF 512: o mais liso e detalhado visualmente; **mas não-watertight** e o
  `a_512` tem winding inconsistente — para impressão 3D exigiria reparo (Fase 2
  Forja) antes do slice.

**Fidelidade à imagem/silhueta:** pose, proporções e elementos (cabeça de
chacal, orelhas, cajado contínuo, ankh, saiote, cauda, pés) preservados nos
três; o TripoSF não inventou nem perdeu partes em nenhuma resolução (verificado
nos dois ângulos canônicos, vistas a e b). O TripoSF é um re-encoder — a
fidelidade "à imagem" herdada do TripoSG é mantida, com pequenas perdas em
detalhes finos (dedos das mãos seguem fundidos/simplificados em todas as
variantes).

**Detalhes:** ourelhas, finial do cajado e contorno do ankh ficam mais nítidos
no 512 > 256 > bruto. Ornamentos do saiote continuam suavizados em todas.

**Defeitos observados (sem maquiagem):**
- TripoSG: ruído/porosidade de superfície; dedos fundidos; bordas arredondadas.
- TripoSF 256: ilhas flutuantes (8–18 comps.); detalhe fino suavizado.
- TripoSF 512: furos/bordas abertas (não-watertight) + winding inconsistente no
  `a`; mesma multiplicidade de ilhas.

## 5. Veredito

**A decisão é visual e do dono (gate humano).** Os comparativos estão em
`gallery_render/comparativo/`. Leitura técnica honesta: o TripoSF (como estágio
de refinamento pós-TripoSG) entrega superfície mais limpa e detalhe levemente
melhor por ~25–30s e <8 GB; o custo é pós-processamento obrigatório (reparo de
watertight/ilhas) se o destino for impressão. O 1024³ do TripoSF segue
inviável nesta GPU sob o guard de 10 GB.

## 6. Arquivos

- `meshes/` — 4 malhas TripoSF (não commitadas; pesadas — ver .gitignore local)
- `input/` — imagens de entrada exatas do teste TripoSG (cópias)
- `report/`, `logs/`, `vram/` — telemetria por run (commitados)
- `TripoSFVAE_o{256,512}.yaml` — configs derivados do oficial (apenas
  `resolution` e `sample_points_num` alterados, documentado acima)
- `gallery_render/` — renders canônicos + comparativos do gate
- Workspace de trabalho (fonte): `~/printer3d-work/triposf-bench/`
