# Galeria — 10 casos × 2 modos

Gerado automaticamente em 2026-11-04T12:32:49. Render: Blender 5.0.1 headless,
Cycles CPU, **câmera/luz idênticas para todos** (ângulo A = 3/4 frontal 35°/25°,
ângulo B = 3/4 traseiro 145°/15°). Malha CRUDA do gerador (sem reparo).

## trex_figurine — miniatura

| input | TRELLIS A / B | TripoSR A / B |
|---|---|---|
![input trex_figurine](../../benchmarks/testset/trex_figurine.png)<br>`MIT` | ![trex_figurine trellis A](gallery/trex_figurine_trellis_a.png)<br>![trex_figurine trellis B](gallery/trex_figurine_trellis_b.png)<br>`t=73.7s · 11816MiB · 292695v · manifold False→False` | ![trex_figurine triposr A](gallery/trex_figurine_triposr_a.png)<br>![trex_figurine triposr B](gallery/trex_figurine_triposr_b.png)<br>`t=28.2s · 3570MiB · 70096v · manifold True→True` |

## humanoide_dragonborn — miniatura humanoide (caso de uso do Estúdio de Pose — Fase 3)

| input | TRELLIS A / B | TripoSR A / B |
|---|---|---|
![input humanoide_dragonborn](../../benchmarks/testset/humanoide_dragonborn.png)<br>`MIT` | ![humanoide_dragonborn trellis A](gallery/humanoide_dragonborn_trellis_a.png)<br>![humanoide_dragonborn trellis B](gallery/humanoide_dragonborn_trellis_b.png)<br>`t=65.1s · 11715MiB · 272517v · manifold False→False` | ![humanoide_dragonborn triposr A](gallery/humanoide_dragonborn_triposr_a.png)<br>![humanoide_dragonborn triposr B](gallery/humanoide_dragonborn_triposr_b.png)<br>`t=27.3s · 3570MiB · 45976v · manifold True→True` |

## criatura_dragao — criatura detalhada

| input | TRELLIS A / B | TripoSR A / B |
|---|---|---|
![input criatura_dragao](../../benchmarks/testset/criatura_dragao.png)<br>`MIT` | ![criatura_dragao trellis A](gallery/criatura_dragao_trellis_a.png)<br>![criatura_dragao trellis B](gallery/criatura_dragao_trellis_b.png)<br>`t=66.0s · 11679MiB · 260934v · manifold False→False` | ![criatura_dragao triposr A](gallery/criatura_dragao_triposr_a.png)<br>![criatura_dragao triposr B](gallery/criatura_dragao_triposr_b.png)<br>`t=26.5s · 3578MiB · 53039v · manifold True→True` |

## estrutura_castelo — estrutura

| input | TRELLIS A / B | TripoSR A / B |
|---|---|---|
![input estrutura_castelo](../../benchmarks/testset/estrutura_castelo.png)<br>`MIT` | `trellis: ERRO` | ![estrutura_castelo triposr A](gallery/estrutura_castelo_triposr_a.png)<br>![estrutura_castelo triposr B](gallery/estrutura_castelo_triposr_b.png)<br>`t=26.5s · 3570MiB · 67179v · manifold False→False` |

## estrutura_piramide — estrutura geométrica simples

| input | TRELLIS A / B | TripoSR A / B |
|---|---|---|
![input estrutura_piramide](../../benchmarks/testset/estrutura_piramide.png)<br>`MIT` | ![estrutura_piramide trellis A](gallery/estrutura_piramide_trellis_a.png)<br>![estrutura_piramide trellis B](gallery/estrutura_piramide_trellis_b.png)<br>`t=65.3s · 11725MiB · 469066v · manifold True→True` | ![estrutura_piramide triposr A](gallery/estrutura_piramide_triposr_a.png)<br>![estrutura_piramide triposr B](gallery/estrutura_piramide_triposr_b.png)<br>`t=26.4s · 3574MiB · 98449v · manifold True→True` |

## prop_caixote — prop simples

| input | TRELLIS A / B | TripoSR A / B |
|---|---|---|
![input prop_caixote](../../benchmarks/testset/prop_caixote.png)<br>`MIT` | `trellis: ERRO` | ![prop_caixote triposr A](gallery/prop_caixote_triposr_a.png)<br>![prop_caixote triposr B](gallery/prop_caixote_triposr_b.png)<br>`t=27.3s · 3570MiB · 96613v · manifold True→True` |

## robo_caranguejo — hard surface

| input | TRELLIS A / B | TripoSR A / B |
|---|---|---|
![input robo_caranguejo](../../benchmarks/testset/robo_caranguejo.png)<br>`MIT` | `trellis: ERRO` | ![robo_caranguejo triposr A](gallery/robo_caranguejo_triposr_a.png)<br>![robo_caranguejo triposr B](gallery/robo_caranguejo_triposr_b.png)<br>`t=26.9s · 3570MiB · 107772v · manifold True→True` |

## local_caneca — peça funcional (uso real do dono)

| input | TRELLIS A / B | TripoSR A / B |
|---|---|---|
![input local_caneca](../../benchmarks/testset/local_caneca.png)<br>`CC0` | ![local_caneca trellis A](gallery/local_caneca_trellis_a.png)<br>![local_caneca trellis B](gallery/local_caneca_trellis_b.png)<br>`t=65.3s · 11225MiB · 234682v · manifold True→True` | ![local_caneca triposr A](gallery/local_caneca_triposr_a.png)<br>![local_caneca triposr B](gallery/local_caneca_triposr_b.png)<br>`t=44.9s · 3585MiB · 72043v · manifold True→True` |

## local_engrenagem — peça funcional mecânica

| input | TRELLIS A / B | TripoSR A / B |
|---|---|---|
![input local_engrenagem](../../benchmarks/testset/local_engrenagem.png)<br>`CC0` | ![local_engrenagem trellis A](gallery/local_engrenagem_trellis_a.png)<br>![local_engrenagem trellis B](gallery/local_engrenagem_trellis_b.png)<br>`t=57.0s · 10713MiB · 149308v · manifold True→True` | ![local_engrenagem triposr A](gallery/local_engrenagem_triposr_a.png)<br>![local_engrenagem triposr B](gallery/local_engrenagem_triposr_b.png)<br>`t=51.2s · 3588MiB · 48964v · manifold True→True` |

## local_gancho — peça funcional (impressão prática)

| input | TRELLIS A / B | TripoSR A / B |
|---|---|---|
![input local_gancho](../../benchmarks/testset/local_gancho.png)<br>`CC0` | ![local_gancho trellis A](gallery/local_gancho_trellis_a.png)<br>![local_gancho trellis B](gallery/local_gancho_trellis_b.png)<br>`t=58.1s · 10815MiB · 125234v · manifold True→True` | ![local_gancho triposr A](gallery/local_gancho_triposr_a.png)<br>![local_gancho triposr B](gallery/local_gancho_triposr_b.png)<br>`t=47.9s · 3588MiB · 80192v · manifold True→True` |

---
Votação do dono: 👍/👎 por caso, por modo — registrada depois em ADR-005 (default mode).

