# Benchmark Fase 1 — TRELLIS vs TripoSR (10 casos fixos)

Gerado automaticamente por `run_benchmark.py` em 2026-11-16T10:58:41 — sem edição manual.

GPU: `NVIDIA GeForce RTX 5060 Ti, 8151 MiB, 621.24` · torch 2.11.0+cu128 · seed TRELLIS 42

Espessura = estimativa amostral (raycast −normal, 300 amostras, percentil 5, **unidades da malha ≈ cubo unitário** — mm reais só após `scale_mm` na Forja). `parede%` = amostras com oposição encontrada (100% = casca fechada em todo o amostrado).

## Tabela completa (por caso × modo)

| caso | modo | tempo_s | VRAM pico MiB | vértices | faces | manifold antes→depois reparo | espessura pct5 | parede% | erro |
|---|---|---|---|---|---|---|---|---|---|
| trex_figurine | trellis | — | — | — | — | None→None | — | — | SIM |
| trex_figurine | triposr | 18.8 | 4385 | 70097 | 140154 | True→True | 0.016 | 100% |  |
| humanoide_dragonborn | trellis | — | — | — | — | None→None | — | — | SIM |
| humanoide_dragonborn | triposr | 14.7 | 4385 | 45976 | 91924 | True→True | 0.047 | 100% |  |
| criatura_dragao | trellis | — | — | — | — | None→None | — | — | SIM |
| criatura_dragao | triposr | 13.5 | 4385 | 53039 | 106082 | True→True | 0.027 | 100% |  |
| estrutura_castelo | trellis | — | — | — | — | None→None | — | — | SIM |
| estrutura_castelo | triposr | 14.0 | 4385 | 67180 | 134184 | False→False | 0.024 | 100% |  |
| estrutura_piramide | trellis | — | — | — | — | None→None | — | — | SIM |
| estrutura_piramide | triposr | 13.5 | 4385 | 98443 | 196866 | True→True | 0.026 | 100% |  |
| prop_caixote | trellis | — | — | — | — | None→None | — | — | SIM |
| prop_caixote | triposr | 14.1 | 4385 | 96609 | 193194 | True→True | 0.109 | 100% |  |
| robo_caranguejo | trellis | — | — | — | — | None→None | — | — | SIM |
| robo_caranguejo | triposr | 13.4 | 4385 | 107770 | 215532 | True→True | 0.039 | 100% |  |
| local_caneca | trellis | — | — | — | — | None→None | — | — | SIM |
| local_caneca | triposr | 27.1 | 4385 | 72043 | 144086 | True→True | 0.120 | 100% |  |
| local_engrenagem | trellis | — | — | — | — | None→None | — | — | SIM |
| local_engrenagem | triposr | 31.0 | 4385 | 48964 | 97916 | True→True | 0.147 | 100% |  |
| local_gancho | trellis | — | — | — | — | None→None | — | — | SIM |
| local_gancho | triposr | 31.1 | 4385 | 80192 | 160380 | True→True | 0.178 | 100% |  |

## Resumo por modo

| modo | tempo médio s | mediana s | VRAM pico máx MiB | vértices médios | manifold após reparo (n/10) | erros (n/10) |
|---|---|---|---|---|---|---|
| trellis | — | — | — | — | 0/10 | 10/10 |
| triposr | 19.1 | 14.4 | 4385 | 74031 | 9/10 | 0/10 |
