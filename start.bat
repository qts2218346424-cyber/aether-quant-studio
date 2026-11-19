@echo off
setlocal
cd /d "%~dp0"

echo ======================================================
echo   Aether Quant Studio - Launching Desktop App...
echo ======================================================
echo.

powershell -NoProfile -Command "$exe = Get-ChildItem -Filter '*.exe' | Select-Object -First 1; if ($exe) { Start-Process -FilePath $exe.FullName -WorkingDirectory '%~dp0' } else { Start-Process -FilePath 'pythonw.exe' -ArgumentList 'desktop_app.py' -WorkingDirectory '%~dp0' }"

echo Desktop App started! Dashboard URL: http://127.0.0.1:8800
ping 127.0.0.1 -n 2 >nul
exit /b 0
