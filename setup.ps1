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

$atLeast312 = "import sys; sys.exit(sys.version_info < (3, 12))"
$pythonRequired = 'Python 3.12 or newer is required. See "Before you start" in README.md.'
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { Stop-Setup $pythonRequired }
# Prefer 3.12, the version the team tests on; otherwise use the newest Python 3 if it is new enough.
# cmd hides the launcher's error when 3.12 is missing; PowerShell 5.1 would stop on redirected stderr.
cmd /c "py -3.12 -c pass >nul 2>&1"
$pyVersion = if ($LASTEXITCODE -eq 0) { "-3.12" } else { "-3" }
py $pyVersion -c $atLeast312
if ($LASTEXITCODE -ne 0) { Stop-Setup $pythonRequired }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  Stop-Setup 'Node.js 22.12 or newer, with npm, is required. See "Before you start" in README.md.'
}
# No double quotes inside: PowerShell 5.1 and 7 pass them to node differently.
node -e "const [a, b] = process.versions.node.split('.').map(Number); process.exit(a > 22 || (a === 22 && b >= 12) ? 0 : 1)"
if ($LASTEXITCODE -ne 0) {
  Stop-Setup "Node.js 22.12 or newer is required. This machine has $(node --version)."
}

if (-not (Test-Path $python)) {
  Invoke-Checked { py $pyVersion -m venv $venv }
}
& $python -c $atLeast312
if ($LASTEXITCODE -ne 0) {
  Stop-Setup "backend/.venv uses Python older than 3.12. Remove that folder and run .\setup.ps1 again."
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
