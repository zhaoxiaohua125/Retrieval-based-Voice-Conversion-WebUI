@echo off
cd /d "%~dp0"
echo ========================================
echo  RVC Client Demo Package Builder
echo  CondaBase: F:\zxh\anaconda3
echo  Zip manually after build completes
echo ========================================
echo.
echo  [1] RTX 50 and earlier  (cu118, env rvc312)
echo  [2] RTX 50 and later    (cu128, env rvc312_cu128)
echo.
set /p CHOICE=Select 1 or 2:
if "%CHOICE%"=="1" goto cu118
if "%CHOICE%"=="2" goto cu128
echo Invalid choice
pause
exit /b 1
:cu118
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_client_package.ps1" -CudaVariant cu118 -CondaPack -CondaBase "F:\zxh\anaconda3" %*
if errorlevel 1 (echo BUILD FAILED) else (echo BUILD OK: dist\RVC-Client-0.1.0-demo-cu118)
goto end
:cu128
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_client_package.ps1" -CudaVariant cu128 -CondaPack -CondaBase "F:\zxh\anaconda3" %*
if errorlevel 1 (echo BUILD FAILED) else (echo BUILD OK: dist\RVC-Client-0.1.0-demo-cu128)
:end
pause
