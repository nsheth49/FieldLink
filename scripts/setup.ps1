param([string]$PythonVersion = '3.12')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
& py "-$PythonVersion" -m venv backend/.venv
if ($LASTEXITCODE -ne 0) { throw 'Install the selected Python version first.' }
& backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency install failed.' }
& backend/.venv/Scripts/python.exe -m pip install -e ./backend --no-deps
& npm --prefix frontend ci
if (!(Test-Path .env)) { Copy-Item .env.example .env }
& backend/.venv/Scripts/python.exe -m app.cli migrate
& backend/.venv/Scripts/python.exe -m app.cli seed-users
Write-Host 'Run the API, worker and frontend in separate terminals. See README.md.'
