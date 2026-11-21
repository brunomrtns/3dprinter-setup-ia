# 00 — Visão Geral (Fábrica 3D)

## 1. O salto

Até aqui o projeto foi um **laboratório**: runs controlados, 1 prompt = 1 run, gates do dono,
evidência pesada. O ciclo se fecha com dois resultados provados e aprovados:

- **Cenário multi-foto** (carro Fox `mv_b`): 4 fotos reais → malha + pintura 8K com PBR real
  (BaseColor Hunyuan 2048 + blending de fotos + reparo genérico + MetallicRoughness TRELLIS.2).
- **Cenário single-image** (Anubis): 1 foto pré-processada → TripoSG→TripoSF512, melhor resultado
  de geração até então (C5). Pintura ainda NÃO validada nesse cenário (fica no M1/pipe_std).

A **Fábrica 3D** é o produto que embala esse arsenal: o usuário entra (login padrão Bruno
Integrations), sobe fotos, e a peça sai pintada em qualidade máxima, hospedada na VPS, com
download e um chat de aprimoramento operado por IA.

## 2. Princípios (não negociáveis)

1. **Zero knobs de qualidade.** O produto não expõe sliders técnicos. 8K sempre, PBR sempre,
   seed 42 sempre, QA automático sempre. A única escolha do usuário é o **modo de entrada** e as
   fotos. (Regra do dono: "não inventa muita configuração".)
2. **Gate humano sempre.** Nada é publicado sem aprovação visual do dono no review (a máquina
   não publica coisa feia; o QA automático filtra, o dono decide).
3. **Estado em arquivos, não em conversa** (contrato do `AGENTS.md`): PROGRESS.md, HANDOFF.md,
   ADRs. Esta suíte é a documentação que permite retomar o caminho a qualquer momento.
4. **Docs antes de código** (contrato do repo): ADR + roadmap antes de qualquer implementação.
5. **Local-first + procedência** (ADR-003): nenhum asset de terceiro sai da máquina; peças
   públicas só com procedência OK. Repos remix 🔴/🟡 jamais publicados.
6. **GPU serializada** (regra 9 do AGENTS.md): a fila de jobs é serial — um job de GPU por vez,
   guard de VRAM sempre (`tools/generator/gpu_guard.py`).
7. **Worker com permissão ampla, escopo monitorado.** O worker no PC do dono executa comandos
   do pipeline; toda execução é logada em evidence; publicação só via gate humano.

## 3. Escopo

### Dentro
- App web integrado ao ecossistema Bruno Integrations (login padronizado, tema padrão).
- Wizard de criação com **modos de entrada padronizados** (ver 01 §4).
- Fila de jobs VPS ↔ worker local (o padrão "Game Play Content Generator" / `apps/worker-python`
  do avesia), **um único worker** (PC do dono). Fila aguarda o PC estar ligado.
- Viewer de peça (evolução do MODELOS 3D v19) com **toggle Pintado/Sem pintura** e **download
  GLB** (8K/4K).
- **Assistente de entrada**: limpeza de fundo das fotos (já embutida no pipeline via
  `preprocess_input.py`/rembg) + oferta opcional de re-render por IA externa (Gemini/Nano Banana)
  para fotos ruins (M5).
- **Modo edição agêntico**: chat por peça; GLM (API Z.ai) escolhe e executa ferramentas do
  pipeline; resultado volta para review.
- Migração dos modelos existentes: manter o aprovado, apagar o resto após backup.

### Fora (explícito, para não inchar)
- Múltiplos workers / escalonamento horizontal (decisão do dono: só o PC local).
- Modo mobile-app/nativo (web responsivo basta).
- Faturamento/planos/usuários pagos — **uso privado**, sem comercialização.
- Fase 3 (Estúdio de Pose) e Forja completa — permanecem fases próprias do roadmap canônico.

## 4. Encaixe no roadmap canônico

O `docs/roadmap.md` do `3dprinter-setup-ia` já prevê: **C4 — "Fila de jobs entre máquinas"**
(marcado FUTURO) e **Fase 4 — "Operador IA + entrega automática"** (não aberta). Esta suíte
**absorve e concretiza** os dois, com camada de produto em cima:

- Proposta: abrir **Fase P — Fábrica 3D (produto)** que consome M1 (pipe_std) e antecipa partes
  de C4/Fase 4. Decisão estrutural → **ADR novo (008+)**: "Fábrica 3D: plataforma de produto
  integrada ao ecossistema Bruno Integrations com worker local".
- Nada disso cancela Fase 2 (Forja) ou Fase 3 (Pose) — seguem no roadmap.

## 5. Segurança e licença (repetir em todo doc gerado)

1. **Uso estritamente privado e pessoal. Proibido uso comercial**, venda, sublicenciamento ou
   prestação de serviço com os modelos/imagens gerados. Apenas o dono e contas que ele
   explicitamente criar no seu sistema de cadastro usam a ferramenta.
2. **Zero segredos em docs/código commitado**: sem chaves de API (Z.ai, Gemini/Nano Banana),
   sem credenciais SSH/VPS, sem tokens. Tudo em `.env` fora do git (VPS e PC).
3. O repositório é **público** (clonável sem auth) — tratar todo byte commitado como público.
4. Imagens/modelos do dono: dados pessoais; a VPS não os expõe sem login exceto peças que o
   dono publicar explicitamente na galeria.
5. Uploads de usuários: validar tipo/tamanho; quarentena antes de tocar o worker.

## 6. Decisões que o dono precisa ratificar (gate M0)

| # | Decisão | Recomendação |
|---|---------|--------------|
| D1 | Nome do produto e URL (ex.: `brunointegrations.com/fab3d`) | "Fábrica 3D" / `/fab3d` |
| D2 | Qual modelo/peça entra na galeria inicial | Fox `mv_b` 8K/4K + Anubis vencedor; resto backup+delete |
| D3 | Stack da VPS | Clonar blueprint avesia (Fastify+React+Postgres+Redis+MinIO+worker-python) |
| D4 | Provedor do agente de edição | API Z.ai com GLM (chave só no `.env` do worker) |
| D5 | Re-render externo de imagem (M5) | Gemini/Nano Banana opcional; default = limpeza local rembg |
| D6 | Acesso | Só o dono no M4; cadastro de outros usuários depois, no padrão Bruno Integrations |
