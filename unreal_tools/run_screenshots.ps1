# Opens the Unreal editor, renders BattleTest views to Saved\Screenshots\SL via screenshots.py, closes, and reports
# each image's mean brightness (0 = black, 255 = white) so a dark/blank capture is caught automatically.
param([double]$Exposure = 0)
$UE = 'C:\Program Files\Epic Games\UE_5.8'; $Proj = Join-Path (Split-Path $PSScriptRoot -Parent) 'Unreal\ShatteredLands'
$log = "$Proj\Saved\Logs\screenshots.log"; $env:SL_AUTOSHOT = '1'; $env:SL_EXPOSURE = "$Exposure"
Get-Process UnrealEditor -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$start = Get-Date
$p = Start-Process "$UE\Engine\Binaries\Win64\UnrealEditor.exe" -ArgumentList "`"$Proj\ShatteredLands.uproject`"", "-nosplash", "-ABSLOG=`"$log`"" -PassThru
if (-not $p.WaitForExit(2700000)) { "TIMEOUT"; $p | Stop-Process -Force }
$env:SL_AUTOSHOT = ''
Select-String -Path $log -Pattern 'SL_|LogPython: Error' | Select-Object -Last 12 | ForEach-Object { $_.Line.Substring([Math]::Min(30, $_.Line.Length)) }
Add-Type -AssemblyName System.Drawing
foreach ($f in Get-ChildItem "$Proj\Saved\Screenshots" -Recurse -Filter SL_*.png | Where-Object { $_.LastWriteTime -gt $start }) {
    $b = [System.Drawing.Bitmap]::FromFile($f.FullName); $s = 0; $n = 0
    for ($x = 0; $x -lt $b.Width; $x += 40) { for ($y = 0; $y -lt $b.Height; $y += 40) { $c = $b.GetPixel($x, $y); $s += ($c.R + $c.G + $c.B) / 3; $n++ } }
    $b.Dispose(); "{0,-40} mean {1:N0}" -f $f.FullName.Replace($Proj,""), ($s / $n)
}
