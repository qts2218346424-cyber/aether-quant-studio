Set fso = CreateObject("Scripting.FileSystemObject")
Set ws = CreateObject("WScript.Shell")
launcherDir = fso.GetParentFolderName(WScript.ScriptFullName)
projectRoot = fso.GetParentFolderName(fso.GetParentFolderName(launcherDir))
ws.CurrentDirectory = projectRoot
ws.Run "pythonw ""src\desktop\tray_app.py""", 0, False
