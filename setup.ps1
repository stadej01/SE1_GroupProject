# Install dependencies and build the frontend. Safe to run again.
# It does not need .env, never writes it, and never touches a database.
$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$venv = Join-Path $root "backend/.venv"
$python = Join-Path $venv "Scripts/python.exe"

function Stop-Setup([string]$Message) {
  [Console]::Error.WriteLine($Message)
  exit 1
}

# Native commands do not stop the script by themselves.
function Invoke-Checked([scriptblock]$Step) {
  & $Step
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
  Stop-Setup 'Python 3.12 is required. See "Before you start" in README.md.'
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  Stop-Setup 'Node.js 22.12 or newer, with npm, is required. See "Before you start" in README.md.'
}
node -e 'const [a, b] = process.versions.node.split(\".\").map(Number); process.exit(a > 22 || (a === 22 && b >= 12) ? 0 : 1)'
if ($LASTEXITCODE -ne 0) {
  Stop-Setup "Node.js 22.12 or newer is required. This machine has $(node --version)."
}

if (-not (Test-Path $python)) {
  Invoke-Checked { py -3.12 -m venv $venv }
}
& $python -c "import sys; sys.exit(sys.version_info[:2] != (3, 12))"
if ($LASTEXITCODE -ne 0) {
  Stop-Setup "backend/.venv does not use Python 3.12. Remove that folder and run .\setup.ps1 again."
}
Invoke-Checked { & $python -m pip install -r (Join-Path $root "backend/requirements.txt") }

Push-Location (Join-Path $root "frontend")
try {
  Invoke-Checked { npm ci }
  Invoke-Checked { npm run build }
} finally {
  Pop-Location
}

if (Test-Path (Join-Path $root ".env")) {
  Write-Output "`nSetup finished. Start the app with .\start.ps1"
} else {
  Write-Output "`nSetup finished. Next, create .env as README.md describes, then start the app with .\start.ps1"
}
