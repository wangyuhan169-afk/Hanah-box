@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto ready
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)"
if errorlevel 1 goto missing
py -3 -m venv .venv
if errorlevel 1 goto fail
:ready
.venv\Scripts\python.exe -c "import lxml, openpyxl, pypdf, xlrd" >nul 2>&1
if not errorlevel 1 goto launch
echo 首次运行，正在安装公告解析组件……
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
:launch
.venv\Scripts\python.exe scripts\launch.py
pause
exit /b
:missing
echo 请先从 python.org 安装 Python 3.12 或更新版本，安装时启用 Python Launcher。
pause
exit /b 1
:fail
echo 安装或启动失败，请保留上方错误信息。
pause
exit /b 1
