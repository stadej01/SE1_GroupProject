# Start a local PR review, or select the existing cloud-backed setup with -Neon.
[CmdletBinding()]
param([switch]$Neon)
$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$python = Join-Path $root "backend/.venv/Scripts/python.exe"
$manage = Join-Path $root "backend/manage.py"
$settings = "--settings=config.settings_neon"

function Stop-Start([string]$Message) {
  [Console]::Error.WriteLine($Message)
  exit 1
}

if (-not $Neon) {
  & (Join-Path $root "setup.ps1")
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  & $python (Join-Path $root "backend/start_review.py")
  exit $LASTEXITCODE
}

if (-not (Test-Path $python)) { Stop-Start "Run .\setup.ps1 first." }
if (-not (Test-Path (Join-Path $root "backend/editor/static/editor/dist/manifest.json"))) {
  Stop-Start "Frontend assets are missing. Run .\setup.ps1 first."
}
if (-not (Test-Path (Join-Path $root ".env"))) {
  Stop-Start "No .env found. See the Neon setup in README.md."
}

& $python $manage check $settings
if ($LASTEXITCODE -ne 0) { exit 1 }

# A pending migration exits silently; a database error prints its reason.
# Windows PowerShell writes native stderr to the error stream. Capture it below.
$ErrorActionPreference = "Continue"
$output = & $python $manage migrate --check $settings 2>&1
if ($LASTEXITCODE -ne 0) {
  if (-not $output) {
    Stop-Start "The database has unapplied migrations. Ask the database maintainer to apply the migrations described in README.md."
  }
  $output | Select-Object -Last 3 | ForEach-Object { [Console]::Error.WriteLine($_) }
  Stop-Start "Could not read the database. Check DATABASE_URL in .env."
}

& $python $manage runserver 127.0.0.1:8000 $settings
exit $LASTEXITCODE
