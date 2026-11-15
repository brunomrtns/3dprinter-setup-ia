$created = $false
$mutex = New-Object System.Threading.Mutex($true, 'Global\WSLIconWatcher', [ref]$created)
if (-not $created) { exit }

$desktop = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desktop 'WSL Toggle.lnk'
$onIcon = "C:\Users\Bruno\Scripts\icons\wsl-on.ico,0"
$offIcon = "C:\Users\Bruno\Scripts\icons\wsl-off.ico,0"
$shell = New-Object -ComObject WScript.Shell
$last = $null

while ($true) {
    $running = [bool](Get-Process -Name vmmem, vmmemWSL -ErrorAction SilentlyContinue)
    if ($running -ne $last) {
        $lnk = $shell.CreateShortcut($lnkPath)
        $lnk.IconLocation = $(if ($running) { $onIcon } else { $offIcon })
        $lnk.Save()
        $last = $running
    }
    Start-Sleep -Seconds 2
}
