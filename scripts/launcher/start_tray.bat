@echo off
chcp 65001 >nul
title Aether Quant Studio · 桌面托盘控制中心
cd /d "%~dp0..\.."

where pythonw >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 pythonw.exe，请检查 Python 环境变量。
    pause
    exit /b 1
)

echo 正在启动 Aether Quant Studio 桌面托盘控制中心...
start "" pythonw "src\desktop\tray_app.py"
echo [就绪] 请查看屏幕右下角系统托盘图标！
timeout /t 2 >nul
exit
