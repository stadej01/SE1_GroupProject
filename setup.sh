#!/usr/bin/env bash
# Install dependencies and build the frontend. Safe to run again.
# It does not need .env, never writes it, and never touches a database.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv="$root/backend/.venv"

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

command -v python3.12 >/dev/null || fail "Python 3.12 is required. See \"Before you start\" in README.md."
command -v npm >/dev/null || fail "Node.js 22.12 or newer, with npm, is required. See \"Before you start\" in README.md."
node -e 'const [a, b] = process.versions.node.split(".").map(Number); process.exit(a > 22 || (a === 22 && b >= 12) ? 0 : 1)' \
  || fail "Node.js 22.12 or newer is required. This machine has $(node --version)."

if [ ! -x "$venv/bin/python" ]; then
  python3.12 -m venv "$venv"
fi
"$venv/bin/python" -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))' \
  || fail "backend/.venv does not use Python 3.12. Remove that folder and run ./setup.sh again."
"$venv/bin/python" -m pip install -r "$root/backend/requirements.txt"

(cd "$root/frontend" && npm ci && npm run build)

if [ -f "$root/.env" ]; then
  printf '\nSetup finished. Start the app with ./start.sh\n'
else
  printf '\nSetup finished. Next, create .env as README.md describes, then start the app with ./start.sh\n'
fi
