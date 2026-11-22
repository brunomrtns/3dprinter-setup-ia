# Painel Único de Gates Pendentes do Dono — `3dprinter-setup-ia`

> **Atualizado em:** 2026-11-22 (TAREFA 3 — RUN `fab3d_mega_v2`)
> **Fonte:** varredura integral do `PROGRESS.md` após encerramento da Fase C (`ADR-007`) e Lei 8 (`ADR-010`).
> Responda cada item apenas com **A** ou **B** em uma sentada só.

---

## Tabela Consolidada de Gates Abertos

| # | Gate / Pendência | Link / Onde Abrir | Pergunta Binária (**A** ou **B**) | O que cada resposta destrava |
|---|---|---|---|---|
| **1** | **Crash `paintfix_v2`** — olho esquerdo lavado/borrado (gatilho `paintfix_v2`) | https://brunointegrations.com/fab3d/?share=589ad043dfbd30ac35653a2433ebffd4 *(contact sheet: `evidence/rtx3060-12gb/paintfix_v2/etapa_c/crash_before_after_sheet.png`)* | **A:** Aprovar e publicar o Crash como está (`color_outliers=0,0099%` PASS, olho direito e dentes limpos)?<br>**B:** Rejeitar e abrir rodada cirúrgica de repintura no olho esquerdo (`pipeline/edit_mesh_region.py`)? | **A** → fecha `paintfix_v2` e promove o Crash para `published` na galeria.<br>**B** → abre tarefa focada de repintura regional no olho esquerdo antes de publicar. |
| **2** | **Gate B (C7-B)** — `Hi3DGen` vs `TripoSG` no `carro_nowin` | https://brunointegrations.com/modelos3d/?case=carro_nowin&mode=hi3dgen&vs=1&mode2=triposg *(evidência: `evidence/rtx3060-12gb/hi3dgen-carro/`)* | **A:** `Hi3DGen` venceu no hard-surface automotivo e vale investir em C7-C (`Hunyuan-2.1`) / reteste CSG?<br>**B:** Manter `TripoSG → TripoSF 512` (`ADR-007`) e arquivar `Hi3DGen` + `C7-C`? | **A** → destrava reteste do Kit CSG sobre base Hi3DGen e abertura opcional de C7-C (Hunyuan 2.1).<br>**B** → arquiva C7-B/C7-C como evidência histórica e mantém 100% do foco no pipeline oficial `ADR-007`. |
| **3** | **Job E2E TAREFA 2 (`e2e_anubis_triposg`)** — `engine=triposg` em `status=review` | Local: `evidence/fase-c/worker-triposg-e2e/qa.json` & `e2e_telemetry.json` · GLBs 8K/4K em `~/printer3d-work/worker-triposg-e2e/run/staged_models/` *(VPS review link `https://brunointegrations.com/fab3d/` aguarda restaurar `factory/worker/.env` no PC)* | **A:** Restaurar `factory/worker/.env` (`VPS_URL` + `WORKER_TOKEN`) para rodar `factory/worker/main.py --once` e ver o job na UI web?<br>**B:** Aceitar a validação E2E local como concluída (`506s`, `lap_var=8104`, `color_outliers=0,009%`, `MR=True`, `8K=16,62MB`/`4K=8,99MB`) e seguir? | **A** → fecha o último `[!]` da Tarefa 2 com job visível na UI web `/fab3d/` em `review`.<br>**B** → encerra o E2E da Tarefa 2 sem retrabalho e libera o PC para próxima frente. |
| **4** | **Lei 8 (`ADR-010`) — 2 Duplicidades Físicas no Disco (`1,55 GiB`)** | `docs/knowledge/inventario-pesos.md` (§Duplicidades Detectadas: `dinov3` `1,13 GiB` + `BiRefNet/RMBG-2.0` `423,9 MiB` entre `~/.cache/huggingface/hub/` e `~/tools/TRELLIS.2/MODELS/`) | **A:** Trocar as 2 cópias em `~/tools/TRELLIS.2/MODELS/` por symlinks apontando para o cache HF único?<br>**B:** Deixar as 2 cópias intactas por enquanto? | **A** → libera `1,55 GiB` e zera duplicidades no inventário da Lei 8.<br>**B** → mantém o disco como está até a próxima faxina. |
| **5** | **Próxima Prioridade Pós-Fase C (`ADR-007`)** | `docs/roadmap.md` (§Fase 2 Forja vs operação da Fábrica para o jogo CONCERTO) | **A:** Abrir a **Fase 2 (Catálogo completo da Forja)** no `3dprinter-setup-ia` agora?<br>**B:** Manter a Fábrica em operação estável (`v0.1.0-fab3d` + `ADR-007`) e focar no **C5 do CONCERTO** (substituição dos heróis/props no Caldeiral)? | **A** → inicia desenvolvimento dos ops individuais + validadores da Forja.<br>**B** → concentra GPU e tempo na produção dos assets C5 do CONCERTO usando o pipeline oficial `TripoSG`. |

---

## Itens Já Encerrados (Não Precisam de Decisão)
- **Fase C / C1 (TRELLIS.2 na 5060 Ti):** Encerrada/Cancelada via `ADR-007` (apenas alinhar com o colega fora do repo).
- **C3 (Comparativo 3060):** Encerrado como evidência histórica via `ADR-007`.
- **API TripoAI na nuvem:** Banida permanentemente via `ADR-009`.
