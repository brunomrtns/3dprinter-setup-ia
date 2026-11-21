# Fábrica 3D — Suíte de Documentação (Fase P)

> **Nome de trabalho:** Fábrica 3D (`fab3d`) — provisório, o dono pode renomear.
> **Data:** 2026-11-20 · **Autor:** estudo preparado no chat (Z.ai) a partir dos repos públicos
> `3dprinter-setup-ia`, `portfolio-v2` e `avesia` + todo o histórico dos runs fox_quality / fox_rearfix / pipe_std.
> **Status:** aguardando ratificação do dono → vira ADR + Fase no `docs/roadmap.md` do monorepo.

## O que é isto

Série de documentos que define o próximo ciclo do projeto: transformar o pipeline de pintura/geração
validado (nível Fox) em um **produto de uso real**, integrado ao ecossistema Bruno Integrations:

- Interface web (padrão TripoAI de simplicidade) para gerar objetos 3D a partir de fotos;
- Máquina local (RTX 3060 12GB) como **worker** consumindo uma **fila de jobs** na VPS;
- **Modo edição agêntico**: chat onde um GLM (API Z.ai) opera o pipeline para aprimorar peças
  existentes sob pedido do usuário, sempre com gate humano antes de publicar.

## Documentos (ler nesta ordem)

| # | Arquivo | Conteúdo |
|---|---------|----------|
| 0 | [00_visao_geral.md](00_visao_geral.md) | Visão, princípios, escopo, segurança/licença, encaixe no roadmap canônico |
| 1 | [01_estudo_tecnico.md](01_estudo_tecnico.md) | Estudo do que existe: pipeline, cenários provados, modos de entrada padronizados, blueprint avesia |
| 2 | [02_prd.md](02_prd.md) | PRD de produto: personas, telas, jornadas, regras de UI, zero knobs de qualidade |
| 3 | [03_arquitetura.md](03_arquitetura.md) | Arquitetura: monorepo, VPS (api/web/storage), worker local, fila, contratos de API, agente GLM, segurança |
| 4 | [04_roadmap.md](04_roadmap.md) | Milestones M0–M7 com pré-requisitos e critérios de aceite; mapa de prompts |
| 5 | [05_checklist.md](05_checklist.md) | Checklist granular executável por milestone |

## Como usar

1. O dono lê 00 e 02 (visão + produto) e ratifica/corrige decisões.
2. `M0` os leva para dentro do monorepo (`docs/fase-p-fabrica3d/`) + ADR + PROGRESS.md.
3. Cada milestone subsequente = 1 prompt que eu (Z.ai) gero sob demanda, no mesmo formato dos
   runs anteriores (`prompt_*.md`), respeitando o contrato do `AGENTS.md` do repo.

## Regra de ouro desta suíte

**Zero segredos.** Esta suíte pode virar conteúdo público do repositório: nenhuma credencial,
IP, token, chave ou caminho sensível. Segredos vivem só em `.env` (VPS e PC, fora do git).
Uso estritamente **privado e pessoal**; proibido uso comercial — nota repetida em 00 e no PRD.
