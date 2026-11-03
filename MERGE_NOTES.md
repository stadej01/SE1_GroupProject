# Merge notes — independent editor and Neon demos

This package is a **clean source snapshot**, not a completed Git rebase. The uploaded repository had an active rebase and conflict markers. This ZIP intentionally excludes `.git/`, `.venv/`, `node_modules/`, and local SQLite data. It does **not** touch the remote repository or the shared Neon database.

## Conflicts found in the uploaded ZIP

- `README.md`
- `backend/requirements.txt`
- `backend/manage.py`
- `backend/config/settings.py`
- `backend/config/urls.py`
- `backend/config/asgi.py`
- `backend/config/wsgi.py`

## Resolution

- `config.settings`: editor only, local SQLite, session-based drafts, default `manage.py` settings.
- `config.settings_neon`: accounts/teams only, Neon Postgres, custom `AUTH_USER_MODEL`.
- `config.urls` and `config.urls_neon`: distinct URL maps for each demo.
- `config.settings_auth_test`: safely tests accounts/teams using temporary SQLite.
- `manage.py`, `asgi.py`, and `wsgi.py`: use `DJANGO_SETTINGS_MODULE` if explicitly supplied; otherwise default to the local editor.
- `requirements.txt`: retains the team's pinned Django, `django-environ`, and `psycopg` dependencies, which also support the editor.
- The original applications, migrations, parser, React components, and test files have not been rewritten for integration.

## Applying the work to the team's active Git rebase

**Do not overwrite the `.git/` folder.** In the original checkout, run `git status` and make a backup branch or copy first. Copy the resolved source files from this package over the corresponding files in the checkout. Stage only the files you reviewed. Use `git diff --check` and your tests before proceeding with `git rebase --continue`.

The ZIP stopped during the first of four commits; further rebase conflicts can occur. If Git reports a new conflict, inspect it before continuing. This archive does not represent a finished rebase or a push to the team's repository.

Neon safety: the default Django configuration and parser never load the Neon credentials. Do not run migrations or create users against the shared Neon database without the team's approval.
