# Glossário para leigo

> Termos que aparecem no projeto, explicados sem jargão. Ordem alfabética.

| Termo | O que é (versão simples) |
|---|---|
| **Agente** | Programa de IA que usa o computador sozinho: lê arquivos, roda comandos, escreve código. Você fala o que quer (numa mensagem, o "prompt") e ele executa passo a passo. OpenCode é um agente. |
| **Branch** | "Galha" do projeto dentro do git. Você trabalha na sua galha sem mexer na versão principal (a `main`). Quando termina, propõe juntar as galhas (o PR). Convenção aqui: `feat/<seu-nome>/<assunto>`. |
| **Commit** | "Foto" salva das suas mudanças num momento, com um texto explicando o que mudou. O histórico do projeto é uma sequência de commits. Aqui os textos seguem o padrão "conventional commits" (`docs:`, `feat:`, `fix:`...). |
| **Distro** | "Versão" do Linux. O projeto usa a distro **Ubuntu** dentro do WSL. Instalar uma distro = instalar o Linux em si. |
| **pip** | Instalador de pacotes do Python. `pip install nome-do-pacote` baixa e instala a biblioteca. Dentro de um venv, o pip instala **só naquele** venv. |
| **PR (Pull Request)** | Pedido formal: "revise minha branch e junte na main". O dono revisa, pede ajustes se precisar e aprova. É o portão de entrada de qualquer mudança no projeto. |
| **Prompt** | A mensagem/instrução que você escreve para o agente. Um bom prompt diz o objetivo, as regras e quando parar e perguntar. |
| **push** | Enviar seus commits da sua máquina para o repositório no GitHub. Commit sem push = o trabalho existe só no seu PC (é considerado falha neste projeto). |
| **venv** | "Aquário" isolado do Python: pacotes instalados dentro dele não conflitam com o resto da máquina nem com outros projetos. O deste projeto se chama `printer3d-ia` e vive em `~/.venvs/printer3d-ia` dentro do Ubuntu. |
| **VRAM** | A memória da placa de vídeo (GPU). Modelos de IA rodam "morando" nela; se o modelo precisa de mais VRAM do que existe, dá erro "out of memory" (OOM). A 3060 tem 12 GB; a 5060 Ti tem 8 GB. Como o Windows também usa essa memória, o projeto tem um **guard** que só deixa rodar job pesado quando há VRAM livre suficiente. |
| **WSL** | "Windows Subsystem for Linux": um Linux de verdade rodando dentro do Windows, sem máquina virtual visível nem segunda máquina. O projeto roda tudo pesado (Blender, IA, CUDA) no Linux do WSL, e o Windows fica por cima. Ligar/desligar o WSL = abrir/fechar essa máquina Linux embutida. |
