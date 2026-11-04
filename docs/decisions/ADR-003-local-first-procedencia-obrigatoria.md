# ADR-003 — Local-first + procedência obrigatória

**Status:** Aceito · **Data:** 2026-11-03 · **Fase:** 0

## Contexto

Os insumos são modelos 3D de **terceiros de origem variada** (sites de download, Patreon, packs). Enviá-los a serviços de nuvem (upload para IA hosted, APIs de reparo, etc.) vazaria dados de terceiros e criaria dependência externa. Além disso, o painel de destino — PrintFlow3D — **não captura licença/autor** nos importadores (gap verificado), o que tornaria impossível distinguir um remix publicável (CC0/CC-BY) de um uso pessoal que jamais deve sair da máquina.

## Decisão

1. **100% local**: todo processamento (geração, reparo, validação, render) roda na máquina do dono (Windows + WSL2, RTX 3060). Nenhum arquivo de terceiro sai da máquina; nenhum serviço de nuvem entra no fluxo;
2. **Procedência obrigatória**: todo asset que entra no sistema ganha um **sidecar JSON** antes da primeira operação — origem (URL/autor), licença, triage 🟢/🟡/🔴, SHA-256 do original e `transform_log` (um append por operação);
3. **Sem sidecar, não processa** — o pipeline rejeita asset sem procedência registrada;
4. Publicação de remix exige cadeia inteira 🟢 (CC0/CC-BY com crédito quando exigido).

## Consequências

- Privacidade e segurança jurídica: sempre é possível responder "de onde veio esta peça e o que fizeram com ela" consultando o sidecar;
- Custo comportamental: disciplina de registro no ingestion — mitigada tornando o registro pré-condição técnica (gate), não boa vontade;
- A triage pode viajar nas `tags` do upload ao PrintFlow3D como metadado auxiliar, mas o registro canônico é o sidecar local (o gap do painel é tratado aqui, não lá);
- Sem dependência de internet para processar (só para downloads deliberados de assets/pesos).
