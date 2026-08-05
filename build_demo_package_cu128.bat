@echo off
cd /d "%~dp0"
echo Build cu128 package (RTX 50 and later, env rvc312_cu128)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_client_package.ps1" -CudaVariant cu128 -CondaPack -CondaBase "F:\zxh\anaconda3" %*
if errorlevel 1 (echo BUILD FAILED) else (echo BUILD OK: dist\RVC-Client-0.1.0-demo-cu128)
pause
