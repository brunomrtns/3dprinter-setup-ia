# Onboarding — novo contribuidor (leigo) numa máquina nova

> Roteiro completo para tirar uma máquina nova do zero (Windows 11, sem WSL, sem GitHub) até rodar o gerador de peças do projeto. Dividido em duas fases:
> - **Fase A** — base do ambiente (driver, WSL, Ubuntu, python, git, auditoria). **Independente deste update: pode rodar hoje.** Use `PROMPT-ONBOARDING-A.md` no OpenCode da máquina nova.
> - **Fase B** — projeto (clone, Blender, venv, TripoSR, benchmark). **Só depois do update `feat/onboarding-multi-maquina` estar na main.** Use `PROMPT-ONBOARDING-B.md`.
>
> Regra dos **GATEs**: onde só um humano pode agir (senha de admin, reiniciar o Windows, digitar algo num site), o roteiro diz **"🛑 GATE — PARE"** e o que pedir ao humano. O agente não pula GATEs e não finge que passou.
> Regra dos números: nada de inventar medida — a máquina nova só "existe" no projeto depois de enviar números reais (que vão para `docs/operations/machine-profiles/rtx5060ti-8gb.md` trocando cada "A VALIDAR").

---

## Fase A — base do ambiente (hoje, antes do update)

Meta: máquina com WSL2 Ubuntu funcionando, python 3.11, git, driver NVIDIA ativo no Windows, monitor WSL na área de trabalho e auditoria de ambiente enviada.

| # | Passo | Quem faz | GATE? |
|---|---|---|---|
| A1 | Verificar Windows 11 22H2+ e atualizações pendentes | agente (OpenCode) | não |
| A2 | Instalar WSL2 + Ubuntu: `wsl --install` (num PowerShell **como administrador**) | humano digita, agente orienta | 🛑 **GATE 1** — admin |
| A3 | Reiniciar o Windows (exigido pelo instalador do WSL) | humano | 🛑 **GATE 2** — reinício |
| A4 | Primeiro boot do Ubuntu: criar usuário e senha Linux (anote!) | humano digita | 🛑 **GATE 3** — senha |
| A5 | Instalar python 3.11 e git dentro do Ubuntu (apt) | agente | não |
| A6 | Conferir/atualizar driver NVIDIA **no Windows** (NVIDIA App ou site; GPU Blackwell exige driver recente) | agente baixa, humano confirma | 🛑 **GATE 4** — pode pedir admin/UAC |
| A7 | Provar CUDA visível dentro do WSL: `nvidia-smi` no Ubuntu (não instalar driver no WSL!) | agente | não |
| A8 | Instalar o monitor WSL da Área de Trabalho (docs/onboarding/monitor-wsl.md §5 — código portátil pronto) | agente | não |
| A9 | Auditoria de ambiente (driver, CUDA, VRAM livre, python, git, discos) e salvar em `evidence/rtx5060ti-8gb/` | agente | não |
| A10 | Enviar o resultado da auditoria ao Bruno (colar no chat) | humano/agente | não |

Detalhes por passo:

- **A2 (🛑 GATE 1)** — peça ao humano: abrir menu Iniciar → digitar "PowerShell" → clicar com o botão direito → **"Executar como administrador"** → colar `wsl --install --distro Ubuntu` e dar Enter. Aguardar terminar.
- **A3 (🛑 GATE 2)** — peça ao humano: salvar o que estiver aberto e **reiniciar o Windows**. Só continue depois do boot.
- **A4 (🛑 GATE 3)** — o Ubuntu abre uma janela pedindo `New UNIX username:` e senha. Humano escolhe (minúsculas, sem espaço) e **não esquece a senha**. Agente não digita senha por ele.
- **A5** — dentro do Ubuntu: `sudo apt update && sudo apt install -y python3.11 python3.11-venv git build-essential`. (Se `sudo` pedir senha, é a do passo A4 — humano digita.)
- **A6 (🛑 GATE 4)** — conferir a GPU: `nvidia-smi` no PowerShell do Windows. Se falhar ou o driver for antigo: baixar o mais recente (o app NVIDIA do Windows resolve). Baixar/instalar driver pode pedir UAC — humano confirma.
- **A7** — no Ubuntu: `nvidia-smi` deve mostrar a RTX 5060 Ti. Se dentro do WSL não aparecer driver: verificar se o driver do Windows está atualizado (A6) e `wsl --shutdown` e reabrir.
- **A8** — seguir `docs/onboarding/monitor-wsl.md` §5: criar `%USERPROFILE%\Scripts`, salvar os 3 scripts, gerar ícones, criar atalho e registrar o watcher no startup. Sem admin.
- **A9/A10** — auditoria (se este update já estiver na main: `bash tools/setup/collect-audit.sh`; senão: comandos manuais do PROMPT-A) — colar output real, sem inventar.

**Fim da Fase A quando:** `nvidia-smi` funciona nos dois lados, `python3.11 --version` e `git --version` respondem no Ubuntu, monitor instalado, auditoria enviada.

---

## Fase B — projeto (após o update estar na main)

Pré-condição: Fase A concluída + branch `feat/onboarding-multi-maquina` já mergeada na main do repositório.

| # | Passo | Quem faz | GATE? |
|---|---|---|---|
| B1 | Criar conta no GitHub (site, e-mail) e enviar o username ao Bruno | humano | 🛑 **GATE 5** — cadastro no navegador |
| B2 | Bruno adiciona o username como colaborador do repo (dono) | dono | aguarda dono |
| B3 | Configurar git (user.name/user.email) e clonar o repositório | agente | não |
| B4 | Pré-requisitos do projeto: `bash tools/setup/check-prereqs.sh` | agente | não |
| B5 | Instalar Blender 5.0.1 headless (se faltar) e validar: `bash tools/setup/check-blender.sh` | agente | não |
| B6 | Criar venv do projeto: `bash tools/setup/make-venv.sh` (python3.11 + **torch cu128** p/ Blackwell sm_120) | agente | não |
| B7 | Validar GPU + torch: `bash tools/setup/check-gpu.sh` (esperado: `get_device_capability() = (12, 0)`) | agente | não |
| B8 | Instalar TripoSR (pesos fora do repo, no filesystem nativo do WSL) | agente | não |
| B9 | Benchmark do TripoSR nesta máquina e salvar em `evidence/rtx5060ti-8gb/` | agente | não |
| B10 | Auditoria consolidada: `bash tools/setup/collect-audit.sh` + commit na branch própria + push + PR | agente | não |
| B11 | Bruno revisa PR e troca os "A VALIDAR" do perfil rtx5060ti-8gb pelos valores medidos | dono | aguarda dono |

Notas:

- **B1 (🛑 GATE 5)** — humano cria a conta em github.com (e-mail, senha) e informa o username. Agente não cria conta por ele.
- **B3** — clone por HTTPS é o caminho simples para o primeiro acesso (o GitHub vai pedir login no navegador — humano conclui o login se abrir prompt). Commits com o nome/e-mail do próprio contribuidor.
- **B6** — o torch da 3060 (cu121) NÃO serve aqui: Blackwell sm_120 exige PyTorch ≥ 2.7 wheels cu128 (perfil rtx5060ti-8gb). O `make-venv.sh` já instala a wheel certa para esta máquina.
- **B8/B9** — TRELLIS é **inviável** nesta GPU (pico medido de 12.070 MiB na 3060 > 8 GB total) — não tentar instalar. O gerador desta máquina é o **TripoSR**.
- **B10** — commit/push **apenas em branch própria** `feat/<nome>/<topico>`; nunca na main (AGENTS.md §Contribuidores). Evidências desta máquina sempre em `evidence/rtx5060ti-8gb/`.

**Fim da Fase B quando:** benchmark do TripoSR rodou com números reais salvos, PR aberto, e o perfil `rtx5060ti-8gb.md` foi atualizado pelo dono com os valores medidos.
