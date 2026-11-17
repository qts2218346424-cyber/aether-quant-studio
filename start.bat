@echo off
chcp 65001 >nul
title Aether Quant Studio · 苍穹量枢
echo ======================================================
echo   ⚡ Aether Quant Studio · 苍穹量枢 正在启动...
echo ======================================================
echo.

cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python 环境，请先安装 Python 3.10+
    pause
    exit /b 1
)

:: 同步拉起右下角桌面系统托盘微控面板（若已安装 PyQt5）
start "" pythonw src\desktop\tray_app.py 2>nul

echo [1/1] 正在启动 FastAPI 核心量化引擎...
echo 面板地址: http://localhost:8800
echo 快捷提示: 在页面内按 Ctrl+K 可呼出极客命令面板！
echo.
python app.py

pause
