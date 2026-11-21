# 02 — PRD: Fábrica 3D (produto)

> Uso privado e pessoal. Proibido uso comercial. Zero segredos neste documento (ver 00 §5).

## 1. Persona e problema

**Bruno (dono)** — cria e imprime peças 3D; hoje o arsenal de geração/pintura exige comandos
manuais na máquina local. Quer transformar isso em ferramenta de uso contínuo, com a
simplicidade de um TripoAI: sobe fotos → peça pintada em qualidade máxima → revisa → baixa ou
pede ajustes conversando com a IA.

**Convidados futuros** — contas criadas pelo dono no sistema de cadastro (Bruno Integrations),
mesmo fluxo, isoladas por usuário.

## 2. Regras de produto (o "não inventa")

1. **Qualidade sempre máxima e invisível**: 8K, PBR, seed 42, QA automático. Nenhum slider,
   dropdown técnico ou "modo avançado" de qualidade. O usuário escolhe: nome da peça, modo de
   entrada, fotos. Nada mais.
2. **Um jeito por vez**: cada job tem UM modo de entrada (1 foto / multi-foto / peça existente).
3. **Assistente antes de erro**: foto com fundo bagunçado não é erro — o sistema limpa (rembg,
   embutido) e oferece re-render por IA externa quando a foto estiver fraca (M5).
4. **Fila honesta**: o PC do dono não está sempre ligado. A UI mostra "na fila" com posição e
   status por etapa do pipeline; o job continua quando o PC volta.
5. **Nada publica sozinho**: QA automático filtra; aprovação visual do dono publica.
6. **PT-BR, tema padrão Bruno Integrations, responsivo** (mesma linguagem visual das outras
   aplicações — `LoginPage`/`theme-store` do padrão avesia).

## 3. Telas

### T3.1 Login (padrão)
Login do ecossistema (mesmo tema/fluxo das demais apps). Sem cadastro self-service na Fase P.

### T3.2 Minhas Peças (home)
- Grid de cards: thumbnail (render 3/4), nome, data, status (Publicada / Em fila / Precisa de revisão).
- Ações por card: **Ver** (abre T3.4), **Download** (GLB 8K/4K), **Aprimorar** (abre T3.5),
  excluir (confirmação; apaga só o registro do usuário, mantém evidência no PC).
- Botão primário: **Nova Peça** → T3.3.

### T3.3 Nova Peça (wizard, 3 passos)
- **Passo 1 — Como você quer criar?** 3 cartões com linguagem de usuário:
  - "Tenho uma foto" (1 foto)
  - "Consigo fotografar de vários ângulos" (multi-foto, recomendado — badge "melhor qualidade")
  - "Quero melhorar uma peça que já existe" (peça existente)
- **Passo 2 — Fotos**: upload/arrastar (1 ou até 4). Dica visual de ângulos (frente/lado/costas/
  lado repetido) com exemplo do Fox. Validação client-side (formato, resolução mínima, tamanho).
  Badge automático "Fundo será removido automaticamente". Se a foto estiver fraca (escura/
  complexa), oferta: "Gerar foto padrão com IA (Gemini/Nano Banana)" (M5).
  No modo peça existente: escolher peça do sistema OU subir malha (GLB/OBJ/STL).
- **Passo 3 — Confirmar**: nome da peça + observações livres (opcional) → "Enviar para fila".

### T3.4 Detalhe da Peça (viewer)
- Viewer three.js (base MODELOS 3D v19): orbit, zoom; **toggle Pintado / Sem pintura**
  (sem pintura = material neutro sem textura — para avaliar geometria antes de imprimir).
- Downloads: **GLB 8K** e **GLB 4K** (e malha/STL quando existir).
- Painel lateral: histórico de jobs (etapas, tempos, VRAM — resumo), resultado do QA
  (gates PASS/FAIL legíveis: nitidez, falhas de pintura, consistência), renders de revisão.
- Botão **Aprimorar** → T3.5.

### T3.5 Chat de Edição (modo agêntico)
- Chat dentro do detalhe da peça. Usuário escreve em linguagem natural ("tirar os rabiscos
  pretos da traseira", "deixar o vidro mais brilhante").
- Agente responde com PLANO (ferramentas que vai usar) → executa no worker → devolve renders
  antes/depois → usuário aprova ou pede mais.
- Limites visíveis: um job de edição por vez; aprovação humana obrigatória para publicar.

### T3.6 Fila & Status
- Página/lista com jobs ativos: posição na fila, etapa atual do pipeline (nomes amigáveis:
  "Limpando fotos…", "Esculpindo malha…", "Pintando em 8K…", "Aplicando brilho/PBR…",
  "Conferindo qualidade…"), estimativa baseada em tempos históricos, "PC offline — aguardando
  worker" quando aplicável.

## 4. Jornadas principais

### J1 — Criar peça nova (caminho feliz, multi-foto)
Login → Nova Peça → "vários ângulos" → sobe 3–4 fotos → nomeia → fila → (PC liga, worker pega)
→ status por etapa → review: renders + QA → dono aprova → publicada → ver/download.

### J2 — Criar com 1 foto (Anubis)
Igual J1 com modo 1 foto; QA de tier single (gates ajustados); expectativa exibida honestamente
("fidelidade máxima na frente; costas geradas pela IA").

### J3 — Aprimorar peça existente (edição agêntica)
Detalhe → Aprimorar → "os rabiscos da traseira persistem, também quero mais brilho no vidro" →
agente propõe plano (ex.: patch_repair + ajuste de roughness/PBR) → executa → antes/depois →
dono aprova → nova versão publicada (histórico mantido; versão anterior fica acessível).

### J4 — Foto ruim
Upload → sistema detecta fundo/qualidade → remove fundo automaticamente (já no pipeline) →
se ainda fraca → oferta re-render IA (M5) → usuário confirma → segue o fluxo normal.

## 5. Requisitos não-funcionais

| Área | Requisito |
|---|---|
| Desempenho percebido | Job multi-foto completo ≤ ~40 min na 3060 (paint ~5 min, PBR ~3 min, malha varia); UI mostra etapa em tempo real |
| Confiabilidade | Job nunca se perde: estados persistidos; retomada por etapa (`--resume` do run_asset); falha = mensagem clara + evidência |
| Privacidade | Peças e fotos por usuário; download autenticado; galeria pública só do que o dono publicar |
| Auditoria | Toda execução do worker logada em `evidence/`; chat do agente persistido por job |
| Acessibilidade/UI | Responsivo (celular/tablet/desktop), tema padrão, PT-BR, sem jargão técnico para o usuário final |

## 6. Métricas de sucesso (v1)

- Pintar 1 peça do início ao fim sem abrir terminal.
- ≥ 90% dos jobs multi-foto passam QA automático de primeira (gates do Fox).
- Ciclo de edição: pedido → resultado aprovado em ≤ 2 interações.
- Zero incidente de segurança (segredos vazados, publicação indevida).
