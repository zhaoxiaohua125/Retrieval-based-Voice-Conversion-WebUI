@echo off
chcp 65001 >nul
cd /d "%~dp0.."
set "SRC="
if exist "%~dp0..\venv\Scripts\python.exe" set "SRC=%~dp0..\venv\Scripts\python.exe"
if not defined SRC if exist "C:\Python312\python.exe" set "SRC=C:\Python312\python.exe"
if not defined SRC if exist "C:\Python311\python.exe" set "SRC=C:\Python311\python.exe"
if not defined SRC if exist "C:\Python310\python.exe" set "SRC=C:\Python310\python.exe"
if not defined SRC if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "SRC=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined SRC if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "SRC=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined SRC if exist "%ProgramFiles%\Python312\python.exe" set "SRC=%ProgramFiles%\Python312\python.exe"
if not defined SRC if exist "%ProgramFiles%\Python311\python.exe" set "SRC=%ProgramFiles%\Python311\python.exe"
if not defined SRC for /f "delims=" %%i in ('where python 2^>nul') do (set "SRC=%%i" & goto :found)
:found
if not defined SRC (
    echo 未找到 python.exe，请手动复制一份并重命名为「桌面歌词.exe」放到项目根目录。
    echo 例如：copy "C:\Python312\python.exe" "桌面歌词.exe"
    pause
    exit /b 1
)
set "PY=%SRC%"
if exist "%~dp0..\venv\Scripts\python.exe" set "PY=%~dp0..\venv\Scripts\python.exe"
"%PY%" "%~dp0gen_app_icons.py"
if errorlevel 1 (
    echo 生成图标失败。
    pause
    exit /b 1
)
copy /Y "%SRC%" "桌面歌词.exe" >nul
if errorlevel 1 (
    echo 无法覆盖 桌面歌词.exe，请先关闭主程序与桌面歌词进程后再运行本脚本。
    pause
    exit /b 1
)
set "RCEDIT=%~dp0tools\rcedit-x64.exe"
if not exist "%RCEDIT%" (
    echo 正在下载 rcedit 以嵌入 exe 图标...
    if not exist "%~dp0tools" mkdir "%~dp0tools"
    curl -L -o "%RCEDIT%" "https://github.com/electron/rcedit/releases/download/v2.0.0/rcedit-x64.exe"
)
if exist "%RCEDIT%" (
    "%RCEDIT%" "桌面歌词.exe" --set-icon "assets\desktop_lyrics.ico"
    echo 已用 %SRC% 生成 %CD%\桌面歌词.exe（绿色「词」图标）
) else (
    echo 已生成 %CD%\桌面歌词.exe，但未能嵌入 exe 图标（可重启后看任务栏窗口图标）。
)
echo 重启客户端后，直播伴侣窗口采集里应显示「桌面歌词.exe 【直播歌词】桌面歌词」。
pause
