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

at_least_312='import sys; sys.exit(sys.version_info < (3, 12))'

# Prefer 3.12, the version the team tests on; otherwise use python3 if it is new enough.
python=""
for candidate in python3.12 python3; do
  if command -v "$candidate" >/dev/null && "$candidate" -c "$at_least_312" 2>/dev/null; then
    python="$candidate"
    break
  fi
done
[ -n "$python" ] || fail "Python 3.12 or newer is required. See \"Before you start\" in README.md."
command -v npm >/dev/null || fail "Node.js 22.12 or newer, with npm, is required. See \"Before you start\" in README.md."
node -e 'const [a, b] = process.versions.node.split(".").map(Number); process.exit(a > 22 || (a === 22 && b >= 12) ? 0 : 1)' \
  || fail "Node.js 22.12 or newer is required. This machine has $(node --version)."

if [ ! -x "$venv/bin/python" ]; then
  "$python" -m venv "$venv"
fi
"$venv/bin/python" -c "$at_least_312" \
  || fail "backend/.venv uses Python older than 3.12. Remove that folder and run ./setup.sh again."
"$venv/bin/python" -m pip install -r "$root/backend/requirements.txt"

(cd "$root/frontend" && npm ci && npm run build)

if [ -f "$root/.env" ]; then
  printf '\nSetup finished. Start the app with ./start.sh\n'
else
  printf '\nSetup finished. Next, create .env as README.md describes, then start the app with ./start.sh\n'
fi
