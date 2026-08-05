@echo off
cd /d "%~dp0"
echo Create conda env rvc312_cu128 for RTX 50+ (one-time setup)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_conda_cu128.ps1"
pause
