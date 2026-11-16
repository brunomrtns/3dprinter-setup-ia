# ADR-005 — Sem default mode: geradores image→3D reprovados qualitativamente pelo dono

**Status:** Aceito · **Data:** 2026-11-16 · **Fase:** 1 (fechamento)

## Contexto

A Fase 1 previa votação 👍/👎 do dono por caso nas galerias do benchmark para eleger o default mode (TRELLIS vs TripoSR). O benchmark técnico foi concluído com dados reais nas duas máquinas:

- 3060 (`evidence/benchmark/`): TRELLIS 65,7s/12.070 MiB pico, 3/10 OOM em casos densos, manifold 4/10 pós-reparo leve; TripoSR 27,3s/3.588 MiB, manifold 9/10, 0 erros;
- 5060 Ti (`evidence/rtx5060ti-8gb/benchmark/`): TripoSR 14,4s/4385 MiB, 10/10 OK; TRELLIS inviável (10/10 sem mesh — 8 GB < pico de 12.070 MiB).

Nas rodadas de vitrine anteriores (Jubarte r1/r2/B2), o TRELLIS já havia sido reprovado visualmente pelo dono três vezes ("não dá pra entender nada", "ficou ruim", fragilidade 0,315mm registrada).

Na votação, o dono **recusou o ritual por caso** e deu veredito global sem ressalvas: **"ficou tudo ruim" / "esse TripoSR é uma bosta"** — reprovação dos dois modos nas duas máquinas (`evidence/benchmark/votacao-dono.md`). O veredito é consistente com as métricas: TripoSR gera sólidos robustos mas de baixa fidelidade (~74k vértices, pouco detalhe); TRELLIS tem detalhe (257k vértices) mas casca fina (pct5 0,002–0,008), OOM em casos densos e histórico de reprovação visual.

## Decisão

1. **Nenhum default mode é eleito.** ADR-005 registra justamente a ausência: nenhum gerador image→3D local atual entra em uso produtivo do pipeline;
2. **Fase 1 encerra com veredito NEGATIVO do dono** — critério "dono aprova por caso e escolhe o default mode" NÃO atendido, e isso é o resultado honesto da fase (não é falha de execução: benchmark, infra, guard e portabilidade foram entregues e validados);
3. O **benchmark permanece válido como referência técnica** (tempos, VRAM, manifold) para quando novos geradores forem avaliados — nada é apagado;
4. O caminho de peças novas fica: (a) aguardar/avaliar gerador novo que passe no gate do dono (mesmo pipeline de benchmark vale), (b) caminho procedural Blender (opção já proposta nas rodadas Jubarte), ou (c) dono traz direção própria. Decisão de qual caminho seguir é do dono, em fase futura;
5. Forja (Fase 2), pipeline comum e validações **não são afetados** — reparo/operação de malha não depende da qualidade do gerador.

## Consequências

- Sem gerador em uso produtivo: módulo "Gerador de Peças" fica **parado até decisão do dono** (nenhuma instalação nova de pesos/modelos — regra de uma fase por vez);
- A infra da Fase 1 (venv por máquina, guard paramétrico, plugins, benchmark, auditorias) segue como ativo reaproveitável — avaliar gerador novo custa só o benchmark, não o setup;
- A votação por caso foi formalmente arquivada (`evidence/benchmark/votacao-dono.md`) — não reabrir sem motivo forte;
- Lição registrada: o gargalo não é infraestrutura nem pipeline — é a qualidade de saída dos geradores image→3D locais para o padrão do dono.
