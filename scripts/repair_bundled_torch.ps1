param(
    [string]$PackageDir = "",
    [string]$CondaBase = "F:\zxh\anaconda3",
    [string]$CondaEnv = "",
    [ValidateSet("cu118", "cu128", "")]
    [string]$CudaVariant = "",
    [switch]$UsePip
)

$ErrorActionPreference = "Stop"
if (-not $PackageDir) { $PackageDir = Split-Path -Parent $PSScriptRoot }
$CondaBase = $CondaBase.TrimEnd('\')
$pyDir = Join-Path $PackageDir "python"
$bundledPy = Join-Path $pyDir "python.exe"
if (-not (Test-Path $bundledPy)) { throw "bundled python not found: $bundledPy" }

$variantFile = Join-Path $PackageDir "GPU_VARIANT.txt"
if (-not $CudaVariant -and (Test-Path $variantFile)) {
    $line = Get-Content $variantFile | Where-Object { $_ -match '^cuda_variant=' } | Select-Object -First 1
    if ($line) { $CudaVariant = ($line -split '=', 2)[1].Trim() }
}
if (-not $CudaVariant) { $CudaVariant = "cu118" }
if (-not $CondaEnv) {
    $CondaEnv = if ($CudaVariant -eq "cu128") { "rvc312_cu128" } else { "rvc312" }
}

function Test-TorchAudio {
    & $bundledPy -c "import torchaudio; from torchaudio.transforms import Resample" 2>$null
    return $LASTEXITCODE -eq 0
}

$EnvPrefix = Join-Path $CondaBase "envs\$CondaEnv"
$srcSite = Join-Path $EnvPrefix "Lib\site-packages"
$dstSite = Join-Path $pyDir "Lib\site-packages"

if (-not $UsePip -and (Test-Path $srcSite)) {
    Write-Host "Sync torch* from $EnvPrefix (no download)..."
    New-Item -ItemType Directory -Force -Path $dstSite | Out-Null
    Get-ChildItem $dstSite | Where-Object { $_.Name -like "torch*" } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    foreach ($item in Get-ChildItem $srcSite | Where-Object { $_.Name -like "torch*" }) {
        Copy-Item $item.FullName (Join-Path $dstSite $item.Name) -Recurse -Force
    }
    if (Test-TorchAudio) {
        Write-Host "Repair complete (local copy)."
        exit 0
    }
    Write-Warning "local copy did not fix torchaudio"
}

if ($UsePip -or -not (Test-TorchAudio)) {
    $wheelDir = Join-Path (Split-Path -Parent $PackageDir) "torch_wheels_$CudaVariant"
    $ver = "2.7.1+$CudaVariant"
    $index = if ($CudaVariant -eq "cu128") { "https://download.pytorch.org/whl/cu128" } else { "https://download.pytorch.org/whl/cu118" }
    if (-not (Test-Path (Join-Path $wheelDir "torch-$ver-*.whl"))) {
        Write-Host "Download wheels once to $wheelDir ..."
        New-Item -ItemType Directory -Force -Path $wheelDir | Out-Null
        & $bundledPy -m pip download "torch==$ver" "torchaudio==$ver" -d $wheelDir --index-url $index --extra-index-url https://pypi.org/simple
        if ($LASTEXITCODE -ne 0) { throw "pip download failed" }
    }
    Write-Host "Install from local wheels (no re-download)..."
    & $bundledPy -m pip install --force-reinstall --no-index --find-links $wheelDir "torch==$ver" "torchaudio==$ver"
    if ($LASTEXITCODE -ne 0) { throw "pip install from wheels failed" }
}
if (-not (Test-TorchAudio)) { throw "torchaudio verify failed" }
Write-Host "Repair complete."
