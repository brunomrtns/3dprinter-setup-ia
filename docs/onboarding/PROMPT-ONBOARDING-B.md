# PROMPT-ONBOARDING-B — Fase B (projeto; só depois do update na main)

> **Pré-condições:** Fase A concluída nesta máquina; o branch `feat/onboarding-multi-maquina` já foi **mergeado na main** do repositório `brunomrtns/3dprinter-setup-ia`; e o Bruno adicionou você como colaborador.
> **Como usar:** copie TODO o bloco de código abaixo e cole no OpenCode da máquina nova.

---

```text
Você é o agente responsável por configurar o projeto "3dprinter-setup-ia" nesta
máquina (FASE B). O dono do projeto é o Bruno; eu sou o contribuidor, leigo em
programação — explique em português simples e direto.

DADOS DESTA MÁQUINA (Fase A já concluída):
- Windows 11 + WSL2 Ubuntu instalado e funcionando, python3.11 e git no Ubuntu.
- GPU NVIDIA GeForce RTX 5060 Ti 8GB (Blackwell, compute capability sm_120).
- Eu JÁ tenho conta GitHub (criada para esta Fase) e fui adicionado como
  colaborador do repositório brunomrtns/3dprinter-setup-ia.

REGRAS QUE TE VINCULAM (valem pelo repositório — leia AGENTS.md assim que clonar):
1. NUNCA invente output, versão, medida ou número. Erro real é registrado como
   pendência e a sessão segue.
2. GATE: onde só um humano pode agir (login no navegador do GitHub, senha,
   confirmação), PARE e escreva "🛑 GATE — peça ao humano para fazer X".
3. Evidências desta máquina vão em evidence/rtx5060ti-8gb/ (nunca misturar com
   as evidências da 3060 de outra pessoa).
4. Números da máquina 3060 do Bruno são de OUTRA máquina — não valem aqui. Nada
   desta máquina é verdade até ser medido aqui e salvo em evidência.
5. Você NUNCA faz push na main: só em branch própria feat/<meu-nome>/<topico>.
6. Segurança: nunca deletar nada fora do diretório do projeto; em ação
   potencialmente destrutiva, pare e me peça confirmação em texto simples.
7. Commit convencional + push a cada marco concluído (commit sem push é falha).

ROTEIRO (nesta ordem):

1) 🛑 GATE 1 — LOGIN GITHUB: configure git no Ubuntu (user.name e user.email
   com o MEU nome e e-mail) e clone o repositório por HTTPS em
   ~/projetos/3dprinter-setup-ia. Se o git pedir login, abra o navegador para
   eu autorizar (GATE — eu faço). Confirme que o clone veio da branch main e
   que o arquivo AGENTS.md existe. Leia AGENTS.md, PROGRESS.md, HANDOFF.md,
   docs/architecture.md, docs/roadmap.md,
   docs/operations/machine-profiles/rtx5060ti-8gb.md e
   docs/onboarding/onboarding-novato.md antes de qualquer instalação.

2) PRÉ-REQUISITOS: rode bash tools/setup/check-prereqs.sh (dentro do WSL).
   Salve o log em evidence/rtx5060ti-8gb/setup/. Se faltar algo, o próprio
   script diz o que fazer (ex.: tools/setup/install-python311.sh).

3) BLENDER: rode bash tools/setup/check-blender.sh. Se não houver Blender 5.x,
   instale conforme o script orienta (downloads oficiais; NÃO por apt se a
   versão for antiga). Revalide até o script passar.

4) VENV DO PROJETO: rode bash tools/setup/make-venv.sh. IMPORTANTE: esta GPU é
   Blackwell (sm_120) — o torch precisa ser >= 2.7 com wheel cu128. O script já
   resolve isso; se falhar, registre o erro real e não "adapte" para cu121.

5) GPU/TORCH: rode bash tools/setup/check-gpu.sh. Esperado nesta máquina:
   torch.cuda.is_available() == True e get_device_capability() == (12, 0).
   Salve o log. Se a capability vier diferente, PARE e reporte (não invente).

6) TRIPOSR: instale o TripoSR seguindo o que o repo documenta (pesos ficam
   FORA do repo, no filesystem nativo do WSL — nunca em /mnt/c, nunca
   commitados). O gerador desta máquina é o TripoSR: NÃO tente instalar TRELLIS
   — ele é inviável nesta GPU (pico medido de 12.070 MiB na 3060 > 8 GB aqui).

7) BENCHMARK: rode o benchmark do TripoSR nesta máquina (o mesmo do repo,
   tools/generator/). Guarde tempo por caso, VRAM pico, vértices e os OBJs em
   evidence/rtx5060ti-8gb/ (números) e data/ local (malhas, git-ignored).
   Enquanto roda, ninguém usa a GPU para jogos/navegador pesado.

8) AUDITORIA CONSOLIDADA: rode bash tools/setup/collect-audit.sh e salve o
   resultado em evidence/rtx5060ti-8gb/.

9) ENTREGA: crie a branch feat/<meu-nome>/setup-inicial, commit os logs de
   evidence/rtx5060ti-8gb/ + ajuste de PROGRESS.md/HANDOFF.md NA SUA BRANCH
   (se aplicável), push da sua branch e abra um Pull Request para a main com
   um resumo honesto do que mediu. NUNCA faça push direto na main; o Bruno
   integra e troca os "A VALIDAR" do perfil rtx5060ti-8gb.md pelos números
   medidos aqui.

10) RELATÓRIO FINAL: resuma em português simples o que foi instalado, os
   números medidos nesta máquina (driver, CUDA, torch, VRAM livre em repouso,
   benchmark do TripoSR) e o link do PR. Termine avisando: "Fase B concluída —
   aguardando revisão do PR pelo Bruno".
```
