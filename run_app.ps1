# Shopping Tracker - Run Script for PowerShell
# Right-click and select "Run with PowerShell"

Write-Host "============================================================" -ForegroundColor Green
Write-Host "Starting Shopping Tracker..." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

# Change to script directory
Set-Location $PSScriptRoot

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to activate virtual environment" -ForegroundColor Red
    Write-Host "Please run: python -m venv venv" -ForegroundColor Red
    Write-Host "Then run: pip install -r requirements.txt" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Virtual environment activated!" -ForegroundColor Green
Write-Host "Starting Flask application..." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

# Run the application as a module (not as a script)
python -m app.main

# If we get here, the app has stopped
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Application stopped." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Read-Host "Press Enter to exit"
