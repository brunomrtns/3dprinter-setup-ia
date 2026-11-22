# ADR-007 — Encerramento da Fase C: Pipeline Oficial TripoSG → TripoSF 512 e Cancelamento do TRELLIS.2 como Gerador

- **Status:** Aceita (decisão do dono em 2026-11-22)
- **Data:** 2026-11-22
- **Supera:** `ADR-005-sem-default-mode.md` (explicitamente superada quanto à ausência de gerador padrão image→3D, ao eleger o pipeline oficial abaixo)
- **Relacionadas:** `ADR-001`, `ADR-003`, `ADR-006`, `ADR-008`, `ADR-009`, `ADR-010`

---

## 1. Contexto

A Fase 1 foi encerrada sem gerador padrão (`ADR-005`) após reprovação qualitativa global dos modelos de 1ª geração (`TRELLIS` v1 e `TripoSR`). A **Fase C** foi aberta em 2026-11-16 para atacar o elo mais fraco (pré-processamento de entrada C2) e avaliar a nova geração de geradores (`TripoSG`, `TripoSF 512`, `TRELLIS.2`, `Hunyuan3D-2mv`, `Hi3DGen`).

Durante os marcos C2, C3, C5 e C6 na RTX 3060 12 GB — e confirmado na prática durante a produção real de assets de jogo (Kit 4.0 do CONCERTO, 2026-11-22) — o **TripoSG** seguido de refino **TripoSF 512** entregou malhas sólidas, limpas e reproduzíveis, enquanto o **TRELLIS.2** como gerador de forma apresentou malhas abertas/esburacadas (`FlexiCubes` non-manifold, efeito picotado não curável por `fix_winding`).

## 2. Decisão (verbatim do dono, 2026-11-22)

1. **Fase C ENCERRADA.**
2. **Pipeline OFICIAL de geração image→3D:**
   ```text
   imagem → preproc C2 → TripoSG → refino TripoSF 512
   ```
   - Ferramenta one-command canônica: `tools/generator/pipeline_imagem3d.sh <imagem> <dir> [seed]` (já validada no smoke ponta-a-ponta do C5).
   - **Engine default do worker da Fábrica (`factory/worker/main.py`):** `triposg` (confirmado como default atual — não alterar).
   - Para impressão em resina/FDM: passar pela **Forja** (`tools/forja/` / `posproc_impressao.py`) após o TripoSF 512 (saída 512 não é watertight por padrão).
3. **TRELLIS.2 CANCELADO como gerador de forma:**
   - **C1** (fork `IgorAherne/TRELLIS.2-stableprojectorz` na máquina `rtx5060ti-8gb` do colega) está **CANCELADA** (alinhar com o colega fora do repo).
   - Qualquer plano futuro de geração de geometria com `TRELLIS.2` está cancelado.
   - **Distinção obrigatória (não confundir):** o estágio **`05_trellis_pbr`** (`pipeline/retexture_trellis.py`, que gera apenas o mapa físico `MetallicRoughness` sobre a malha já pintada pelo `Hunyuan3D-Paint`) **NÃO é cancelado** — faz parte do estado local restaurado pela `ADR-009` e não deve ser alterado sem ordem expressa do dono.
4. **Comparativo C3, Gate B (Hi3DGen) e C7-C (Hunyuan 2.1):**
   - Permanecem como **evidência histórica / experimentos futuros opcionais**.
   - Nenhum outro gerador é promovido automaticamente (`ADR-005` segue valendo como trava para todos os demais geradores não eleitos aqui).
   - **C7-C (Hunyuan 2.1)** só reabre mediante veredito explícito do dono no **Gate B**.
5. **Relação com ADR-005:**
   - Esta `ADR-007` **supera explicitamente a `ADR-005`** no ponto "nenhum default mode", elegendo `imagem → preproc C2 → TripoSG → TripoSF 512` (`engine=triposg` no worker) como o pipeline oficial do projeto.
   - `TRELLIS (v1)` e `TripoSR` permanecem descontinuados para produção.
   - `ADR-009` segue vinculante: **nunca** integrar API em nuvem do TripoAI em nenhuma etapa.

## 3. Consequências

- O worker `factory/worker/main.py` opera com `engine=triposg` como rota oficial padrão (`pipeline_imagem3d.sh` → `pipeline/run_asset.py`).
- O roadmap marca a **Fase C como `[x]` encerrada** e **C1 como CANCELADA**, liberando o foco para operação estável da Fábrica 3D (Fase P) e Forja (Fase 2).
- Novos experimentos de gerador (ex.: Hi3DGen no Gate B ou Hunyuan 2.1 em C7-C) continuam isolados em `evidence/` e nunca substituem o default sem nova ADR aprovada pelo dono.
