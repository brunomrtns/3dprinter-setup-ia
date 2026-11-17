# Comparativo Fase C (C3) — 4 geradores, entrada pré-processada

Gerado automaticamente em 2026-11-17T12:36:36 — sem edição manual.

GPU: `NVIDIA GeForce RTX 3060, 12288 MiB, 621.01` · entrada: testset_preproc (C2 — preprocess_input.py) · seed 42

## Tabela por caso × modo

| caso | modo | tempo_s | VRAM pico MiB | vértices | manifold antes→depois | espessura pct5 | erro |
|---|---|---|---|---|---|---|---|
| trex_figurine | trellis2 | 157.1 | 5229 | 858845 | False→False | 0.002 |  |
| trex_figurine | triposg | 88.5 | 11254 | 694738 | True→True | 0.006 |  |
| trex_figurine | trellis | 65.5 | 12048 | — | None→None | — | SIM |
| trex_figurine | triposr | 43.6 | 3860 | 65404 | True→True | 0.019 |  |
| humanoide_dragonborn | trellis2 | 153.0 | 5327 | 430551 | False→False | 0.002 |  |
| humanoide_dragonborn | triposg | 73.6 | 10759 | 586210 | True→True | 0.018 |  |
| humanoide_dragonborn | trellis | 58.1 | 12038 | — | None→None | — | SIM |
| humanoide_dragonborn | triposr | 46.8 | 4056 | 45929 | True→True | 0.031 |  |
| criatura_dragao | trellis2 | 154.9 | 5180 | 293452 | False→False | 0.018 |  |
| criatura_dragao | triposg | 74.0 | 11625 | 551556 | True→True | 0.075 |  |
| criatura_dragao | trellis | 56.4 | 12034 | — | None→None | — | SIM |
| criatura_dragao | triposr | 43.1 | 4057 | 46544 | True→True | 0.042 |  |
| estrutura_castelo | trellis2 | 194.3 | 5121 | 922918 | False→False | 0.005 |  |
| estrutura_castelo | triposg | 145.1 | 12039 | 1687086 | False→False | 0.005 |  |
| estrutura_castelo | trellis | 66.7 | 11924 | — | None→None | — | SIM |
| estrutura_castelo | triposr | 44.2 | 4058 | 67673 | True→True | 0.038 |  |
| estrutura_piramide | trellis2 | 170.7 | 5080 | 905859 | False→False | 0.002 |  |
| estrutura_piramide | triposg | 94.7 | 10396 | 1108953 | False→False | 0.031 |  |
| estrutura_piramide | trellis | 63.1 | 11985 | — | None→None | — | SIM |
| estrutura_piramide | triposr | 42.8 | 4058 | 95600 | True→True | 0.028 |  |
| prop_caixote | trellis2 | 210.3 | 5081 | 969024 | False→False | 0.007 |  |
| prop_caixote | triposg | 124.5 | 10215 | 2112753 | False→False | 0.087 |  |
| prop_caixote | trellis | 105.6 | 12011 | — | None→None | — | SIM |
| prop_caixote | triposr | 42.8 | 4060 | 96241 | True→True | 0.055 |  |
| robo_caranguejo | trellis2 | 173.1 | 5081 | 903245 | False→False | 0.002 |  |
| robo_caranguejo | triposg | 99.4 | 11455 | 1283068 | True→True | 0.080 |  |
| robo_caranguejo | trellis | 72.1 | 12034 | — | None→None | — | SIM |
| robo_caranguejo | triposr | 75.1 | 5818 | 106893 | False→False | 0.034 |  |
| local_caneca | trellis2 | 151.6 | 5451 | 873590 | False→False | 0.008 |  |
| local_caneca | triposg | — | — | — | None→None | — | SIM |
| local_caneca | trellis | 63.8 | 12017 | — | None→None | — | SIM |
| local_caneca | triposr | 80.4 | 5887 | 71416 | True→True | 0.114 |  |
| local_engrenagem | trellis2 | 147.2 | 5207 | 645341 | False→False | 0.080 |  |
| local_engrenagem | triposg | — | — | — | None→None | — | SIM |
| local_engrenagem | trellis | 55.8 | 12032 | — | None→None | — | SIM |
| local_engrenagem | triposr | 78.0 | 5905 | 44650 | True→True | 0.189 |  |
| local_gancho | trellis2 | 151.0 | 5208 | 842559 | False→False | 0.002 |  |
| local_gancho | triposg | — | — | — | None→None | — | SIM |
| local_gancho | trellis | 53.8 | 11202 | 68392 | False→False | 0.005 |  |
| local_gancho | triposr | 74.7 | 10642 | 51196 | False→False | 0.037 |  |

## Resumo por modo

| modo | tempo mediana s | VRAM pico máx MiB | vértices médios | manifold pós-reparo | erros |
|---|---|---|---|---|---|
| trellis2 | 156.0 | 5451 | 764538 | 0/10 | 0/10 |
| triposg | 94.7 | 12039 | 1146338 | 4/10 | 3/10 |
| trellis | 53.8 | 11202 | 68392 | 0/10 | 9/10 |
| triposr | 45.5 | 10642 | 69155 | 8/10 | 0/10 |
