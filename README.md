# SE1 Group Project

This repository currently has two Django demos. They share a codebase but **do not share a database**. We are keeping them separate for this sprint and can integrate authentication with the dialogue editor later.

- **Dialogue editor:** Markdown-to-node graph editing with React Flow. Drafts save in a local SQLite database. Run on **port 8000**.
- **Accounts and teams:** Django admin demo with email-based user accounts and team memberships. Uses **Neon PostgreSQL**. Run on **port 8001**.

The Markdown parser, graph conversion, and React frontend do not read or write to Neon. The accounts demo does not install the `editor` app.

## Requirements

- Python **3.12** (team's pinned dependencies target this version)
- Node.js **22.12+** and npm
- Access to the team's Neon database **only for the accounts demo**

Open a terminal in the project root (the folder containing `frontend/` and `backend/`).

## macOS: first-time setup

**Terminal 1: compile the React frontend**

```bash
cd frontend
npm install
npm run dev
```

`npm run dev` watches and rebuilds assets for Django; it does not start a separate web server. Leave it open. For a one-time production-style build instead, use `npm run build`.

**Terminal 2: dialogue editor (local SQLite)**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Visit **http://127.0.0.1:8000/**. No Neon credentials are needed for this demo.

**Terminal 3: accounts/teams demo (Neon)**

From the project root, create `.env` from `.env.example` and fill in the team's `DATABASE_URL` and `DJANGO_SECRET_KEY`. Ask the teammate responsible for Neon for the connection details. Never commit the `.env` file.

```bash
cd backend
source .venv/bin/activate
python manage.py check --settings=config.settings_neon
python manage.py runserver 127.0.0.1:8001 --settings=config.settings_neon
```

Visit **http://127.0.0.1:8001/admin/** and sign in with an existing admin account. The health endpoint is **http://127.0.0.1:8001/api/v1/health/**.

**Do not run `migrate`, `createsuperuser`, or tests against the shared Neon database without coordinating with the team.** These commands can change data or schema. The accounts demo requires the team's tables and admin user to already exist.

## Windows PowerShell: first-time setup

Start three PowerShell windows in the project root.

**Terminal 1: frontend**

```powershell
cd frontend
npm install
npm run dev
```

**Terminal 2: dialogue editor**

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

If PowerShell blocks the activation script, run `Set-ExecutionPolicy -Scope Process Bypass` in that terminal and try again.

**Terminal 3: accounts/teams demo**

Create `.env` in the project root using `.env.example`, fill in the shared Neon credentials, then:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py check --settings=config.settings_neon
python manage.py runserver 127.0.0.1:8001 --settings=config.settings_neon
```

Use **http://127.0.0.1:8001/admin/**. As with macOS, don't run migrations or create users on shared Neon without your team's agreement.

## Running it again

There is no need to recreate `.venv` or run `npm install` each time unless the dependencies have changed.

1. Frontend: `cd frontend && npm run dev`.
2. Editor: `cd backend`, activate `.venv`, then `python manage.py runserver 127.0.0.1:8000`.
3. Accounts: in another backend terminal, activate `.venv`, then `python manage.py runserver 127.0.0.1:8001 --settings=config.settings_neon`.

Remember that `python manage.py migrate` without `--settings` only migrates the local SQLite editor database.

## Tests

From `backend/`, with the virtual environment active:

```bash
# Editor and parser tests: local SQLite only
python manage.py test editor
python -m unittest discover -s tests -p 'test_*.py' -v

# Accounts/teams tests: isolated temporary SQLite, not Neon
python manage.py test accounts teams config --settings=config.settings_auth_test
```

The TypeScript graph tests run from `frontend/`:

```bash
npm run typecheck
npm test
```

The Neon test settings use the actual accounts/teams Django models and admin, but point Django to a local, temporary SQLite test database. This checks behavior without making a connection to the shared service; it is not a substitute for a later PostgreSQL integration test.

## Main files

| File | Purpose |
| --- | --- |
| `backend/config/settings.py` | Editor settings: local SQLite, editor app, no Neon access. |
| `backend/config/urls.py` | Editor URL routes (`/`, `/sync`, `/save`). |
| `backend/config/settings_neon.py` | Teammates' accounts/teams settings: Neon and custom user model. |
| `backend/config/urls_neon.py` | Accounts demo routes (`/admin/`, `/api/v1/health/`). |
| `backend/config/settings_auth_test.py` | Safe, SQLite-only settings for accounts/teams tests. |
| `backend/accounts/` | Email-based custom user model, admin, and tests. |
| `backend/teams/` | Team membership models, admin, and tests. |
| `backend/editor/` | Draft persistence and Django endpoints for the editor. |
| `backend/dialogue_graph/` | Markdown parser, validation, and graph conversion; independent of Django and Neon. |
| `frontend/src/main.tsx` | Browser editor actions and React integration. |
| `frontend/src/components/` | React Flow nodes, edges, and graph. |
| `fixtures/` | Sample Markdown and its expected graph output. |

More details are in `FILE_GUIDE.md`. See `MERGE_NOTES.md` for the original conflict list and how to apply this to a Git branch currently in a rebase.

## Current limits

The parser is still the regex-based prototype rather than the proposed Lark implementation. The editor does not use login, team permissions, or a Neon project model yet. Draft ownership is session-based, and SQLite draft files are local to the machine. The accounts demo currently uses Django admin rather than a custom login page. We plan to integrate these features in a later sprint.
