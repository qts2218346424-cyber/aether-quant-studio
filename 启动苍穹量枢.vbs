' Aether Quant Studio · 苍穹量枢 桌面端无黑框一键启动脚本
' 双击此文件即可静默拉起量化客户端主窗口与系统托盘

Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)

Set ws = CreateObject("WScript.Shell")
ws.CurrentDirectory = currentDir

' 启动命令：优先使用 pythonw 执行 desktop_app.py，彻底消除黑框
command = "powershell -WindowStyle Hidden -NoProfile -Command ""Start-Process -FilePath 'pythonw.exe' -ArgumentList 'desktop_app.py' -WorkingDirectory '" & currentDir & "'"""
ws.Run command, 0, False
