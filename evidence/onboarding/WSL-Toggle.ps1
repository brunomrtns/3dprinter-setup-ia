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
    Start-Process -FilePath "$env:LOCALAPPDATA\Microsoft\WindowsApps\wt.exe" -ArgumentList '-p', '{5f1b6f9c-4ee3-59ad-88cd-615e159a849c}'
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
