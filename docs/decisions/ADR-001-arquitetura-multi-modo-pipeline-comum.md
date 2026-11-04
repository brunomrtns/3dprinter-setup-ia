# ADR-001 — Arquitetura multi-modo com pipeline comum

**Status:** Aceito · **Data:** 2026-11-03 · **Fase:** 0

## Contexto

O projeto precisa gerar peças novas por IA image→3D local. O estado da arte muda rápido: o dono já tem TripoSR funcional (legado), TRELLIS (Microsoft, MIT) foi aprovado como modo principal planejado (roda na RTX 3060 12GB a 1024³, ~90s/modelo), e novos geradores vão aparecer. Independente de quem gera a malha, o trabalho seguinte é sempre o mesmo: a malha de IA vem quebrada (ver `docs/knowledge/stl-e-malhas.md` §3) e precisa de reparo, operações, validação objetiva e preparo para resina antes de ir ao slicer/PrintFlow3D.

## Decisão

1. **Geradores são plugins** atrás de uma interface comum: `generate(image_path, output_path, params) -> GenerationReport` (modo, versão, tempo, VRAM pico, vértices). Adicionar/trocar modo não altera nada fora do plugin;
2. **Todo resultado — de qualquer gerador ou módulo — passa obrigatoriamente pelo pipeline comum**: `entrada → reparo (manifold) → operações → validação (gates objetivos) → preview render → entrega PrintFlow3D`. Nenhum caminho curto direto ao slicer;
3. **Jobs de GPU em fila serial única** com guard de VRAM antes do despacho.

## Consequências

- Benchmark entre modos é comparável por construção (mesmos casos, mesmos gates) — base da decisão de default mode na Fase 1;
- Novo gerador futuro = novo plugin + benchmark, sem refatorar o pipeline;
- Custo: manter a interface de plugin estável e disciplinar o bypass (ninguém entrega malha crua);
- A validação nunca depende de julgamento visual: gates numéricos (manifold, espessura, mm, volume) reprovam antes de qualquer humano ver.
