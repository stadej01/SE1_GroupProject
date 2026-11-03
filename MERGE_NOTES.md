# Merge notes — editor and accounts demos

This folder is a complete local Git checkout with the rebase resolved. It contains the `.git/` directory, unlike the earlier source-only ZIP. The original uploaded repository was copied before the rebase was continued; the original upload and remote GitHub repository were not modified.

## Git resolution

- Branch: `js_US-01_mkd2GUI`
- Rebasing onto: `a265b86` (team accounts/teams baseline)
- All four queued commits have been processed and the rebase completed.
- Conflict markers and unmerged Git index entries were resolved; the working tree was clean after the rebase.
- Git history was rewritten locally by the rebase. **Do not force-push or replace the team's branch without coordinating with the team.**
- We deliberately removed generated dependencies (`node_modules/`, `__pycache__/`, `.venv/`) and the local SQLite database from the rebased commit instead of committing them.

## Files that required conflict resolution

- `README.md`
- `backend/requirements.txt`
- `backend/manage.py`
- `backend/config/settings.py`
- `backend/config/urls.py`
- `backend/config/asgi.py`
- `backend/config/wsgi.py`
- `.gitignore` (during the second commit)
- `backend/tests/test_graph.py` (during the fourth commit)

## Configuration decisions

- `config.settings` is the default for the dialogue editor: React Flow, Markdown parser, session-based local SQLite drafts. It does not load Neon credentials.
- `config.settings_neon` is for the accounts/teams demo with the custom user model, Django admin, and Neon PostgreSQL.
- `config.urls` and `config.urls_neon` keep the two demos' routes separate.
- `config.settings_auth_test` runs accounts/teams tests against temporary SQLite, without contacting Neon.
- `backend/requirements.txt` combines the dependencies needed for both demos.

## Validation

After completing the rebase, Django checks and tests passed:

- Editor tests: 13
- Parser/graph tests: 19
- Accounts/teams/config tests: 10, using isolated SQLite
- TypeScript typecheck: passed using cached dependencies

The frontend browser tests and the live Neon connection were not verified. The frontend unit-test runner was blocked by an incomplete Linux dependency cache; local `npm install` should provide the appropriate dependencies on macOS or Windows.

## Safely using this checkout

1. Extract this ZIP into a **new directory**. Avoid overwriting an existing `.git/` folder or an active team checkout.
2. From that directory, run `git status` and `git log --oneline -5` to verify the completed local rebase.
3. Follow `README.md` to set up the app's Python and Node dependencies. For the Neon demo, provide the team's `.env` values separately; no `.env` credentials are included.
4. Have your teammates review the rebase before pushing. Because the branch was rebased, ordinary pushes may be rejected; don't force-push without explicit agreement.

The remote GitHub repository and the shared Neon database have not been changed.
