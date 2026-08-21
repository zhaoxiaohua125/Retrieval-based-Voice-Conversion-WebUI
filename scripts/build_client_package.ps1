param(
    [string]$Version = "",
    [ValidateSet("cu118", "cu128", "")]
    [string]$CudaVariant = "",
    [switch]$Lite,
    [switch]$CondaPack,
    [switch]$Pyd,
    [string]$CondaEnv = "",
    [string]$CondaBase = "F:\zxh\anaconda3"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$VariantMap = @{
    cu118 = @{ Env = "rvc312"; Label = "RTX 50 series and earlier (CUDA 11.8)"; Torch = "2.7.1+cu118" }
    cu128 = @{ Env = "rvc312_cu128"; Label = "RTX 50 series and later (CUDA 12.8)"; Torch = "2.7.1+cu128" }
}

if ($CudaVariant -and -not $VariantMap.ContainsKey($CudaVariant)) {
    Write-Error "Unknown -CudaVariant: $CudaVariant (use cu118 or cu128)"
}
if (-not $CudaVariant -and $CondaEnv -eq "rvc312_cu128") { $CudaVariant = "cu128" }
if (-not $CudaVariant -and $CondaEnv -eq "rvc312") { $CudaVariant = "cu118" }
if (-not $CudaVariant) { $CudaVariant = "cu118" }

$info = $VariantMap[$CudaVariant]
if (-not $CondaEnv) { $CondaEnv = $info.Env }
if (-not $Version) { $Version = "0.1.0-demo-$CudaVariant" }

function Invoke-CondaPack {
    param([string]$PackExe, [string[]]$PackArgs)
    Write-Host ("conda-pack " + ($PackArgs -join ' '))
    & $PackExe @PackArgs
    if ($LASTEXITCODE -ne 0) { throw ("conda-pack failed (exit $LASTEXITCODE)") }
}

function Clear-TreeReadOnly {
    param([string]$Path)
    Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.PSIsContainer) { return }
        try {
            if ($_.Attributes -band [IO.FileAttributes]::ReadOnly) {
                $_.Attributes = $_.Attributes -band (-bnot [IO.FileAttributes]::ReadOnly)
            }
        } catch {}
    }
}

function Invoke-CondaUnpack {
    param([string]$UnpackExe, [string]$PyDir, [int]$Retries = 3)
    Clear-TreeReadOnly $PyDir
    $ortCapi = Join-Path $PyDir "Lib\site-packages\onnxruntime\capi"
    for ($i = 1; $i -le $Retries; $i++) {
        if ($i -gt 1) {
            Write-Host "conda-unpack retry $i/$Retries ..."
            Start-Sleep -Seconds 2
            Clear-TreeReadOnly $PyDir
            if (Test-Path $ortCapi) {
                Get-ChildItem -LiteralPath $ortCapi -Filter *.dll -ErrorAction SilentlyContinue | ForEach-Object {
                    try { $_.IsReadOnly = $false } catch {}
                }
            }
        }
        Write-Host "Running conda-unpack..."
        & $UnpackExe
        if ($LASTEXITCODE -eq 0) { return }
    }
    throw @"
conda-unpack failed (often Permission denied on onnxruntime *.dll).
Close all Python/RVC processes and retry. Add dist folder to antivirus exclusions.
If still failing, run this build script as Administrator.
"@
}

$CondaBase = $CondaBase.TrimEnd('\')
$CondaExe = Join-Path $CondaBase "Scripts\conda.exe"
$PackExe = Join-Path $CondaBase "python.exe"
$PackScript = Join-Path $CondaBase "Scripts\conda-pack-script.py"
if (-not (Test-Path $CondaExe)) { Write-Error "conda not found: $CondaBase" }

$EnvPrefix = Join-Path $CondaBase "envs\$CondaEnv"
$EnvPython = Join-Path $EnvPrefix "python.exe"
if (-not (Test-Path $EnvPython)) {
    Write-Host ""
    Write-Host "ERROR: env not found: $EnvPrefix"
    if ($CudaVariant -eq "cu128") {
        Write-Host "Create it first: scripts\setup_conda_cu128.ps1"
        Write-Host "Or see packaging/INSTALL_RUNTIME.md"
    }
    exit 1
}

Write-Host "Variant: $CudaVariant ($($info.Label))"
Write-Host "Conda env: $CondaEnv"
Write-Host "Version: $Version"
Write-Host "Output: dist\RVC-Client-$Version"

$pyArgs = @("scripts/build_client_package.py", "--version", $Version, "--output", "dist", "--cuda-variant", $CudaVariant)
if ($Lite) { $pyArgs += "--lite" }
if ($Pyd) { $pyArgs += "--pyd" }

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
    $packTar = Join-Path $Root "dist\python-env-$CudaVariant.tar.gz"
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
    Invoke-CondaUnpack $unpack $pyDir
    $bundledPy = Join-Path $pyDir "python.exe"
    if (-not (Test-Path $bundledPy)) { throw "python.exe not found: $bundledPy" }
    Write-Host "Repair torch/torchaudio..."
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\repair_bundled_torch.ps1") `
        -PackageDir $OutDir -CudaVariant $CudaVariant -CondaBase $CondaBase -CondaEnv $CondaEnv
    if ($LASTEXITCODE -ne 0) { throw "torch/torchaudio repair failed" }
    Write-Host "Verify package..."
    & $bundledPy (Join-Path $Root "scripts\verify_client_package.py") $OutDir
    if ($LASTEXITCODE -ne 0) { throw "package verify failed" }
    Write-Host "Ship desktop lyrics exe..."
    & $EnvPython (Join-Path $Root "scripts\build_client_package.py") --ship-desktop-lyrics $OutDir
    if ($LASTEXITCODE -ne 0) { throw "desktop lyrics exe ship failed" }
    & $EnvPython (Join-Path $Root "scripts\build_client_package.py") --verify-desktop-lyrics $OutDir
    if ($LASTEXITCODE -ne 0) { throw "desktop lyrics verify failed (python/DesktopLyrics.exe)" }
    Write-Host "Desktop lyrics OK (python/DesktopLyrics.exe)"
    Write-Host "Python runtime OK: $bundledPy"
    $variantFile = Join-Path $OutDir "GPU_VARIANT.txt"
    @(
        "cuda_variant=$CudaVariant",
        "conda_env=$CondaEnv",
        "target_gpu=$($info.Label)",
        "expected_torch=$($info.Torch)"
    ) | Set-Content -Path $variantFile -Encoding UTF8
}

Write-Host ""
Write-Host "Package ready: $OutDir"
if (Test-Path (Join-Path $OutDir "python\python.exe")) {
    Write-Host "Bundled python/ included. Zip the folder manually before shipping."
} else {
    Write-Host "WARNING: no python/ folder. Rebuild with -CondaPack."
}
Write-Host "GPU variant: $CudaVariant - $($info.Label)"
