param(
    [switch]$ConfirmDestructiveReset
)

$ErrorActionPreference = "Stop"

if (-not $ConfirmDestructiveReset) {
    throw "This removes the local demo database. Re-run with -ConfirmDestructiveReset."
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $repositoryRoot "docker-compose.yml"
$projectFile = Join-Path $repositoryRoot "pyproject.toml"

if (-not (Test-Path -LiteralPath $composeFile) -or -not (Test-Path -LiteralPath $projectFile)) {
    throw "Repository markers were not found; refusing to reset."
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory)]
        [scriptblock]$Command,
        [Parameter(Mandatory)]
        [string]$Description
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

Push-Location $repositoryRoot
try {
    Invoke-Checked { docker compose down --volumes --remove-orphans } "Compose teardown"
    Invoke-Checked { docker compose up -d postgres } "PostgreSQL startup"
    Invoke-Checked { uv run alembic upgrade head } "Database migration"
    Invoke-Checked { uv run luma-generate-enterprise --no-write-manifests } "Dataset generation"
    Invoke-Checked { uv run luma-index-policies } "Policy indexing"
    Invoke-Checked { uv run luma-bootstrap } "Operations account bootstrap"
    Invoke-Checked { uv run luma-agent --setup-checkpoints } "Checkpoint initialization"
    Write-Host "Local demo database reset and reseeded successfully."
}
finally {
    Pop-Location
}
