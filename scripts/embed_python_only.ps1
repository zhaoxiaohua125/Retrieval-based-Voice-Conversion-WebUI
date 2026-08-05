param(
    [string]$Version = "0.1.0-demo",
    [string]$CondaEnv = "rvc312",
    [string]$CondaBase = "F:\zxh\anaconda3"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$CondaBase = $CondaBase.TrimEnd('\')
$OutDir = Join-Path $Root "dist/RVC-Client-$Version"
$EnvPrefix = Join-Path $CondaBase "envs\$CondaEnv"
$PackExe = Join-Path $CondaBase "python.exe"
$PackScript = Join-Path $CondaBase "Scripts\conda-pack-script.py"
$CondaExe = Join-Path $CondaBase "Scripts\conda.exe"
$pyDir = Join-Path $OutDir "python"
$packTar = Join-Path $Root "dist\python-env.tar.gz"

if (-not (Test-Path $OutDir)) { throw "package dir not found: $OutDir" }
if (-not (Test-Path (Join-Path $EnvPrefix "python.exe"))) { throw "env not found: $EnvPrefix" }

Write-Host "=== embed python only ==="
& $CondaExe pack --help 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    & $CondaExe install -y -c conda-forge conda-pack
    if ($LASTEXITCODE -ne 0) { throw "conda-pack install failed" }
}
if (Test-Path $packTar) { Remove-Item $packTar -Force }
Write-Host "conda-pack (~10 min)..."
& $PackExe $PackScript --prefix $EnvPrefix -o $packTar --ignore-missing-files --force
if ($LASTEXITCODE -ne 0) { throw "conda-pack failed" }
if (Test-Path $pyDir) { Remove-Item $pyDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $pyDir | Out-Null
Write-Host "Extracting..."
tar -xf $packTar -C $pyDir
Remove-Item $packTar -Force -ErrorAction SilentlyContinue
$unpack = Join-Path $pyDir "Scripts\conda-unpack.exe"
if (-not (Test-Path $unpack)) { $unpack = Join-Path $pyDir "conda-unpack.exe" }
& $unpack
& (Join-Path $pyDir "python.exe") -c 'import torch; print(torch.__version__)'
Write-Host "DONE: $pyDir"
