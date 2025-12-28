param(
    [switch] $Verbose = $false
)

Set-StrictMode -Version Latest

# Enable or suppress verbose output explicitly for older PowerShell versions.
if ($Verbose) {
    $VerbosePreference = 'Continue'
} else {
    $VerbosePreference = 'SilentlyContinue'
}

# Quick launch helper for Smart Comp Web on Windows PowerShell.
# It prepares environment files, ensures dependencies, starts Redis (via Docker),
# and spawns the backend (Uvicorn), Celery worker, and Vite dev server.

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

function Ensure-EnvFile {
    param(
        [Parameter(Mandatory)][string] $Source,
        [Parameter(Mandatory)][string] $Destination
    )

    if (-not (Test-Path $Destination)) {
        Copy-Item -Path $Source -Destination $Destination -Force
        Write-Verbose "Created $(Split-Path -Leaf $Destination) from template."
    }
    else {
        Write-Verbose "Found $(Split-Path -Leaf $Destination)."
    }
}

function Ensure-Command {
    param([Parameter(Mandatory)][string] $Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' is not available on PATH."
    }
}

function Ensure-RedisContainer {
    $containerName = "smartcomp-redis"

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Warning "Docker is not available; start Redis manually on port 6379."
        return
    }

    $existing = docker ps -a --filter "name=^${containerName}$" --format "{{.ID}}"
    if (-not $existing) {
        Write-Verbose "Starting Redis container '$containerName'..."
        docker run --name $containerName -p 6379:6379 -d redis:7 | Out-Null
    }
    elseif (-not (docker ps --filter "name=^${containerName}$" --format "{{.ID}}")) {
        Write-Verbose "Starting existing Redis container '$containerName'..."
        docker start $containerName | Out-Null
    }
    else {
        Write-Verbose "Redis container '$containerName' is already running."
    }
}

function Ensure-BackendVenv {
    $backendDir = Join-Path $repoRoot "backend"
    $venvPath   = Join-Path $backendDir ".venv"
    $venvPython = Join-Path $venvPath "Scripts" | Join-Path -ChildPath "python.exe"

    if (-not (Test-Path $venvPath)) {
        Write-Verbose "Creating Python virtual environment in backend/.venv ..."
        Push-Location $backendDir
        python -m venv .venv
        Pop-Location
    }

    Push-Location $backendDir
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -e "." -e ".[dev]"
    Pop-Location

    return $venvPython
}

function Ensure-FrontendDeps {
    $frontendDir = Join-Path $repoRoot "frontend"
    if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
        Write-Verbose "Installing frontend dependencies..."
        Push-Location $frontendDir
        npm install
        Pop-Location
    }
    else {
        Write-Verbose "Frontend dependencies already installed."
    }
}

function Start-Window {
    param(
        [Parameter(Mandatory)][string] $Title,
        [Parameter(Mandatory)][string] $WorkingDirectory,
        [Parameter(Mandatory)][string] $Command
    )

    $shell = (Get-Command pwsh -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source)
    if (-not $shell) {
        $shell = (Get-Command powershell -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source)
    }

    if (-not $shell) {
        throw "No PowerShell executable found to spawn child processes."
    }

    Start-Process -FilePath $shell -ArgumentList @(
        "-NoExit",
        "-Command",
        "`$host.UI.RawUI.WindowTitle = '$Title'; Set-Location '$WorkingDirectory'; $Command"
    )
}

# 1) Ensure required CLI tools are present.
Ensure-Command python
Ensure-Command npm

# 2) Ensure environment files exist.
Ensure-EnvFile -Source (Join-Path $repoRoot "backend/.env.example") -Destination (Join-Path $repoRoot "backend/.env")
Ensure-EnvFile -Source (Join-Path $repoRoot "frontend/.env.example") -Destination (Join-Path $repoRoot "frontend/.env")

# 3) Start Redis (Docker) if available.
Ensure-RedisContainer

# 4) Prepare backend virtual environment and install deps.
$venvPython = Ensure-BackendVenv
$venvActivate = Join-Path $repoRoot "backend/.venv/Scripts/Activate.ps1"

# 5) Prepare frontend dependencies.
Ensure-FrontendDeps

# 6) Launch services in separate terminals.
Start-Window -Title "SmartComp - Celery Worker" -WorkingDirectory (Join-Path $repoRoot "backend") -Command ". '$venvActivate'; .\celery_worker.ps1"
Start-Window -Title "SmartComp - API" -WorkingDirectory (Join-Path $repoRoot "backend") -Command ". '$venvActivate'; python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
Start-Window -Title "SmartComp - Frontend" -WorkingDirectory (Join-Path $repoRoot "frontend") -Command "npm run dev -- --host --port 5173"

Write-Host "Launch complete. Services are starting in separate windows:" -ForegroundColor Green
Write-Host "  - API:        http://localhost:8000/api/health" -ForegroundColor Green
Write-Host "  - Frontend:   http://localhost:5173" -ForegroundColor Green
Write-Host "  - Redis:      localhost:6379 (Docker container 'smartcomp-redis')" -ForegroundColor Green
