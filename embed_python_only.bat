@echo off
cd /d "%~dp0"
echo Embed rvc312 into dist\RVC-Client-0.1.0-demo\python
echo Skip this if full build_demo_package.bat is still running.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\embed_python_only.ps1"
pause
