# Separate demo validation

This source snapshot keeps the editor and the account/team demo independent.

## Checks completed on the supplied source

- Python syntax checked for all backend `.py` files.
- Django system check passed for the local editor settings.
- **13/13 editor Django tests passed** using local SQLite.
- **16/16 parser/graph unit tests passed**; the old JSON fixture comparison now tolerates newer metadata fields.
- **10/10 accounts/team/health tests passed** using an isolated SQLite test profile, not Neon.
- TypeScript `npm run typecheck` passed after adding explicit types to two React components.
- All previous Git conflict-marker lines were removed from the new source snapshot.

## Not verified here

- Connection to the real Neon database, because shared credentials were not provided and no live database should be changed as part of this merge.
- React browser/end-to-end tests. The uploaded `node_modules` contained dependencies for macOS, not a complete Linux runtime; frontend test execution in this environment could not load `esbuild`.
- Completion of the original Git rebase. The original ZIP contained an in-progress rebase with three more commits queued. This archive is a clean source tree without `.git`.

## How the accounts tests were isolated

The accounts demo test profile (`config.settings_auth_test`) overrides the database with in-memory SQLite before the Django app initializes. The application-level tests run against the original accounts/teams models and admin views. In this environment only, the absent `django-environ` dependency was replaced with a local test-only environment shim; the shim is **not included in the delivered source**. On a team member's machine, install `requirements.txt` and run the test command in the README to use the real dependency.
