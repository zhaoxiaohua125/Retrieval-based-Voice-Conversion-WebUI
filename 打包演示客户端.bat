@echo off
cd /d "%~dp0"
echo [RVC] Full package build: assets + conda + zip
echo This may take 2-5 minutes. Do not close this window.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_client_package.ps1" -Version "0.1.0-demo" -Zip -CondaPack -CondaEnv rvc312
if errorlevel 1 (
    echo [FAILED] See errors above.
) else (
    echo [OK] Output: dist\RVC-Client-0.1.0-demo.zip
)
pause
