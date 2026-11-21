# ADR-009 — Pipeline 100% local: API em nuvem do TripoAI REJEITADA pelo dono (nunca mais)

**Status:** Aceito · **Data:** 2026-11-21 · **Fase:** P (Fábrica 3D)

## Contexto

O RUN `tripo_paint_v1` (commit `4f81db1`) propôs integrar a **API em nuvem do TripoAI** (endpoint `/v3/models/texture` + upload STS/S3) como **pintor principal** do pipeline, com o Hunyuan3D-Paint local rebaixado a fallback. Motivação declarada: alcançar "pintura perfeita de primeira" usando o serviço que o dono vê no produto TripoAI.

O dono **rejeitou a proposta na mesma data, de forma enfática e definitiva**: o motivo de existir deste projeto é justamente **não depender do TripoAI**. Se a solução para qualidade é pagar/depender da API do TripoAI, o projeto perde o sentido. O commit foi integralmente revertido (`git revert 4f81db1` → `ba801e6`, 828 linhas fora).

## Decisão

1. **NUNCA MAIS propor, planejar ou implementar integração com API/serviço em nuvem do TripoAI** — pintura, geração, textura, upscale ou qualquer outra etapa do pipeline. Esta é uma decisão vinculante do dono, válida para qualquer agente (AGENTS.md §1.1);
2. **Pintor principal = pipeline 100% local**: Hunyuan3D-Paint (BaseColor) + TRELLIS.2-4B (MetallicRoughness) + photo_blend/patch_repair/pack_glb — exatamente o estado anterior ao `tripo_paint_v1`, restaurado pelo revert;
3. **Não confundir**: os modelos open-source **locais** TripoSR / TripoSG / TripoSF (pesos abertos, rodam nas GPUs locais do projeto, com guard de VRAM) **continuam fazendo parte do arsenal** — eles NÃO são a API em nuvem e não são afetados;
4. A meta "pintura perfeita de primeira" continua, mas conquistada **no caminho local**: melhoria sistêmica de UV/atlasing, blending multi-foto, PBR local e QA numérico — não por chamada de serviço externo;
5. Qualidade de referência para qualquer benchmark/prompts = **a MELHOR peça aprovada pelo dono** — o Fox é a pior peça pintada do acervo e nunca serve de alvo de qualidade.

## Consequências

- Removidos do repo (revert `ba801e6`): `pipeline/tripo_client.py`, `pipeline/test_tripo_client.py`, integração provider em `run_asset.py`/`defaults.json`/`patch_repair.py`, `TRIPO_API_KEY` do `factory/worker/.env.example`, e o ADR-009 anterior (pintor principal tripo-api) — substituído por este;
- Nenhuma credencial de serviço externo de geração/textura entra no projeto (`.env` do worker não terá chaves de API de nuvem para esta finalidade);
- Custos de créditos/API externa: zero — todo o custo passa a ser tempo de GPU local (serializado com guard, como já é);
- O documento `docs/fase-p-fabrica3d/01_estudo_tecnico.md` e os prompts de run passam a tratar "receita Fox" como **histórico de parâmetros validados**, nunca como benchmark de qualidade;
- Qualidade da pintura local segue como o elo fraco declarado do pipeline — atacada por runs locais (ex.: UV melhor, blending, QA com gates), um de cada vez, com gate visual do dono.
