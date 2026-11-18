# ADR-008 — Esteira de pós-processamento v1 (impressão, jogos e animação)

**Status:** Proposto (aguardando aprovação do dono — entra em vigor na abertura da Fase 2) · **Data:** 2026-11-18 · **Fase:** transição Fase C → Fase 2

## Contexto

O gate C5 (2026-11-17) elegeu o pipeline oficial `imagem → preproc C2 → TripoSG → refino TripoSF 512` por decisão visual do dono, com pendência explícita registrada no PROGRESS: **para imprimir é preciso passar pela Forja antes — a saída 512³ NÃO é watertight** (8–18 componentes-ilha; winding inconsistente no anubis_a_512). O catálogo completo da Forja (Fase 2) ainda não foi implementado — existe só o pacote de reparo entregue na Fase 1 (`tools/forja/forja/`).

O dono solicitou (2026-11-18) uma pesquisa de ferramentas de pós-processamento — GitHub, documentação oficial e fóruns — para três destinos da mesma peça de origem: impressão em resina (foco atual), assets para jogos e, no futuro, animação. A pesquisa foi conduzida com auditoria real (§1.5): licenças lidas nos arquivos LICENSE/raw do GitHub, CLI confirmada em código-fonte onde relevante, atividade verificada via API/páginas — log completo em `evidence/pesquisa-pos-processamento/fontes-verificadas.md`; base técnica consolidada em `docs/knowledge/pos-processamento-ferramentas.md`.

Achado central da pesquisa: o gap do pipeline não é mais o gerador — é hermeticidade, ilhas, espessura e oco. Existe ferramenta madura, local e com licença verificada para cada etapa da esteira; quase tudo roda em CPU.

## Decisão proposta (a aprovar pelo dono antes de implementar)

1. **Adotar a esteira v1 de 9 etapas** (tabela completa no knowledge doc §3): reparo pesado → união de componentes → suavização leve → decimação → espessura → escala mm → oco+dreno → preview → slice+QC. Cada etapa com gate objetivo e append no `transform_log` do sidecar (ADR-003). O escopo vira o plano de abertura da Fase 2 no roadmap;
2. **Motor de booleana das ops `boolean_*` = manifold3d** (Apache-2.0): o trimesh 5.2.1 já usado pelo projeto expõe engine `manifold` em `trimesh.boolean` — integração de dependência mínima (`pip install manifold3d`), booleana com saída manifold garantida. Ressalvas documentadas do autor: booleana não é definida para malha non-manifold (reparo vem antes) e evitar STL como formato intermediário (trafegar OBJ; STL só na entrega final ao slicer);
3. **Reparo pesado de fallback = fTetWild** (MPL-2.0) — licença permissiva, entrada tolerante a malhas sujas, projeto ativo. ManifoldPlus resolve hermeticidade em 1 comando, mas é **uso não-comercial** (Stanford): apenas uso manual excepcional, com registro no sidecar — nunca dependência padrão, para não criar dívida de licença se o projeto um dia comercializar;
4. **Gate objetivo pós-slice = UVtoolsCmd** (`print-issues`: ilhas, overhangs, armadilhas de resina, sucção — exit code verificável). UVtools é AGPL-3.0: instalar como **binário CLI externo** no fluxo, sem linkar código no repo;
5. **Suavização com preservação de detalhe = Taubin** (PyMeshLab ou equivalente) com **gate de Hausdorff** (teto configurável) — preservar o detalhe que sobreviveu ao grid 512³, nunca suavizar agressivamente por padrão;
6. **Decimação antes do slicer** é opcional e calibrada pela resolução da impressora (aresta ~0,3–0,5 mm), com gate Δ bbox/volume < 1% — abaixo do passo do grid as faces só descrevem ruído;
7. **IA de refinamento de malha fica na watchlist** (MeshAnythingV2, EdgeRunner, BPT — todas experimentais, teto de faces ou VRAM que o guard bloqueia), mesmo espírito do ADR-005: só avaliar com ADR próprio e caminho novo de qualidade, se o gate visual da esteira tradicional falhar.

## Alternativas consideradas

- **Manter só PyMeshFix** (estado atual): não cobre os casos pesados — winding inconsistente e autointerseção persistem; o próprio C5 registrou `fix_winding` falhando em malha aberta do trellis2;
- **ManifoldPlus como padrão de hermeticidade**: tecnicamente simples, mas licença não-comercial cria dívida se o projeto virar venda de peças — rejeitado como dependência padrão;
- **IA de refinamento como etapa da esteira** (ex.: malha densa → topologia de artista): teto de 1.600 faces (MeshAnythingV2) contra ~616 mil faces de entrada; ~12 GB fp16 (BPT) acima do guard; fluxo dos autores depende de serviço em nuvem (contra o ADR-003/local-first). Watchlist;
- **Não padronizar esteira e deixar cada caso no improviso**: contradiz o pipeline comum da arquitetura (reparo → operações → validação) e os gates objetivos.

## Consequências

- A abertura da Fase 2 passa a incluir: implementar as etapas 2–4 (novas), 7 (spec já pronta) e 9 (wrapper do UVtoolsCmd), com validador + evidência por etapa (DoD da fase);
- Dependência nova no venv `printer3d-ia`: `manifold3d` (pip, Apache-2.0) — exige OK do dono na abertura da fase (regra de uma fase por vez); UVtools é binário externo (instalação documentada na abertura);
- Toda a esteira é CPU-only e 100% local (local-first intacto; roda com o dono jogando — mesmo padrão da Forja da Fase 1);
- Procedência: qualquer ferramenta de licença restritiva que toque um asset fica registrada no `transform_log` do sidecar (ADR-003) — uma venda futura de peça sabe exatamente qual caminho ela percorreu;
- Nada muda na Fase C corrente: nenhum código é escrito agora (regra de uma fase por vez); este ADR apenas define o escopo da Fase 2 com antecedência.
