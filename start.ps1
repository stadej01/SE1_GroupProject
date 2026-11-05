# Check the configuration and database, then start the full app.
# It never writes .env, never migrates, and never clears data.
$ErrorActionPreference = "Continue"

$root = $PSScriptRoot
$python = Join-Path $root "backend/.venv/Scripts/python.exe"
$settings = "--settings=config.settings_neon"

function Stop-Start([string]$Message) {
  [Console]::Error.WriteLine($Message)
  exit 1
}

if (-not (Test-Path $python)) { Stop-Start "Run .\setup.ps1 first." }
if (-not (Test-Path (Join-Path $root "backend/editor/static/editor/dist/manifest.json"))) {
  Stop-Start "Frontend assets are missing. Run .\setup.ps1 first."
}
if (-not (Test-Path (Join-Path $root ".env"))) {
  Stop-Start "No .env found. Create it as README.md describes, or put the shared .env you received beside README.md."
}

Set-Location (Join-Path $root "backend")
& $python manage.py check $settings
if ($LASTEXITCODE -ne 0) { exit 1 }

# A pending migration exits silently; a database error prints its reason.
$output = & $python manage.py migrate --check $settings 2>&1
if ($LASTEXITCODE -ne 0) {
  if (-not $output) {
    Stop-Start "The database has unapplied migrations. In your own environment, confirm DATABASE_URL, then run from backend/: python manage.py migrate --settings=config.settings_neon. With a shared .env, ask its maintainer."
  }
  $output | Select-Object -Last 3 | ForEach-Object { [Console]::Error.WriteLine($_) }
  Stop-Start "Could not read the database. Check DATABASE_URL in .env."
}

& $python manage.py runserver 127.0.0.1:8000 $settings
exit $LASTEXITCODE
