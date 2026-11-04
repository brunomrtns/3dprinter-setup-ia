# Benchmark Fase 1 — TRELLIS vs TripoSR (10 casos fixos)

Gerado automaticamente por `run_benchmark.py` em 2026-11-04T12:32:49 — sem edição manual.

GPU: `NVIDIA GeForce RTX 3060, 12288 MiB, 621.01` · torch 2.5.1+cu121 · seed TRELLIS 42

Espessura = estimativa amostral (raycast −normal, 300 amostras, percentil 5, **unidades da malha ≈ cubo unitário** — mm reais só após `scale_mm` na Forja). `parede%` = amostras com oposição encontrada (100% = casca fechada em todo o amostrado).

## Tabela completa (por caso × modo)

| caso | modo | tempo_s | VRAM pico MiB | vértices | faces | manifold antes→depois reparo | espessura pct5 | parede% | erro |
|---|---|---|---|---|---|---|---|---|---|
| trex_figurine | trellis | 73.7 | 11816 | 292695 | 585760 | False→False | 0.003 | 100% |  |
| trex_figurine | triposr | 28.2 | 3570 | 70096 | 140152 | True→True | 0.016 | 100% |  |
| humanoide_dragonborn | trellis | 65.1 | 11715 | 272517 | 545044 | False→False | 0.005 | 100% |  |
| humanoide_dragonborn | triposr | 27.3 | 3570 | 45976 | 91924 | True→True | 0.043 | 100% |  |
| criatura_dragao | trellis | 66.0 | 11679 | 260934 | 521860 | False→False | 0.005 | 100% |  |
| criatura_dragao | triposr | 26.5 | 3578 | 53039 | 106082 | True→True | 0.033 | 100% |  |
| estrutura_castelo | trellis | 79.2 | 12070 | — | — | None→None | — | — | SIM |
| estrutura_castelo | triposr | 26.5 | 3570 | 67179 | 134180 | False→False | 0.027 | 100% |  |
| estrutura_piramide | trellis | 65.3 | 11725 | 469066 | 938428 | True→True | 0.002 | 100% |  |
| estrutura_piramide | triposr | 26.4 | 3574 | 98449 | 196878 | True→True | 0.027 | 100% |  |
| prop_caixote | trellis | 108.9 | 12057 | — | — | None→None | — | — | SIM |
| prop_caixote | triposr | 27.3 | 3570 | 96613 | 193202 | True→True | 0.087 | 100% |  |
| robo_caranguejo | trellis | 76.7 | 12050 | — | — | None→None | — | — | SIM |
| robo_caranguejo | triposr | 26.9 | 3570 | 107772 | 215536 | True→True | 0.047 | 100% |  |
| local_caneca | trellis | 65.3 | 11225 | 234682 | 469292 | True→True | 0.008 | 100% |  |
| local_caneca | triposr | 44.9 | 3585 | 72043 | 144086 | True→True | 0.120 | 100% |  |
| local_engrenagem | trellis | 57.0 | 10713 | 149308 | 298632 | True→True | 0.002 | 100% |  |
| local_engrenagem | triposr | 51.2 | 3588 | 48964 | 97916 | True→True | 0.145 | 100% |  |
| local_gancho | trellis | 58.1 | 10815 | 125234 | 250440 | True→True | 0.002 | 100% |  |
| local_gancho | triposr | 47.9 | 3588 | 80192 | 160380 | True→True | 0.176 | 100% |  |

## Resumo por modo

| modo | tempo médio s | mediana s | VRAM pico máx MiB | vértices médios | manifold após reparo (n/10) | erros (n/10) |
|---|---|---|---|---|---|---|
| trellis | 71.5 | 65.7 | 12070 | 257777 | 4/10 | 3/10 |
| triposr | 33.3 | 27.3 | 3588 | 74032 | 9/10 | 0/10 |
