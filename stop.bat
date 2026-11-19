@echo off
setlocal
cd /d "%~dp0"

echo ======================================================
echo   Aether Quant Studio - Stopping All Services...
echo ======================================================
echo.

python scripts\stop_all.py

echo.
ping 127.0.0.1 -n 2 >nul
exit /b 0
