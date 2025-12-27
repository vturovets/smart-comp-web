Set-StrictMode -Version Latest

# Load backend\.env into this PowerShell session
Get-Content "$PSScriptRoot\.env" | ForEach-Object {
    $line = $_.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { return }

    $parts = $line.Split("=", 2)
    if ($parts.Count -ne 2) { return }

    $name  = $parts[0].Trim()
    $value = $parts[1].Trim()

    # Remove surrounding quotes if present
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
        $value = $value.Substring(1, $value.Length - 2)
    }

    # Correct way to set dynamic env var names in PowerShell
    Set-Item -Path ("Env:{0}" -f $name) -Value $value
}

# Optional: show what we loaded
Write-Host "CELERY_BROKER_URL=$env:CELERY_BROKER_URL"
Write-Host "CELERY_RESULT_BACKEND=$env:CELERY_RESULT_BACKEND"
Write-Host "APP_CORS_ORIGINS=$env:APP_CORS_ORIGINS"

python -m celery -A app.worker.celery_app worker -l INFO --pool=solo
