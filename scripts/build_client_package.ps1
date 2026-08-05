param(
    [string]$Version = "0.1.0-demo",
    [switch]$Lite,
    [switch]$CondaPack,
    [string]$CondaEnv = "rvc312",
    [string]$CondaBase = "F:\zxh\anaconda3"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Invoke-CondaPack {
    param([string]$PackExe, [string[]]$PackArgs)
    Write-Host ("conda-pack " + ($PackArgs -join ' '))
    & $PackExe @PackArgs
    if ($LASTEXITCODE -ne 0) { throw ("conda-pack failed (exit $LASTEXITCODE)") }
}

$CondaBase = $CondaBase.TrimEnd('\')
$CondaExe = Join-Path $CondaBase "Scripts\conda.exe"
$PackExe = Join-Path $CondaBase "python.exe"
$PackScript = Join-Path $CondaBase "Scripts\conda-pack-script.py"
if (-not (Test-Path $CondaExe)) { Write-Error "conda not found: $CondaExe" }

$EnvPrefix = Join-Path $CondaBase "envs\$CondaEnv"
$EnvPython = Join-Path $EnvPrefix "python.exe"
if (-not (Test-Path $EnvPython)) { Write-Error "env not found: $EnvPython" }

Write-Host "Conda: $CondaExe"
Write-Host "Pack env: $EnvPrefix"

$pyArgs = @("scripts/build_client_package.py", "--version", $Version, "--output", "dist")
if ($Lite) { $pyArgs += "--lite" }

& $EnvPython @pyArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$OutDir = Join-Path $Root "dist/RVC-Client-$Version"
if ($CondaPack) {
    Write-Host ""
    Write-Host "=== conda-pack $CondaEnv -> $OutDir\python (~10 min, ~6 GB) ==="
    & $CondaExe pack --help 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing conda-pack (first time only)..."
        & $CondaExe install -y -c conda-forge conda-pack
        if ($LASTEXITCODE -ne 0) { throw "conda-pack install failed" }
    } else {
        Write-Host "conda-pack ready, skip install"
    }
    $packTar = Join-Path $Root "dist\python-env.tar.gz"
    if (Test-Path $packTar) { Remove-Item $packTar -Force }
    Invoke-CondaPack $PackExe @($PackScript, "--prefix", $EnvPrefix, "-o", $packTar, "--ignore-missing-files", "--force")
    if (-not (Test-Path $packTar)) { throw "conda pack did not create $packTar" }
    $tarSize = (Get-Item $packTar).Length
    if ($tarSize -lt 100MB) { throw "pack output too small ($tarSize bytes)" }
    Write-Host ("Archive OK: " + [math]::Round($tarSize / 1GB, 2) + " GB")
    $pyDir = Join-Path $OutDir "python"
    if (Test-Path $pyDir) { Remove-Item $pyDir -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $pyDir | Out-Null
    Write-Host "Extracting..."
    tar -xf $packTar -C $pyDir
    if ($LASTEXITCODE -ne 0) { throw "tar extract failed" }
    Remove-Item $packTar -Force -ErrorAction SilentlyContinue
    $unpack = Join-Path $pyDir "Scripts\conda-unpack.exe"
    if (-not (Test-Path $unpack)) { $unpack = Join-Path $pyDir "conda-unpack.exe" }
    if (-not (Test-Path $unpack)) { throw "conda-unpack not found in $pyDir" }
    Write-Host "Running conda-unpack..."
    & $unpack
    if ($LASTEXITCODE -ne 0) { throw "conda-unpack failed" }
    $bundledPy = Join-Path $pyDir "python.exe"
    if (-not (Test-Path $bundledPy)) { throw "python.exe not found: $bundledPy" }
    & $bundledPy -c "import torch; print(torch.__version__)"
    if ($LASTEXITCODE -ne 0) { throw "bundled python missing torch" }
    Write-Host "Python runtime OK: $bundledPy"
}

Write-Host ""
Write-Host "Package ready: $OutDir"
if (Test-Path (Join-Path $OutDir "python\python.exe")) {
    Write-Host "Bundled python/ included. Zip the folder manually before shipping."
} else {
    Write-Host "WARNING: no python/ folder. Rebuild with -CondaPack."
}
Write-Host "Readme: $OutDir\DEMO_README.md"
