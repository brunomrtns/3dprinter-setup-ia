# 01 — Estudo Técnico: o que existe e como padronizar os modos de entrada

> Fonte: clonagem dos repos `3dprinter-setup-ia`, `portfolio-v2`, `avesia` (2026-11-20) +
> histórico dos runs fox_quality / fox_rearfix / pipe_std.
>
> **NOTA (2026-11-21):** "Fox" nos nomes de runs/configs é referência HISTÓRICA de receita
> (parâmetros validados) — a peça Fox é a **PIOR pintada do acervo** (2.086 UV islands,
> gutter bleed) e **NUNCA** serve de benchmark de qualidade. Qualidade-alvo = a MELHOR peça
> aprovada pelo dono. API em nuvem do TripoAI: **REJEITADA** (ADR-009) — pipeline 100% local.

## 1. O arsenal atual (3dprinter-setup-ia)

### 1.1 Pipeline de pintura (validado nos runs fox_quality / fox_rearfix)
Scripts em `pipeline/` (todos genéricos, zero nome de peça em código; parâmetros por asset em
`--config`, ex. `cars/fox.json`):

| Script | Papel |
|---|---|
| `paint_quality.py` | Hunyuan3D-Paint 2048 (seed 42) → SR x4 por vista → back-project → uv_inpaint |
| `photo_blend.py` | Alinhamento silhueta-IoU das fotos reais + transferência de detalhe com correção de iluminação (cos 0.80–0.92, w_max 0.8) |
| `patch_repair.py` | Reparo universal: pontos escuros 2D + micro-ilhas 3D + guarda de consistência fotográfica |
| `retexture_trellis.py` | TRELLIS.2-4B Trellis2TexturingPipeline → MetallicRoughness 2048 (PBR real) |
| `pack_glb.py` | Real-ESRGAN x4 → 8192/4096 JPEG q95 + MR PNG → GLB |
| `eval_texture.py` | QA: lap_var, patches %, saturação, consistência fotográfica, crops |
| `consolidate_quality_report.py` | report.json consolidado |

Contrato proposto pelo run `pipe_std` (prompt já entregue): `pipeline/defaults.json` (valores
aprovados do Fox como default global) + `assets/<id>.json` (só sobrescreve o que difere) +
`pipeline/run_asset.py` (1 comando, `--resume` por etapa) + QA PASS/FAIL automático.

### 1.2 Config real do Fox (exemplo vivo de `cars/fox.json`)
`asset_id carro_foxh`, seed 42, `work_dir ~/printer3d-work/carro/fox_fullrun`, variante `mv_b`
com `uv.obj` + `gt_views` (front/left/back/right = fotos reais R1/R2/R3/R2r),
`paint.target_texture_size 2048` / fallback 1024 / `vram_limit_mib 11000`.

### 1.3 Pré-processamento de entrada (já existe!)
`tools/generator/preprocess_input.py` (C2 concluído): **rembg (fundo removido) + pad quadrado
sem corte + 1024px** + sidecar de procedência (ADR-003). Ou seja: a "limpeza de fundo" que o
dono quer na interface **já está implementada** como etapa padrão do pipeline — a interface só
precisa comunicar isso (e oferecer o re-render externo como camada opcional, M5).

### 1.4 Guard e evidência
`tools/generator/gpu_guard.py` (paramétrico por perfil em `docs/operations/machine-profiles/`),
logger de VRAM 10s, `evidence/rtx3060-12gb/<run>/report.json`. Toda execução de job na Fábrica
herda isso.

### 1.5 Site MODELOS 3D (`tools/modelos3d-site/`)
`index.html + app.js (v19) + manifest.json + gen_manifest.py + deploy.sh` + three.js vendado.
v19: preserva material glTF quando há MR; MeshPhysicalMaterial (clearcoat 0.4, roughness 0.55,
RoomEnvironment) para albedo-only; NoToneMapping + SRGBColorSpace. É estático na VPS — a
Fábrica o absorve como **viewer de peça** (toggle pintado/sem pintura + download) dentro do app.

## 2. Os dois cenários provados (e o que cada um exige de entrada)

### Cenário A — Multi-foto ("receita Fox", qualidade máxima)
- **Entrada:** 3–4 fotos reais do MESMO objeto: front / side / back / side-repeat (padrão
  R1/R2/R3/R2r), capturadas com luz uniforme, objeto ocupando ~70% do quadro, fundo o mais
  limpo possível (rembg corrige o resto).
- **O que produz:** malha (Hunyuan3D-2mv multi-vista + TripoSF512 + pós-proc watertight, C6) ou
  malha existente; pintura 8K PBR com fidelidade real nas 4 faces.
- **Gargalo honesto:** a qualidade deste tier vem de fotos reais alinhadas (o que se aproveita
  do Fox é a receita/parâmetros — a peça em si é a pior do acervo). É o tier de topo do
  pipeline local.

### Cenário B — Single-image ("receita Anubis")
- **Entrada:** 1 foto (após `preprocess_input.py`: fundo removido, quadrado 1024).
- **O que produz:** malha via TripoSG→TripoSF512 (veredito C5: "o triposf512 ganhou, melhor até
  agora") — pintura ainda não validada neste caminho (M1 fecha isso com os tiers do pipe_std:
  tier "single" = Hunyuan single-view + TRELLIS cond na mesma imagem).
- **Uso na Fábrica:** o modo padrão para 1 foto (ex.: Anubis).

### Cenário C — Só malha (avançado)
- **Entrada:** arquivo de malha (GLB/OBJ/STL) já existente.
- **O que produz:** tier "none" do pipe_std — renders Blender neutros como conditioning +
  pintura/reparo/PBR. Para aprimorar peça que a IA já criou.

## 3. Resposta à pergunta do dono sobre o "módulo 360"

**Não precisa de grade 2×2 nem formato especial.** O padrão da Fábrica é **N fotos soltas
(1–4), cada uma um ângulo** — o pipeline alinha cada uma por silhueta-IoU (com validação:
IoU < 0.90 → foto descartada e relatada). A grade 2×2 foi o caminho antigo (variante `mv_a` do
Fox) e está **descontinuada** (veredito do dono: "só o primeiro que tá valendo"). Mais de 4
fotos = não validado; a UI limita a 4 e explica os ângulos ideais.

## 4. Modos de entrada padronizados da Fábrica (definição final)

| Modo | UI | Entrada | Pipeline | Qualidade esperada |
|---|---|---|---|---|
| **1 foto** | padrão | 1 imagem | preprocess (rembg+pad) → TripoSG→TripoSF512 → pintura tier "single" → PBR | Bom; fidelidade frontal alta, costas estimadas |
| **Multi-foto** | recomendado | 3–4 fotos (front/side/back/side-repeat) | preprocess → multi-vista (C6) → pintura tier "photos" (blending real) → PBR | **Máxima do pipeline local (multi-foto)** |
| **Peça existente** | avançado | malha OU peça já no sistema | tier "none" ou re-run de pintura/reparo sobre a peça | Acabamento máximo sobre a malha dada |

A UI guia por conteúdo: "Tenho só uma foto" / "Consigo fotografar de vários ângulos" /
"Quero melhorar uma peça que já existe". **Nenhuma configuração técnica aparece.**

## 5. Blueprint de plataforma (portfolio-v2 / avesia)

- **portfolio-v2** = "Bruno Martins — Portfolio & Platform": monorepo pnpm+Turbo, `apps/api`
  (Fastify + **Prisma**), `apps/web`, `packages/{shared,types}`. É o sistema de cadastro de
  pessoas onde a Fábrica se integra.
- **avesia** = SaaS clínico: MESMA família de stack + **`apps/worker-python`** (main.py,
  config.py, heartbeat.py, redis_client.py, storage.py, ai_provider.py) com plugin
  **`worker-auth`** na API e rota **`worker-heartbeat`** — o padrão exato de
  "PC local como worker de fila" que o dono já usa no Game Play Content Generator.
  Filas **BullMQ (Redis)**, storage **MinIO**, Postgres+Prisma, `packages/ai-providers`
  (ProviderRouter com fallback), React+Vite com `LoginPage.tsx`, `auth-store`, `theme-store`,
  RBAC/tenant, deploy nginx em `brunointegrations.com/<app>/`.
- **Conclusão:** a Fábrica NÃO inventa infraestrutura — clona o blueprint avesia (D3), trocando
  os domínios clínicos por peças 3D/jobs, e conectando o worker-python do PC ao pipeline real
  (`run_asset.py`) em vez dos consumers do avesia.

## 6. Agente de edição (Fase 4 do roadmap canônico)

O roadmap já reserva **Fase 4 — "Operador IA + entrega automática"**. Design compatível:
GLM via API Z.ai rodando **dentro do worker** (onde estão as ferramentas e a GPU), com catálogo
de ferramentas = scripts de `pipeline/` + blender + guard; toda ação logada em evidence;
publicação só com aprovação humana no chat. Detalhes de contratos e guardrails em 03 §6.

## 7. Lacunas que a Fábrica precisa fechar (checklist mental)

1. `pipe_std` concluído (runner único + QA PASS/FAIL) — **pré-requisito de tudo**.
2. Pintura validada em tier "single" (fecha a dúvida do Anubis).
3. API de jobs na VPS (não existe — C4 era FUTURO).
4. Worker consumindo a fila (avesia provou o padrão; falta o conteúdo 3D).
5. Viewer com toggle pintado/sem pintura + download (hoje só galeria fixa).
6. Auth "peça pertence a usuário" (tenant do avesia serve de modelo).
7. Migração/limpeza dos modelos de teste.
