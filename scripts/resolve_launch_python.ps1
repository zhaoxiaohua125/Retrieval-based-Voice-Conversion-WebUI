param([string]$Root = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'SilentlyContinue'
$candidates = @(
    (Join-Path $Root 'python\python.exe'),
    (Join-Path $Root 'python\Scripts\python.exe'),
    'F:\zxh\anaconda3\envs\rvc312\python.exe'
)
foreach ($base in @(
    'F:\zxh\anaconda3',
    "$env:USERPROFILE\miniconda3",
    "$env:USERPROFILE\anaconda3",
    "$env:USERPROFILE\Miniconda3",
    "$env:USERPROFILE\Anaconda3",
    'C:\ProgramData\miniconda3',
    'C:\ProgramData\anaconda3',
    'D:\miniconda3',
    'D:\anaconda3',
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
foreach ($base in @('F:\zxh\anaconda3', "$env:USERPROFILE\anaconda3", "$env:USERPROFILE\miniconda3", 'F:\anaconda3', 'D:\anaconda3')) {
    $envs = Join-Path $base 'envs'
    if (-not (Test-Path $envs)) { continue }
    Get-ChildItem $envs -Directory | ForEach-Object {
        $py = Join-Path $_.FullName 'python.exe'
        $key = $py.ToLower()
        if ($seen[$key]) { return }
        $seen[$key] = $true
        if (-not (Test-Path $py)) { return }
        & $py -c "import torch" 2>$null
        if ($LASTEXITCODE -eq 0) { Write-Output $py; exit 0 }
    }
}
exit 1
