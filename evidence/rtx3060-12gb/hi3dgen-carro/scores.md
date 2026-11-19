# Benchmark Comparativo A/B C7-B — Hi3DGen × TripoSG × TRELLIS.2 (Caso Carro Fox)

**Data:** 2026-11-19  
**GPU:** NVIDIA GeForce RTX 3060 12GB (VRAM total 12.288 MiB)  
**Entrada comum:** `frente-e-lado-diagonal_tinted.png` (vista hero 3/4 dianteira-esquerda com vidros grafite padronizados)  
**Seed:** 42 em todos os geradores  

---

## 1. Tabela Comparativa de Métricas Reais

| Gerador | VRAM Pico (MiB) | Tempo Total (s) | Vértices | Faces | Abordagem Técnica |
|---|---|---|---|---|---|
| **`TripoSG`** (C6 baseline) | 10.250 | 116,96 s | 1.557.463 | 3.116.268 | DiT 2D→3D direto (sensível a reflexo de tinta/lataria) |
| **`TRELLIS.2`** (C6 512³) | 4.177 | 239,49 s | 922.933 | 1.961.412 | SLaT 512³ cascade (geometria esparsa) |
| **`Hi3DGen`** (C7-B novo) | **7.803** | **65,78 s** | **296.548** | **593.226** | **Normal-Bridging** (NiRNE YOSO 768px → Trellis-Normal DiT 1024px) |

---

## 2. Destaques da Execução Hi3DGen

1. **Eficiência e Velocidade:**
   - Inferência completa em **65,78 s** (quase o dobro da velocidade do TripoSG e 3,6× mais rápido que o TRELLIS.2).
   - Mapa de normais gerado pelo NiRNE em **6,10 s** e salvo em `normal.png`.
   - Pipeline 3D rodou em **33,68 s** (Stage 1 Sparse Structure 50 steps: 27 s; Stage 2 SLAT 6 steps: 3 s; mesh decode: 3 s).
2. **Consumo de VRAM Seguro na RTX 3060 12GB:**
   - Pico medido de **7.803,07 MiB** (margem de ~4,4 GB livres no desktop com Xwayland ativo).
   - Offload sequencial: NiRNE descarregado da GPU após a previsão das normais, liberando a VRAM para 8,12 MiB antes do carregamento do Hi3DGenPipeline.
3. **Resolução e Malha:**
   - Produz **593.226 faces** com topologia nítida e sem necessidade de decimação forçada.
   - O mapa de normais intermediário elimina a confusão causada por reflexos especulares na pintura do carro.

---

## 3. Próximo Passo

Publicação no viewer web (`https://brunointegrations.com/modelos3d/`) no caso `carro_nowin` como modo `hi3dgen` para avaliação e veredito do dono (Gate C7-B).
