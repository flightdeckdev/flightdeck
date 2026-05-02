#Requires -Version 5.1
<#
.SYNOPSIS
  Run optional PostgreSQL storage tests (tests/test_storage_postgres.py).

.DESCRIPTION
  1. Install the driver: close any process using flightdeck.exe, then from repo root:
       uv sync --extra dev --extra postgres
     (Or: uv pip install "psycopg[binary]>=3.2" into your venv if sync cannot replace the CLI shim.)

  2. Start PostgreSQL with an empty database, e.g. Docker:
       docker run -d --rm --name fd-pg-test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=flightdeck_test -p 5432:5432 postgres:16
     Wait ~5s for ready, then:
       $env:FLIGHTDECK_TEST_POSTGRES_URL = 'postgresql://postgres:test@127.0.0.1:5432/flightdeck_test'

  3. From repo root:
       .\scripts\run_postgres_tests.ps1

  With -Docker, this script tries to start/stop the container above (requires Docker on PATH).
#>
param(
    [switch] $Docker,
    [string] $PostgresUrl = "postgresql://postgres:test@127.0.0.1:5432/flightdeck_test"
)

$ErrorActionPreference = "Stop"
# PSScriptRoot = .../flightdeck/scripts  -> repo root is parent
$root = Split-Path $PSScriptRoot -Parent

Push-Location $root
try {
    $py = Join-Path $root ".venv\Scripts\python.exe"
    if (-not (Test-Path $py)) {
        Write-Error "No .venv\Scripts\python.exe — run: uv sync --extra dev --extra postgres"
    }

    & $py -c "import psycopg" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "psycopg not installed. Close apps using flightdeck.exe, then run: uv sync --extra dev --extra postgres"
    }

    $startedDocker = $false
    if ($Docker) {
        $docker = Get-Command docker -ErrorAction SilentlyContinue
        if (-not $docker) {
            Write-Error "Docker not on PATH; start Postgres yourself or install Docker Desktop."
        }
        docker rm -f fd-pg-test 2>$null | Out-Null
        docker run -d --name fd-pg-test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=flightdeck_test -p 5432:5432 postgres:16
        $startedDocker = $true
        Write-Host "Waiting for Postgres..." -ForegroundColor Cyan
        Start-Sleep -Seconds 6
    }

    $env:FLIGHTDECK_TEST_POSTGRES_URL = $PostgresUrl
    & $py -m pytest tests/test_storage_postgres.py -v --tb=short
    $code = $LASTEXITCODE

    if ($startedDocker) {
        docker rm -f fd-pg-test 2>$null | Out-Null
        Write-Host "Stopped container fd-pg-test." -ForegroundColor Cyan
    }

    if ($code -ne 0) { exit $code }
}
finally {
    Pop-Location
}
