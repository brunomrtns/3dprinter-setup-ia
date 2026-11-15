# Monitor WSL da Área de Trabalho ("WSL Toggle")

> Material de onboarding: programa pequeno que mostra na Área de Trabalho se o **WSL está ligado ou desligado** (o ícone muda de cor) e permite ligar/desligar com um clique. Documentação gerada por engenharia reversa no PC de referência (2026-11-14) — evidências em `evidence/onboarding/`.

## 1. O que é

Um conjunto de **3 scripts PowerShell + 2 ícones + 1 atalho + 1 chave de inicialização**. Nada é instalado; é tudo arquivo solto que o Windows executa.

| Peça | Papel |
|---|---|
| `WSL-Toggle.ps1` | Janela com botões **Ligar WSL / Desligar WSL** e rótulo de status que se atualiza sozinho a cada 3 s (verde "WSL LIGADO (N MB RAM)" / vermelho "WSL DESLIGADO") |
| `WSL-IconWatcher.ps1` | Processo invisível que roda em segundo plano e **troca o ícone do atalho** na Área de Trabalho (`wsl-on.ico` verde ↔ `wsl-off.ico` cinza) conforme o estado do WSL, verificando a cada 2 s |
| `make-icons.ps1` | Gera os dois arquivos `.ico` (símbolo de "power", cinza = desligado, verde = ligado; tamanhos 256/48/32/16 dentro de um único ICO) |
| `WSL Toggle.lnk` | Atalho da Área de Trabalho; abre a janela do Toggle. O **ícone do atalho** é o indicador visual |
| Chave de registro `HKCU\...\Run\WSLIconWatcher` | Faz o IconWatcher iniciar escondido a cada login |

## 2. Como detecta o estado do WSL (por dentro)

A detecção **não usa `wsl --status`** — usa a existência do processo da máquina virtual do WSL2:

```powershell
Get-Process -Name vmmem, vmmemWSL -ErrorAction SilentlyContinue
```

- `vmmemWSL` (ou `vmmem` em versões antigas) é o processo que hospeda a VM do WSL2. **Só existe enquanto a VM está rodando** → existe = LIGADO; não existe = DESLIGADO;
- A soma do `WorkingSet64` desses processos dá a RAM em uso pela VM (mostrada no rótulo da janela);
- Limitação conhecida (medida nesta auditoria): o processo pode **linger alguns segundos** após `wsl --shutdown`, e há um intervalo entre ligar e o processo aparecer — o status pode ficar velho por alguns segundos em ambas as direções.

Ações dos botões:

- **Ligar:** `Start-Process wsl.exe -ArgumentList '-e','sleep','infinity' -WindowStyle Hidden` (mantém a VM acordada com um processo dormindo dentro dela) + abre um terminal no perfil Ubuntu do Windows Terminal;
- **Desligar:** `wsl.exe --shutdown` (derruba a VM; qualquer sessão aberta morre).

## 3. Onde está NESTE PC (referência)

| Item | Caminho |
|---|---|
| Scripts e ícones | `C:\Users\Bruno\Scripts\` (`WSL-Toggle.ps1`, `WSL-IconWatcher.ps1`, `make-icons.ps1`, `icons\wsl-on.ico`, `icons\wsl-off.ico`) |
| Atalho | `C:\Users\Bruno\OneDrive\Área de Trabalho\WSL Toggle.lnk` → alvo `powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\Users\Bruno\Scripts\WSL-Toggle.ps1"` |
| Ícone do atalho | `C:\Users\Bruno\Scripts\icons\wsl-off.ico,0` (alternado pelo watcher para `wsl-on.ico,0`) |
| Inicialização | Valor `WSLIconWatcher` em `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` |
| Cópia dos fontes no repo | `evidence/onboarding/` (mesmos arquivos + SHA256 em `descoberta-monitor-wsl.txt`) |

Estado observado na coleta (2026-11-14): chave de Run registrada, **watcher não estava rodando** (pode ter morrido após um reboot — a chave garante só o próximo login) e WSL `Stopped`. É inofensivo: o atalho continua abrindo a janela, que mostra o estado correto; só o ícone fica parado na última cor.

## 4. Por que NÃO é copiável direto para outra máquina

O conjunto é **amarrado a este PC** por três detalhes:

1. **Caminhos absolutos com "Bruno"** dentro do `WSL-IconWatcher.ps1` (`C:\Users\Bruno\Scripts\icons\...`) e do `make-icons.ps1`;
2. **GUID do perfil do Windows Terminal hardcoded** no botão Ligar (`wt.exe -p '{5f1b6f9c-…}'` — esse GUID é do Ubuntu **desta** instalação; cada máquina tem um GUID diferente);
3. Os `.ico` foram gerados aqui — na outra máquina é mais simples **regenerá-los** com o `make-icons.ps1`.

Portanto: na máquina do colega, **não copie os arquivos; instale a versão portátil abaixo**.

## 5. Versão portátil pronta (máquina do colega)

Mesmo comportamento, sem nada hardcoded: caminhos relativos ao próprio script (`$PSScriptRoot`) e perfil do terminal resolvido na hora. Criar a pasta `%USERPROFILE%\Scripts` e salvar os 3 arquivos abaixo dentro dela.

### 5.1 `WSL-Toggle.ps1`

```powershell
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
    if (Test-Path $wt) {
        Start-Process -FilePath $wt -ArgumentList '-p', 'Ubuntu'
    } else {
        Start-Process -FilePath 'wsl.exe'
    }
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
```

### 5.2 `WSL-IconWatcher.ps1`

```powershell
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
```

### 5.3 `make-icons.ps1`

```powershell
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
    $bw.Write([uint16]0)
    $bw.Write([uint16]1)
    $bw.Write([uint16]$frames.Count)
    $offset = 6 + (16 * $frames.Count)
    for ($i = 0; $i -lt $frames.Count; $i++) {
        $png = $frames[$i]
        $sz = $sizes[$i]
        $dim = [byte]$(if ($sz -ge 256) { 0 } else { $sz })
        $bw.Write($dim)
        $bw.Write($dim)
        $bw.Write([byte]0)
        $bw.Write([byte]0)
        $bw.Write([uint16]1)
        $bw.Write([uint16]32)
        $bw.Write([uint32]$png.Length)
        $bw.Write([uint32]$offset)
        $offset += $png.Length
    }
    foreach ($png in $frames) { $bw.Write($png) }
    $bw.Close()
    $fs.Close()
}

New-PowerIcon -Path (Join-Path $PSScriptRoot 'icons\wsl-off.ico') -R 110 -G 110 -B 110
New-PowerIcon -Path (Join-Path $PSScriptRoot 'icons\wsl-on.ico') -R 0 -G 150 -B 70
```

### 5.4 Instalação automática (`install-wsl-toggle.ps1`) — recomendo usar o agente OpenCode

Não é preciso fazer na mão: o prompt da **Fase A** (`docs/onboarding/PROMPT-ONBOARDING-A.md`) já manda o agente do colega criar a pasta, os arquivos e o atalho. O roteiro manual, para referência:

```powershell
# Rodar no PowerShell normal (sem admin)
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\Scripts\icons" | Out-Null
# (salvar os 3 scripts acima em $env:USERPROFILE\Scripts e rodar:)
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\Scripts\make-icons.ps1"

# Atalho na Área de Trabalho
$sh = New-Object -ComObject WScript.Shell
$lnk = $sh.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'WSL Toggle.lnk'))
$lnk.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$lnk.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}\WSL-Toggle.ps1"' -f "$env:USERPROFILE\Scripts"
$lnk.WorkingDirectory = "$env:USERPROFILE\Scripts"
$lnk.IconLocation = "$env:USERPROFILE\Scripts\icons\wsl-off.ico,0"
$lnk.Description = 'Liga e desliga o WSL'
$lnk.Save()

# Iniciar o IconWatcher junto com o Windows
$val = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}\WSL-IconWatcher.ps1"' -f "$env:USERPROFILE\Scripts"
New-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'WSLIconWatcher' -Value $val -PropertyType String -Force | Out-Null
```

Observações de segurança: tudo fica em `%USERPROFILE%` (não exige admin); a chave de Run só afeta o usuário atual; nada é apagado. Para desinstalar: apagar a pasta `%USERPROFILE%\Scripts`, o atalho e o valor `WSLIconWatcher` da chave de Run.
