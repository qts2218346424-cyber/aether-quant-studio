param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$launcherDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $launcherDir "..\..")).Path
$supervisor = Join-Path $root "src\desktop\server_supervisor.py"
$dashboard = "http://127.0.0.1:8800/"

function Test-Dashboard {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $dashboard -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

if (-not (Test-Dashboard)) {
    $runningSupervisor = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match '^python(w)?\.exe$' -and
        $_.CommandLine -like "*server_supervisor.py*"
    }

    if (-not $runningSupervisor) {
        $python = Get-Command pythonw.exe -ErrorAction SilentlyContinue
        if (-not $python) {
            $python = Get-Command python.exe -ErrorAction Stop
        }
        Start-Process `
            -FilePath $python.Source `
            -ArgumentList "`"$supervisor`"" `
            -WorkingDirectory $root `
            -WindowStyle Hidden
    }

    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 500
        if (Test-Dashboard) {
            $ready = $true
            break
        }
    }
    if (-not $ready) {
        throw "Dashboard did not start within 20 seconds."
    }
}

if (-not $NoBrowser) {
    Start-Process $dashboard
}

Write-Output "READY $dashboard"
