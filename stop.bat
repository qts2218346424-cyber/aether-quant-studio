@echo off
chcp 65001 >nul
title 停止 Aether Quant Studio

echo ======================================================
echo   正在安全停止 Aether Quant Studio 后台进程...
echo ======================================================

powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*server_supervisor.py*' -or $_.CommandLine -like '*tray_app.py*' -or ($_.CommandLine -like '*app.py*' -and $_.Name -match 'python') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo.
echo [OK] 核心交易引擎、系统托盘及守护进程已全部安全停止！
echo.
pause
