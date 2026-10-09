$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    docker compose --profile tools run --rm --build test
    if ($LASTEXITCODE -ne 0) { throw 'CricX tests failed.' }
} finally {
    Pop-Location
}
