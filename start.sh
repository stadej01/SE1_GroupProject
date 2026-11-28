#!/usr/bin/env bash
# Start a local PR review, or select the existing cloud-backed setup with --neon.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python="$root/backend/.venv/bin/python"
settings="--settings=config.settings_neon"

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

if [ "$#" -eq 0 ]; then
  "$root/setup.sh"
  exec "$python" "$root/backend/start_review.py"
fi
[ "$#" -eq 1 ] && [ "$1" = "--neon" ] || fail "Usage: ./start.sh [--neon]"

[ -x "$python" ] || fail "Run ./setup.sh first."
[ -f "$root/backend/editor/static/editor/dist/manifest.json" ] || fail "Frontend assets are missing. Run ./setup.sh first."
[ -f "$root/.env" ] || fail "No .env found. See the Neon setup in README.md."

cd "$root/backend"
"$python" manage.py check "$settings" || exit 1

# A pending migration exits silently; a database error prints its reason.
if ! output="$("$python" manage.py migrate --check "$settings" 2>&1)"; then
  if [ -z "$output" ]; then
    fail "The database has unapplied migrations. Ask the database maintainer to apply the migrations described in README.md."
  fi
  printf '%s\n' "$output" | tail -n 3 >&2
  fail "Could not read the database. Check DATABASE_URL in .env."
fi

exec "$python" manage.py runserver 127.0.0.1:8000 "$settings"
