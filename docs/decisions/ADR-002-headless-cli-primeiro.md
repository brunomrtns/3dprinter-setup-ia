# ADR-002 — Headless/CLI primeiro, UI depois (se houver dor real)

**Status:** Aceito · **Data:** 2026-11-03 · **Fase:** 0

## Contexto

O sistema é **operado por agentes de IA** (o dono alterna OpenCode/Claude/Antigravity — AGENTS.md), que são nativos de CLI. Além disso, o dono já possui um painel visual completo — o PrintFlow3D — que é o destino final de todo asset. Construir UI intermediária seria duplicar o que já existe e adicionar superfície de manutenção sem usuário humano no meio do fluxo.

## Decisão

1. Toda funcionalidade nasce como **script/CLI headless** com saída estruturada (JSON + exit code), invocável por qualquer agente: `wsl blender -b -P ...`, `wsl ~/.venvs/printer3d-ia/bin/python ...`;
2. Visualização humana vem de: **preview render** padronizado do pipeline (PNG) e do painel **PrintFlow3D** (entrega via API);
3. **UI própria só se houver dor real** demonstrada (ex.: dono precisando ajustar pose manualmente com feedback visual e o preview render não der conta). Nesse caso, a UI consumirá os mesmos contratos CLI — nada de lógica nova fora deles.

## Consequências

- Automação total desde o dia 1, validável por exit code (evidências em `evidence/`);
- Zero esforço de frontend até a Fase 4; o operador IA (Fase 4) é um consumidor a mais dos mesmos contratos;
- UX manual improvisada fica limitada até lá — risco aceito, mitigado pelo preview render e pelo painel existente;
- Se a UI um dia nascer, não há retrabalho de backend: ela nasce consumindo os contratos já versionados.
