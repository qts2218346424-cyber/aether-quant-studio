$ErrorActionPreference = "Stop"

$launcherDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $launcherDir "..\..")).Path
$pythonwCmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
$pythonw = if ($pythonwCmd) { $pythonwCmd.Source } else { (Get-Command python.exe -ErrorAction Stop).Source }
$supervisor = Join-Path $root "src\desktop\server_supervisor.py"
$taskName = "AetherQuantStudioDashboard"

$action = New-ScheduledTaskAction `
    -Execute $pythonw `
    -Argument "`"$supervisor`"" `
    -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

try {
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description "Keep Aether Quant Studio local dashboard on port 8800 available." `
        -Force | Out-Null
    Start-ScheduledTask -TaskName $taskName
    Write-Host "Installed and started scheduled task: $taskName"
}
catch {
    $startup = [Environment]::GetFolderPath("Startup")
    $launcher = Join-Path $startup "AetherQuantStudioDashboard.vbs"
    $command = 'CreateObject("WScript.Shell").Run """' +
        $pythonw + '"" ""' + $supervisor + '""", 0, False'
    Set-Content -LiteralPath $launcher -Value $command -Encoding Unicode
    Start-Process -FilePath $pythonw -ArgumentList "`"$supervisor`"" -WorkingDirectory $root -WindowStyle Hidden
    Write-Host "Installed and started per-user startup watchdog: $launcher"
}
