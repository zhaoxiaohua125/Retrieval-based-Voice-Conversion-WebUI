param([string]$Root = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'SilentlyContinue'
$bundled = Join-Path $Root 'python\python.exe'
if (Test-Path $bundled) { Write-Output $bundled; exit 0 }
$bundled = Join-Path $Root 'python\Scripts\python.exe'
if (Test-Path $bundled) { Write-Output $bundled; exit 0 }
$candidates = @('F:\zxh\anaconda3\envs\rvc312\python.exe')
foreach ($base in @(
    'F:\zxh\anaconda3',
    "$env:USERPROFILE\miniconda3",
    "$env:USERPROFILE\anaconda3",
    'C:\ProgramData\miniconda3',
    'D:\miniconda3',
    'F:\miniconda3',
    'F:\anaconda3'
)) {
    $rvc = Join-Path $base 'envs\rvc312\python.exe'
    if (Test-Path $rvc) { $candidates += $rvc }
}
$seen = @{}
foreach ($py in $candidates) {
    $key = $py.ToLower()
    if ($seen[$key]) { continue }
    $seen[$key] = $true
    if (-not (Test-Path $py)) { continue }
    & $py -c "import torch" 2>$null
    if ($LASTEXITCODE -eq 0) { Write-Output $py; exit 0 }
}
exit 1
