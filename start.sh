#!/usr/bin/env bash
# Check the configuration and database, then start the full app.
# It never writes .env, never migrates, and never clears data.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python="$root/backend/.venv/bin/python"
settings="--settings=config.settings_neon"

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

[ -x "$python" ] || fail "Run ./setup.sh first."
[ -f "$root/backend/editor/static/editor/dist/manifest.json" ] || fail "Frontend assets are missing. Run ./setup.sh first."
[ -f "$root/.env" ] || fail "No .env found. Create it as README.md describes, or put the shared .env you received beside README.md."

cd "$root/backend"
"$python" manage.py check "$settings" || exit 1

# A pending migration exits silently; a database error prints its reason.
if ! output="$("$python" manage.py migrate --check "$settings" 2>&1)"; then
  if [ -z "$output" ]; then
    fail "The database has unapplied migrations. In your own environment, confirm DATABASE_URL, then run from backend/: python manage.py migrate --settings=config.settings_neon. With a shared .env, ask its maintainer."
  fi
  printf '%s\n' "$output" | tail -n 3 >&2
  fail "Could not read the database. Check DATABASE_URL in .env."
fi

exec "$python" manage.py runserver 127.0.0.1:8000 "$settings"
