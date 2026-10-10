param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000
)

$ErrorActionPreference = "Stop"
$nexyraRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$nexyraFrontend = Join-Path $nexyraRoot "frontend"
$nexyraLogDir = Join-Path $nexyraRoot "logs\dev"
$nexyraPython = Join-Path $nexyraRoot "venv\Scripts\python.exe"
$nexyraNode = (Get-Command node.exe -ErrorAction Stop).Source
$nexyraNextCli = Join-Path $nexyraFrontend "node_modules\next\dist\bin\next"

foreach ($port in @($BackendPort, $FrontendPort)) {
    $ownerIds = @()
    foreach ($line in (& netstat.exe -ano -p tcp)) {
        if ($line -match "^\s*TCP\s+\S+:$port\s+\S+\s+LISTENING\s+(\d+)\s*$") {
            $ownerIds += [int]$Matches[1]
        }
    }
    $ownerIds = @($ownerIds | Sort-Object -Unique)
    if ($ownerIds.Count -gt 0) {
        $details = $ownerIds | ForEach-Object {
            $process = Get-Process -Id $_ -ErrorAction SilentlyContinue
            "port $port is held by PID $_ ($($process.ProcessName))"
        }
        throw "Nexyra startup stopped because $($details -join '; '). Inspect the named process and close only the intended Nexyra server, then retry. This script never terminates a process it did not start."
    }
}

if (!(Test-Path -LiteralPath $nexyraPython) -or !(Test-Path -LiteralPath $nexyraNextCli)) {
    throw "Nexyra dependencies are missing. Create the project venv and install backend/frontend dependencies first."
}

New-Item -ItemType Directory -Force -Path $nexyraLogDir | Out-Null
$backendProcess = $null
$frontendProcess = $null
$priorBackendUrl = [Environment]::GetEnvironmentVariable("NEXYRA_BACKEND_URL", "Process")
try {
    $backendStdout = Join-Path $nexyraLogDir "backend.stdout.log"
    $backendStderr = Join-Path $nexyraLogDir "backend.stderr.log"
    $frontendStdout = Join-Path $nexyraLogDir "frontend.stdout.log"
    $frontendStderr = Join-Path $nexyraLogDir "frontend.stderr.log"

    $backendProcess = Start-Process -FilePath $nexyraPython -ArgumentList @(
        "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort"
    ) -WorkingDirectory $nexyraRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $backendStdout -RedirectStandardError $backendStderr

    [Environment]::SetEnvironmentVariable("NEXYRA_BACKEND_URL", "http://127.0.0.1:$BackendPort", "Process")
    $frontendProcess = Start-Process -FilePath $nexyraNode -ArgumentList @(
        $nexyraNextCli, "dev", "--hostname", "127.0.0.1", "--port", "$FrontendPort"
    ) -WorkingDirectory $nexyraFrontend -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $frontendStdout -RedirectStandardError $frontendStderr

    Write-Host "Nexyra development services starting. Press Ctrl+C here to stop only these two process trees."
    Write-Host "API:      http://127.0.0.1:$BackendPort/api/health"
    Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
    Write-Host "Logs:     $nexyraLogDir"

    $ready = $false
    $deadline = (Get-Date).AddSeconds(40)
    while ((Get-Date) -lt $deadline -and -not $ready) {
        if ($backendProcess.HasExited -or $frontendProcess.HasExited) {
            throw "A Nexyra process exited during startup. Check the log files above."
        }
        try {
            $apiHealth = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/api/health" -TimeoutSec 2
            $frontResponse = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort" -TimeoutSec 2 -UseBasicParsing
            $ready = $apiHealth.status -eq "ok" -and $apiHealth.database -eq "reachable" -and $frontResponse.StatusCode -eq 200
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $ready) { throw "Nexyra did not pass API and frontend health checks within 40 seconds. Check the log files above." }
    Write-Host "API database: $($apiHealth.database) · Frontend HTTP $($frontResponse.StatusCode)"

    while ($true) {
        if ($backendProcess.HasExited -or $frontendProcess.HasExited) {
            throw "A Nexyra service stopped. Check the log files above."
        }
        Start-Sleep -Seconds 1
    }
}
finally {
    [Environment]::SetEnvironmentVariable("NEXYRA_BACKEND_URL", $priorBackendUrl, "Process")
    foreach ($ownedProcess in @($frontendProcess, $backendProcess)) {
        if ($null -ne $ownedProcess -and -not $ownedProcess.HasExited) {
            & taskkill.exe /PID $ownedProcess.Id /T /F | Out-Null
        }
    }
}
