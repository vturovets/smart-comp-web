param(
    [switch] $Verbose = $false,
    [switch] $RemoveRedisContainer = $false
)

Set-StrictMode -Version Latest

if ($Verbose) {
    $VerbosePreference = 'Continue'
} else {
    $VerbosePreference = 'SilentlyContinue'
}

# Shutdown helper for Smart Comp Web on Windows PowerShell.
# It closes the spawned service windows, stops the Redis Docker container,
# and frees common dev ports used by the app.

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$serviceTitles = @(
    "SmartComp - Celery Worker",
    "SmartComp - API",
    "SmartComp - Frontend"
)

$servicePorts = @(5173, 8000)
$redisContainerName = "smartcomp-redis"

function Stop-WindowedServices {
    param([string[]] $Titles)

    foreach ($title in $Titles) {
        $procs = Get-Process | Where-Object { $_.MainWindowTitle -eq $title -or $_.MainWindowTitle -like "$title*" }
        if ($procs) {
            foreach ($proc in $procs) {
                Write-Verbose "Stopping process '$($proc.ProcessName)' (PID $($proc.Id)) with title '$title'."
                Stop-Process -Id $proc.Id -Force
            }
        }
        else {
            Write-Verbose "No windowed process found for '$title'."
        }
    }
}

function Close-Ports {
    param([int[]] $Ports)

    foreach ($port in $Ports) {
        $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if ($connections) {
            $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
            foreach ($pid in $pids) {
                try {
                    $proc = Get-Process -Id $pid -ErrorAction Stop
                    Write-Verbose "Terminating process '$($proc.ProcessName)' (PID $pid) using port $port."
                    Stop-Process -Id $pid -Force
                }
                catch {
                    Write-Warning ("Unable to stop process PID {0} on port {1}: {2}" -f $pid, $port, $_)
                }
            }
        }
        else {
            Write-Verbose "No active listeners detected on port $port."
        }
    }
}

function Stop-RedisContainer {
    param(
        [Parameter(Mandatory)][string] $Name,
        [switch] $Remove
    )

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Verbose "Docker not available; skipping Redis container shutdown."
        return
    }

    $running = docker ps --filter "name=^${Name}$" --format "{{.ID}}"
    if ($running) {
        Write-Verbose "Stopping Redis container '$Name'..."
        docker stop $Name | Out-Null
    }
    else {
        Write-Verbose "Redis container '$Name' is not running."
    }

    if ($Remove) {
        $existing = docker ps -a --filter "name=^${Name}$" --format "{{.ID}}"
        if ($existing) {
            Write-Verbose "Removing Redis container '$Name'..."
            docker rm $Name | Out-Null
        }
        else {
            Write-Verbose "No Redis container '$Name' to remove."
        }
    }
}

Write-Verbose "Stopping Smart Comp Web services..."
Stop-WindowedServices -Titles $serviceTitles

Write-Verbose "Closing common Smart Comp Web ports..."
Close-Ports -Ports $servicePorts

Write-Verbose "Stopping Redis Docker container (if running)..."
Stop-RedisContainer -Name $redisContainerName -Remove:$RemoveRedisContainer

Write-Host "Shutdown complete. Local services and common ports have been cleared." -ForegroundColor Green
