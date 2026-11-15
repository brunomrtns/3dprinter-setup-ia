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

New-PowerIcon -Path 'C:\Users\Bruno\Scripts\icons\wsl-off.ico' -R 110 -G 110 -B 110
New-PowerIcon -Path 'C:\Users\Bruno\Scripts\icons\wsl-on.ico' -R 0 -G 150 -B 70
