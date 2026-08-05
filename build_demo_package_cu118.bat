@echo off
cd /d "%~dp0"
echo Build cu118 package (RTX 50 and earlier, env rvc312)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_client_package.ps1" -CudaVariant cu118 -CondaPack -CondaBase "F:\zxh\anaconda3" %*
if errorlevel 1 (echo BUILD FAILED) else (echo BUILD OK: dist\RVC-Client-0.1.0-demo-cu118)
pause
