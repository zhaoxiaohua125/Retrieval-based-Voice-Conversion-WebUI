@echo off
cd /d "%~dp0"
set "PKG=%~dp0"
if exist "%~dp0dist\RVC-Client-0.1.0-demo-cu118\python\python.exe" set "PKG=%~dp0dist\RVC-Client-0.1.0-demo-cu118"
if exist "%~dp0dist\RVC-Client-0.1.0-demo\python\python.exe" set "PKG=%~dp0dist\RVC-Client-0.1.0-demo"
echo Verify package: %PKG%
"%PKG%python\python.exe" "%PKG%scripts\verify_client_package.py" "%PKG%"
if errorlevel 1 (echo VERIFY FAILED) else (echo VERIFY OK)
pause
