@echo off
cd /d "%~dp0"
echo ========================================
echo  RVC Client Demo Package (with rvc312)
echo  CondaBase: F:\zxh\anaconda3
echo  Estimated time: 10-30 min, size ~10 GB
echo  Zip manually after build completes
echo ========================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_client_package.ps1" -Version "0.1.0-demo" -CondaPack -CondaEnv rvc312 -CondaBase "F:\zxh\anaconda3" %*
if errorlevel 1 (echo BUILD FAILED) else (echo BUILD OK: dist\RVC-Client-0.1.0-demo)
pause
