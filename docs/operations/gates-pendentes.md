# Painel Único de Gates Pendentes do Dono — `3dprinter-setup-ia`

> **Atualizado em:** 2026-11-22 (TAREFA 1 — RUN `mega_v3`, vereditos gravados: **`1C(ARQUIVAR) · 2B · 3B · 4B · 5B`**)
> **Estado:** Todos os 5 gates operacionais da Fábrica estão **FECHADOS** — foco deslocado para o **C5 do CONCERTO** (`game-concerto`).

---

## Tabela Consolidada de Gates (Vereditos Gravados em 2026-11-22)

| # | Gate / Pendência | Link / Evidência RAW | Veredito (2026-11-22) | Justificativa & O que destrava |
|---|---|---|---|---|
| **1** | **Crash `paintfix_v2`** — olho esquerdo lavado/borrado | https://raw.githubusercontent.com/brunomrtns/3dprinter-setup-ia/main/evidence/rtx3060-12gb/paintfix_v2/etapa_c/crash_before_after_sheet.png · [qa.json](https://raw.githubusercontent.com/brunomrtns/3dprinter-setup-ia/main/evidence/rtx3060-12gb/paintfix_v2/etapa_c/qa.json) | **`1C` — CRASH ARQUIVADO SEM REPAINT** | Peça de TESTE de pintura do acervo, não é asset do jogo — **zero GPU nela**. O fix regional de outliers **FUNCIONOU** (`0,184% → 0,0099%`) e é esse método que os props/heróis do C5 herdam; o olho esquerdo lavado fica registrado como limitação CONHECIDA da pintura (atacar nos HERÓIS do M1 se aparecer na Porca/Dez). Peça **NÃO publica**; `paintfix_v2` encerrado como aprendizado. |
| **2** | **Gate B (C7-B)** — `Hi3DGen` vs `TripoSG` no `carro_nowin` | https://raw.githubusercontent.com/brunomrtns/3dprinter-setup-ia/main/evidence/rtx3060-12gb/hi3dgen-carro/scores.md · [normal.png](https://raw.githubusercontent.com/brunomrtns/3dprinter-setup-ia/main/evidence/rtx3060-12gb/hi3dgen-carro/normal.png) | **`2B` — MANTER `TripoSG → TripoSF 512` (ADR-007)** | Arquiva `Hi3DGen` e `C7-C (Hunyuan 2.1)` como evidência histórica. **Nota honesta:** o normal map do `Hi3DGen` é limpo e o runner é ~2× mais rápido — fica documentado como caminho rápido conhecido para hard-surface automotivo, reabrível barato (venv + evidence preservados), mas **SEM track novo agora**. |
| **3** | **Job E2E (`e2e_anubis_triposg`)** — `engine=triposg` em `status=review` | https://raw.githubusercontent.com/brunomrtns/3dprinter-setup-ia/main/evidence/fase-c/worker-triposg-e2e/e2e_telemetry.json · [qa.json](https://raw.githubusercontent.com/brunomrtns/3dprinter-setup-ia/main/evidence/fase-c/worker-triposg-e2e/qa.json) | **`3B` — E2E LOCAL ENCERRADO** | Validado como teste de encanamento (`506s`, `0` OOM, guard 10 GB intacto, glob `*_reconstruction.obj` casado, GLBs 8K/4K sãos, `watertight=false` esperado no 512). **Nota honesta:** `qa_pass=false` por `bright_patches` (`0,6115%`) é sinal do elo fraco PINTURA, não de encanamento — peça permanece em `review` (não vai pra galeria). Restaurar `factory/worker/.env` segue como ação HUMANA de 1 linha. |
| **4** | **Lei 8 (`ADR-010`) — 2 Duplicidades Físicas (`1,55 GiB`)** | https://raw.githubusercontent.com/brunomrtns/3dprinter-setup-ia/main/docs/knowledge/inventario-pesos.md | **`4B` — DUPLICIDADES ACEITAS** | As 2 duplicidades (`dinov3` `1,13 GiB` + `BiRefNet/RMBG-2.0` `423,9 MiB`) ficam **ACEITAS**: a cópia em `~/tools/TRELLIS.2/MODELS/` é canônica do TRELLIS.2 (que segue rodando em `05_trellis_pbr` e como fallback oficial do jogo). Reabre só sob pressão real de disco, com teste obrigatório do `05_trellis_pbr` após symlink. |
| **5** | **Próxima Prioridade Pós-Fase C (`ADR-007`)** | `docs/roadmap.md` | **`5B` — FOCO NO C5 DO CONCERTO** | Fase 2 (Forja) preservada como próxima fase da Fábrica quando houver demanda de impressão; prioridade imediata = **C5 do CONCERTO** (props batch-1 + conceitos Porca/Dez em `game-concerto`). |

---

## Itens Já Encerrados (Histórico)
- **Fase C / C1 (TRELLIS.2 na 5060 Ti):** Encerrada/Cancelada via `ADR-007`.
- **C3 (Comparativo 3060):** Encerrado como evidência histórica via `ADR-007`.
- **API TripoAI na nuvem:** Banida permanentemente via `ADR-009`.
