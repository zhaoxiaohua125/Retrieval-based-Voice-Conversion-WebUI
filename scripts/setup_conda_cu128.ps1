param(
    [string]$CondaBase = "F:\zxh\anaconda3",
    [string]$EnvName = "rvc312_cu128"
)

$ErrorActionPreference = "Stop"
$CondaBase = $CondaBase.TrimEnd('\')
$CondaExe = Join-Path $CondaBase "Scripts\conda.exe"
$Root = Split-Path -Parent $PSScriptRoot
$ReqCu128 = Join-Path $Root "requirments_cu128_py312.txt"
$ReqUi = Join-Path $Root "requirments_client_ui.txt"

if (-not (Test-Path $CondaExe)) { Write-Error "conda not found: $CondaBase" }
if (-not (Test-Path $ReqCu128)) { Write-Error "missing $ReqCu128" }

Write-Host "=== Create $EnvName for RTX 50+ (cu128) ==="
& $CondaExe create -n $EnvName python=3.12 -y
if ($LASTEXITCODE -ne 0) { throw "conda create failed" }

$py = Join-Path $CondaBase "envs\$EnvName\python.exe"
Write-Host "Install torch cu128..."
& $py -m pip install torch==2.7.1+cu128 torchaudio==2.7.1+cu128 `
    --index-url https://download.pytorch.org/whl/cu128 `
    --extra-index-url https://pypi.org/simple
if ($LASTEXITCODE -ne 0) { throw "torch cu128 install failed" }

Write-Host "Install project deps..."
& $py -m pip install -r $ReqCu128
if ($LASTEXITCODE -ne 0) { throw "requirments_cu128_py312 install failed" }
if (Test-Path $ReqUi) {
    & $py -m pip install -r $ReqUi
    if ($LASTEXITCODE -ne 0) { throw "requirments_client_ui install failed" }
}

& $py -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
Write-Host "DONE: $EnvName ready. Run build_demo_package_cu128.bat to pack."
