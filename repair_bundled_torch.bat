@echo off
cd /d "%~dp0"
echo Repair bundled torch/torchaudio (fix libtorchaudio.pyd error)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\repair_bundled_torch.ps1" -PackageDir "%~dp0"
if errorlevel 1 (echo REPAIR FAILED) else (echo REPAIR OK)
pause
