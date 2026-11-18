# PROMPT-C6 — Hunyuan3D-2.1 multi-vista + fotogrametria (VGGT) — rodar na IA do Bruno (3060)

> **Como usar:** cole TODO o bloco de código abaixo no OpenCode da máquina do Bruno. Foi escrito pela IA anterior que ficou sem crédito — o dono pediu handoff documentado. **Regra de ouro do dono: atualize PROGRESS.md com frequência e faça commit+push a cada marco — os créditos dele acabam rápido.**

---

```text
Você opera na máquina do dono (Bruno, rtx3060-12gb), no WSL2 Ubuntu 26.04, no repo
3dprinter-setup-ia. Leia ANTES de executar: AGENTS.md, PROGRESS.md (seção "carro fox"
e "PROMPT-C6"), HANDOFF.md, e evidence/fase-c/comparativo-3060/install-notes.md
(armadilhas do ambiente — /tmp volátil, background morre com sessão wsl, gcc-14,
CUDA toolkit em ~/cuda-12.8 com patch de header). Regras do contrato valem: nada
inventado, evidência real, guard de VRAM, commit convencional + push a cada marco.

CONTEXTO (veredito real do dono, 2026-11-18):
- O CARRO FOX (Downloads/fox) AINDA NÃO FICOU BOM: "frente fica bom atras fica ruim,
  atras fica bom frente fica ruim". Anubis ficou aceitável/imprimível; carro não.
- DADO IMPORTANTE do veredito: no carro, TRELLIS.2 ficou MELHOR que o TripoSG
  (invertendo o gate C5 do anubis). Registre isso — dado real.
- Diagnóstico aceito pelo dono: geradores single-view adivinham o lado invisível.
  Ele quer: modelo local que aceita VÁRIAS imagens do mesmo objeto (ou gerar a partir
  de várias vistas) e modela todos os lados. "Tenho recurso pra isso."
- Já existe em ~/printer3d-work/carro/: front/back/all gerados (trellis2, triposg,
  triposf512 — 9 GLBs no viewer, casos carro_front/carro_back/carro_all) e
  ~/printer3d-work/carro/vistas/{v1_esq,v2_meio,v3_dir}.png (terços do all.webp
  recortados às cegas — CONFIRME com o dono qual é frente/lado/trás antes de usar).

TAREFA A — HUNYUAN3D-2.1 MULTI-VISTA (prioridade):
1) git clone https://github.com/Tencent-Hunyuan3D-2.1.git → ERRADO, o repo é
   https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1.git em ~/tools/Hunyuan3D-2.1.
2) venv PRÓPRIO ~/.venvs/hunyuan (ADR-004; padrão dos venvs triposg/trellis2).
   README oficial testa torch 2.5.1+cu124/py3.10 — nesta máquina use python3.11 e
   torch 2.8.0+cu128 (padrão que já funciona nos outros venvs, sm_86 OK). Instale o
   requirements.txt do repo. PESOS: tencent/Hunyuan3D-2.1 no HF (NÃO gated) — baixe
   SÓ o subfolder de forma (hunyuan3d-dit-v2-1 + hunyuan3d-vae-v2-1, ~7GB) via
   snapshot_download com allow_patterns; textura (paintpbr, 21GB VRAM) NÃO CABE e
   NÃO é necessária para impressão.
3) USO SHAPE-ONLY (10GB VRAM segundo o README — cabe na 3060 com guard):
   from hy3dshape.pipelines import Hunyuan3DDiTFlowMatchingPipeline
   pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained('tencent/Hunyuan3D-2.1')
   mesh = pipeline(image=...)[0]
   VERIFICAÇÃO CHAVE: o pipeline aceita MÚLTIPLAS imagens? Leia demo.py/gradio_app.py
   do repo clonado — o gradio oficial vende "multi-view input" (a API pode aceitar
   lista em image=[...] ou ter parâmetro de cond extra). Se NÃO existir modo
   multi-imagem: registre honesto e rode single-view na MELHOR vista (frente).
4) Gere o carro fox: (a) multi-vista com frente+trás (e lateral do vistas/ se o dono
   confirmar qual terço é); (b) se só der single-view, gere frente e trás separadas.
   Entradas SEMPRE pelo preprocess_input.py (C2) antes. Seed 42. Guard: venv_py no
   padrão dos plugins (vram_min_free_mib ~9500) — crie tools/generator/hunyuan_
   runner.py + hunyuan_plugin.py seguindo trellis2_plugin.py como molde (runner
   imprime REPORT_JSON=..., plugin define venv_py).
5) Pós-geração: decima ~600k faces (pymeshlab; OBS: precisa de libopengl0 — JÁ
   instalado), GLB em ~/printer3d-work/modelos3d-site/models/carro_mv__<modo>.glb,
   adicione caso "carro_mv" no tools/modelos3d-site/manifest.json (molde: entrada
   carro_front), rode tools/modelos3d-site/deploy.sh e VALIDE ao vivo (curl 200 no
   GLB + manifest). Telemetria real (tempo, VRAM pico via VramPoller do gpu_guard)
   em evidence/rtx3060-12gb/hunyuan-carro/ com log completo.
6) Compare no viewer (VS): carro_mv vs carro_front/trellis2 (o melhor atual segundo
   o dono). GATE: veredito visual do dono → se vencer, candidato a pipeline oficial
   (ADR novo, substituindo TripoSG→TripoSF no fluxo imagem→3D ou entrando como
   etapa multi-vista). NÃO promova sem veredito.

TAREFA B — FOTOGRAMETRIA FEED-FORWARD (VGGT), preparação:
1) Monte venv ~/.venvs/vggt com o repo https://github.com/facebookresearch/VGGT
   (MIT; entrada: N fotos → poses + point maps densos; roda em ~8-12GB) + pesos
   facebook/VGGT no HF (não gated). Torch cu128, python3.11.
2) Escreva tools/generator/vggt_recon.py: N imagens → nuvem densa (confiança
   filtrada) → Poisson (open3d) → malha → trimesh → GLB. Roteiro de captura pro
   dono (docs/onboarding/captura-fotogrametria.md, leigo): 20-40 fotos circulando
   o carro, ~70% de sobreposição, luz difusa, fundo limpo se possível, SEM zoom
   digital; colocar o carro numa superfície com marcas ajuda o registro.
3) Se o dono trouxer fotos, rode e publique como caso "carro_foto" no viewer.
   Fotogrametria MEDe a realidade (não inventa) — provavelmente o melhor caminho
   para "máxima fidelidade" em objeto físico que ele pode fotografar.

REGRAS DE SESSÃO (dono pediu explicitamente):
- PROGRESS.md atualizado a CADA marco (não só no fim); commit+push frequente;
- se um caminho falhar 2x pelo mesmo motivo, registre pendência e siga o outro;
- GPU serial com guard; nada de peso dentro do repo; evidência namespaced
  (evidence/rtx3060-12gb/ para esta máquina);
- ao final: atualize PROGRESS/HANDOFF, git status limpo, push, e relate com LINK
  do viewer pro dono julgar.

Relatório final em português simples, com o link do viewer.
```
