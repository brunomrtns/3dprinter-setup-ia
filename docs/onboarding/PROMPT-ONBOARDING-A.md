# PROMPT-ONBOARDING-A — Fase A (base do ambiente, roda hoje)

> **Como usar:** copie TODO o bloco de código abaixo e cole no OpenCode da máquina nova. O agente vai executar e parar nos GATEs onde só o humano pode agir. Nada deste passo depende do repositório do projeto.

---

```text
Você é o agente responsável por preparar ESTA máquina Windows 11 para o projeto
"3dprinter-setup-ia" (sistema local de IA para impressão 3D em resina). Esta é a
FASE A: base do ambiente. O dono do projeto é o Bruno; eu sou o novo contribuidor,
leigo em programação — explique em português simples e direto o que você está
fazendo a cada passo.

DADOS DESTA MÁQUINA:
- Windows 11, SEM WSL instalado ainda, SEM conta GitHub (GitHub só na Fase B).
- GPU: NVIDIA GeForce RTX 5060 Ti 8GB (arquitetura Blackwell, sm_120) — PC gamer.
- Você (OpenCode) já está instalado e funcionando.

REGRAS QUE TE VINCULAM:
1. NUNCA invente output de comando, versão ou número. Se um comando falhar,
   registre o erro real e siga (ou pare no GATE correspondente).
2. GATE: onde só um humano pode agir (senha de administrador, reiniciar o
   Windows, digitar senha, confirmar UAC), PARE e escreva claramente
   "🛑 GATE — peça ao humano para fazer X" e espere eu confirmar antes de seguir.
3. Guarde TODAS as evidências (comandos e outputs reais, com data) em
   C:\Users\<meu-usuário>\Documents\onboarding-faseA\ (crie a pasta).
4. Não instale nada fora do que está no roteiro. Não mexa em configurações do
   Windows além do listado.
5. Ao final, gere um relatório em ARQUIVO ÚNICO de texto na mesma pasta,
   pronto para eu copiar e enviar ao Bruno.

ROTEIRO (nesta ordem):

1) VERIFICAÇÃO INICIAL: versão do Windows (winver/build), se `wsl` existe,
   se `nvidia-smi` funciona no PowerShell. Registre tudo.

2) 🛑 GATE 1 — INSTALAR WSL (exige admin): me peça para abrir o PowerShell
   COMO ADMINISTRADOR (Iniciar → "PowerShell" → botão direito → Executar como
   administrador) e rodar:  wsl --install --distro Ubuntu
   Depois que eu confirmar que terminou, siga.

3) 🛑 GATE 2 — REINICIAR O WINDOWS (o instalador do WSL exige): me peça para
   salvar tudo e reiniciar. Só continue DEPOIS que eu confirmar o reboot.

4) 🛑 GATE 3 — PRIMEIRO BOOT DO UBUNTU: a janela do Ubuntu vai pedir usuário
   e senha Linux. Me oriente (usuário em minúsculas, sem espaços; senha que eu
   não esqueça) e espere eu criar. Você NÃO digita a senha por mim.

5) DENTRO DO UBUNTU (via wsl): atualize e instale o básico:
   sudo apt update && sudo apt install -y python3.11 python3.11-venv git build-essential curl
   (se pedir senha no sudo, é a senha que eu criei no passo 4 — EU digito).
   Confirme depois: python3.11 --version e git --version.

6) DRIVER NVIDIA NO WINDOWS: rode nvidia-smi no PowerShell normal.
   Se funcionar, registre a versão do driver. Se falhar OU o driver for
   anterior ao suporte a Blackwell (RTX 50xx), oriente a atualização pelo app
   NVIDIA (ou baixe o driver mais recente do site da NVIDIA).
   🛑 GATE 4 — a instalação do driver pode pedir confirmação UAC/admin: EU faço.

7) PROVAR CUDA NO WSL: rode nvidia-smi DENTRO do Ubuntu. Deve mostrar a
   RTX 5060 Ti. IMPORTANTE: NUNCA instale driver NVIDIA dentro do Ubuntu/WSL —
   o driver é do Windows; o WSL só usa por mapeamento. Se não aparecer,
   diagnostique (wsl --shutdown e reabrir) e registre o erro real.

8) INSTALAR O "MONITOR WSL" NA MINHA ÁREA DE TRABALHO (programa do projeto que
   mostra se o WSL está ligado — ícone muda de cor). Crie a pasta
   %USERPROFILE%\Scripts e salve dentro dela os 3 arquivos PowerShell abaixo
   (conteúdo EXATO), depois gere os ícones, crie o atalho e registre o watcher
   no startup. Nada disso exige admin.

   --- Arquivo 1: %USERPROFILE%\Scripts\WSL-Toggle.ps1 ---
   Add-Type -AssemblyName System.Windows.Forms
   Add-Type -AssemblyName System.Drawing

   function Get-WslState {
       $p = @(Get-Process -Name vmmem, vmmemWSL -ErrorAction SilentlyContinue)
       if ($p.Count -gt 0) {
           $ram = [math]::Round(($p | Measure-Object WorkingSet64 -Sum).Sum / 1MB)
           [pscustomobject]@{ Running = $true; RamMB = $ram }
       } else {
           [pscustomobject]@{ Running = $false; RamMB = 0 }
       }
   }

   function Update-Status {
       $state = Get-WslState
       if ($state.Running) {
           $lblStatus.Text = "WSL LIGADO ($($state.RamMB) MB RAM)"
           $lblStatus.ForeColor = [System.Drawing.Color]::FromArgb(0, 150, 70)
           $btnOn.Enabled = $false
           $btnOff.Enabled = $true
       } else {
           $lblStatus.Text = "WSL DESLIGADO"
           $lblStatus.ForeColor = [System.Drawing.Color]::Firebrick
           $btnOn.Enabled = $true
           $btnOff.Enabled = $false
       }
   }

   $form = New-Object System.Windows.Forms.Form
   $form.Text = 'WSL Toggle'
   $form.Size = New-Object System.Drawing.Size(330, 200)
   $form.StartPosition = 'CenterScreen'
   $form.FormBorderStyle = 'FixedDialog'
   $form.MaximizeBox = $false
   $form.TopMost = $true

   $lblStatus = New-Object System.Windows.Forms.Label
   $lblStatus.Location = New-Object System.Drawing.Point(15, 20)
   $lblStatus.Size = New-Object System.Drawing.Size(285, 35)
   $lblStatus.Font = New-Object System.Drawing.Font('Segoe UI', 12, [System.Drawing.FontStyle]::Bold)
   $lblStatus.TextAlign = 'MiddleCenter'

   $btnOn = New-Object System.Windows.Forms.Button
   $btnOn.Location = New-Object System.Drawing.Point(20, 75)
   $btnOn.Size = New-Object System.Drawing.Size(135, 50)
   $btnOn.Text = 'Ligar WSL'
   $btnOn.Font = New-Object System.Drawing.Font('Segoe UI', 10)

   $btnOn.Add_Click({
       $btnOn.Enabled = $false
       $lblStatus.Text = 'Iniciando...'
       $form.Refresh()
       Start-Process -FilePath 'wsl.exe' -ArgumentList '-e', 'sleep', 'infinity' -WindowStyle Hidden
       $wt = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps\wt.exe'
       if (Test-Path $wt) { Start-Process -FilePath $wt -ArgumentList '-p', 'Ubuntu' }
       else { Start-Process -FilePath 'wsl.exe' }
       Start-Sleep -Seconds 2
       Update-Status
   })

   $btnOff = New-Object System.Windows.Forms.Button
   $btnOff.Location = New-Object System.Drawing.Point(165, 75)
   $btnOff.Size = New-Object System.Drawing.Size(135, 50)
   $btnOff.Text = 'Desligar WSL'
   $btnOff.Font = New-Object System.Drawing.Font('Segoe UI', 10)

   $btnOff.Add_Click({
       $btnOff.Enabled = $false
       $lblStatus.Text = 'Desligando...'
       $form.Refresh()
       & wsl.exe --shutdown 2>$null
       Start-Sleep -Seconds 1
       Update-Status
   })

   $lblHint = New-Object System.Windows.Forms.Label
   $lblHint.Location = New-Object System.Drawing.Point(15, 135)
   $lblHint.Size = New-Object System.Drawing.Size(285, 25)
   $lblHint.Text = 'Status atualiza automaticamente'
   $lblHint.Font = New-Object System.Drawing.Font('Segoe UI', 8)
   $lblHint.ForeColor = [System.Drawing.Color]::Gray
   $lblHint.TextAlign = 'MiddleCenter'

   $timer = New-Object System.Windows.Forms.Timer
   $timer.Interval = 3000
   $timer.Add_Tick({ Update-Status })
   $timer.Start()

   $form.Controls.AddRange(@($lblStatus, $btnOn, $btnOff, $lblHint))
   Update-Status
   [void]$form.ShowDialog()

   --- Arquivo 2: %USERPROFILE%\Scripts\WSL-IconWatcher.ps1 ---
   $created = $false
   $mutex = New-Object System.Threading.Mutex($true, 'Global\WSLIconWatcher', [ref]$created)
   if (-not $created) { exit }

   $desktop = [Environment]::GetFolderPath('Desktop')
   $lnkPath = Join-Path $desktop 'WSL Toggle.lnk'
   $onIcon  = (Join-Path $PSScriptRoot 'icons\wsl-on.ico') + ',0'
   $offIcon = (Join-Path $PSScriptRoot 'icons\wsl-off.ico') + ',0'
   $shell = New-Object -ComObject WScript.Shell
   $last = $null

   while ($true) {
       $running = [bool](Get-Process -Name vmmem, vmmemWSL -ErrorAction SilentlyContinue)
       if ($running -ne $last) {
           if (Test-Path $lnkPath) {
               $lnk = $shell.CreateShortcut($lnkPath)
               $lnk.IconLocation = $(if ($running) { $onIcon } else { $offIcon })
               $lnk.Save()
           }
           $last = $running
       }
       Start-Sleep -Seconds 2
   }

   --- Arquivo 3: %USERPROFILE%\Scripts\make-icons.ps1 ---
   Add-Type -AssemblyName System.Drawing

   function New-PowerIcon {
       param([string]$Path, [int]$R, [int]$G, [int]$B)
       $sizes = @(256, 48, 32, 16)
       $color = [System.Drawing.Color]::FromArgb(255, $R, $G, $B)
       $frames = @()
       foreach ($s in $sizes) {
           $bmp = New-Object System.Drawing.Bitmap($s, $s)
           $gfx = [System.Drawing.Graphics]::FromImage($bmp)
           $gfx.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
           $gfx.Clear([System.Drawing.Color]::Transparent)
           $stroke = [math]::Max(2.0, $s * 0.09)
           $pen = New-Object System.Drawing.Pen($color, [float]$stroke)
           $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
           $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
           $m = $s * 0.14
           $d = $s - (2 * $m)
           $gfx.DrawArc($pen, [float]$m, [float]$m, [float]$d, [float]$d, 310, 280)
           $cx = $s / 2.0
           $gfx.DrawLine($pen, [float]$cx, [float]$m, [float]$cx, [float]($m + ($s * 0.24)))
           $gfx.Dispose()
           $ms = New-Object System.IO.MemoryStream
           $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
           $bmp.Dispose()
           $frames += , $ms.ToArray()
       }
       $fs = [System.IO.File]::Create($Path)
       $bw = New-Object System.IO.BinaryWriter($fs)
       $bw.Write([uint16]0); $bw.Write([uint16]1); $bw.Write([uint16]$frames.Count)
       $offset = 6 + (16 * $frames.Count)
       for ($i = 0; $i -lt $frames.Count; $i++) {
           $png = $frames[$i]; $sz = $sizes[$i]
           $dim = [byte]$(if ($sz -ge 256) { 0 } else { $sz })
           $bw.Write($dim); $bw.Write($dim); $bw.Write([byte]0); $bw.Write([byte]0)
           $bw.Write([uint16]1); $bw.Write([uint16]32)
           $bw.Write([uint32]$png.Length); $bw.Write([uint32]$offset)
           $offset += $png.Length
       }
       foreach ($png in $frames) { $bw.Write($png) }
       $bw.Close(); $fs.Close()
   }

   New-PowerIcon -Path (Join-Path $PSScriptRoot 'icons\wsl-off.ico') -R 110 -G 110 -B 110
   New-PowerIcon -Path (Join-Path $PSScriptRoot 'icons\wsl-on.ico') -R 0 -G 150 -B 70

   --- Depois dos 3 arquivos ---
   a) powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\Scripts\make-icons.ps1"
   b) Criar o atalho "WSL Toggle" na Área de Trabalho:
      alvo powershell.exe com argumentos -NoProfile -ExecutionPolicy Bypass
      -WindowStyle Hidden -File "<caminho>\WSL-Toggle.ps1",
      diretório de trabalho <caminho>, ícone icons\wsl-off.ico,0,
      descrição "Liga e desliga o WSL".
   c) Registrar no startup do usuário (chave HKCU\Software\Microsoft\Windows\
      CurrentVersion\Run, nome WSLIconWatcher) o comando
      powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden
      -File "<caminho>\WSL-IconWatcher.ps1"
   d) Teste: rode o atalho uma vez e mostre se a janela abre e o status
      está correto. Registre o resultado.

9) AUDITORIA FINAL DA FASE A: cole num único arquivo de relatório os outputs
   reais (com data) de: winver/build do Windows; wsl -l -v; lsb_release -a e
   uname -r dentro do Ubuntu; python3.11 --version e git --version no Ubuntu;
   nvidia-smi no Windows E no Ubuntu (versão do driver, CUDA, VRAM total e
   livre); espaço livre em C: e no disco do WSL (df -h /).

10) RELATÓRIO: gere Documents\onboarding-faseA\RELATORIO-FASE-A.txt com:
   o que foi feito, GATEs que passei por você, resultados-chave, pendências
   reais (com o erro que deu, se deu). Termine avisando: "Fase A concluída —
   enviar o relatório ao Bruno e aguardar o update do projeto na main para
   começar a Fase B".
```
