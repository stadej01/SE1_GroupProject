# SE1 Group Project

This repository contains two Django demos that we're keeping separate for this sprint:

- **Dialogue editor:** Write game dialogue in Markdown, turn it into a React Flow graph, and edit nodes and connections. Drafts are stored in a local SQLite database.

- **Accounts and teams:** Manage email-based user accounts and team memberships through Django admin. This demo uses the team's Neon PostgreSQL database.

Both demos use the same source repository, but **they do not share a database**. The dialogue parser and editor do not connect to Neon. We plan to integrate the two systems in a later sprint.

## Requirements

- Python **3.12** (recommended for the team's pinned dependencies)

- Node.js **22.12 or newer**, with npm

- Terminal on macOS or PowerShell on Windows

- Neon credentials and an existing admin account **only if you're running the accounts demo**

Start in the project root, the folder containing `backend/`, `frontend/`, and `fixtures/`.

## macOS: first-time setup

Open a separate Terminal window for each process you want to run. If you're only working on the dialogue editor, you need Terminals 1 and 2.

### Terminal 1 — Frontend build

```bash
cd frontend
npm install
npm run dev
```

Leave this terminal open. In this project, `npm run dev` runs `vite build --watch`: it builds the React files that Django serves and rebuilds them when you make changes. It doesn't start a separate frontend website.

### Terminal 2 — Dialogue editor (SQLite)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Open **http://127.0.0.1:8000/**. The editor does not need Neon credentials.

### Terminal 3 — Accounts and teams (Neon, optional)

First, create a `.env` file in the **project root** from `.env.example`. Ask the teammate managing Neon for the correct values for `DATABASE_URL` and `DJANGO_SECRET_KEY`. Do not commit `.env` to Git.

In a new terminal, starting from the project root:

```bash
cd backend
source .venv/bin/activate
python manage.py check --settings=config.settings_neon
python manage.py runserver 127.0.0.1:8001 --settings=config.settings_neon
```

Open **http://127.0.0.1:8001/admin/** and sign in using an existing admin account. The health endpoint is **http://127.0.0.1:8001/api/v1/health/**.

**Do not run migrations, create users, or run tests against the shared Neon database without checking with the team first.** This demo assumes the database and admin account have already been set up.

## Windows: first-time setup (PowerShell)

Open PowerShell terminals from the project root. Use Terminals 1 and 2 for the editor, plus Terminal 3 if you want to run the accounts demo.

### Terminal 1 — Frontend build

```powershell
cd frontend
npm install
npm run dev
```

### Terminal 2 — Dialogue editor (SQLite)

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Open **http://127.0.0.1:8000/**.

If PowerShell blocks virtual-environment activation, run the following in that terminal and try activating it again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

If the `py` launcher is unavailable, use `python -m venv .venv` with an installed Python 3.12 interpreter.

### Terminal 3 — Accounts and teams (Neon, optional)

As on macOS, create a project-root `.env` file based on `.env.example` and fill in your team's `DATABASE_URL` and `DJANGO_SECRET_KEY`.

In a new PowerShell terminal, starting from the project root:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py check --settings=config.settings_neon
python manage.py runserver 127.0.0.1:8001 --settings=config.settings_neon
```

Open **http://127.0.0.1:8001/admin/**. Avoid migrations, user creation, and tests against the shared Neon database unless the team has approved them.

## Starting the project again

You don't need to recreate `.venv` or reinstall dependencies every time. Reinstall when `requirements.txt` or `package.json` changes. Run migrations again when new Django migrations are added.

**macOS:**

```bash
# Terminal 1, from project root
cd frontend
npm run dev
```

```bash
# Terminal 2, from project root
cd backend
source .venv/bin/activate
python manage.py runserver 127.0.0.1:8000
```

**Windows PowerShell:**

```powershell
# Terminal 1, from project root
cd frontend
npm run dev
```

```powershell
# Terminal 2, from project root
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py runserver 127.0.0.1:8000
```

If you also want the accounts demo, use a third terminal with the same virtual environment and run:

```bash
python manage.py runserver 127.0.0.1:8001 --settings=config.settings_neon
```

Run that last command from `backend/`. Use `Ctrl+C` to stop either Django server or the frontend watcher.

## Using the dialogue editor

1. Write or edit dialogue in Markdown, then click **Parse Markdown** to build the graph.

2. Click a node to highlight where it came from in Markdown. You can edit its speaker, dialogue, audience, and extra fields.

3. Use **+ New node** to add a node. Connect nodes by dragging between handles or by using the **From**, **To**, and **Type** controls.

4. Select a connection and click **Delete connection** to remove it.

5. Graph edits appear immediately on the canvas but stay in a pending buffer until you click **Parse Markdown**. Then use **Save draft** to save the updated Markdown.

6. Markdown drafts with syntax errors can still be saved. Errors prevent graph generation and report a line number when one is available.

7. Use the layout controls to switch between horizontal and vertical graphs or rotate connection labels.

For example:

```markdown
# Node_Greeting
<!-- category: shop, color: blue -->
Merchant: Welcome, traveler.
Merchant: What can I do for you?
* "Browse the shop" -> Node_Shop

# Node_Shop
Merchant: Take your time.
<<jump: Node_Greeting>>
```

A larger sample is in `fixtures/merchant.md`.

## Tests

Run these checks before merging or pushing changes. The editor tests use SQLite, and the accounts/teams tests use a separate temporary SQLite test database. **None of the commands below require Neon credentials or modify the shared Neon database.** They do not verify a live Neon connection.

### macOS — run all primary tests

Start in the repository root (`SE1_GroupProject`), with the Python and Node.js dependencies installed as described above:

```bash
# Backend: Django editor, Markdown parser, and graph generation
cd backend
source .venv/bin/activate
python manage.py test editor -v 2
python -m unittest discover -s tests -p 'test_*.py' -v

# Accounts/teams models and permissions: isolated SQLite, never Neon
python manage.py test accounts teams config --settings=config.settings_auth_test

# Frontend: TypeScript, React Flow tests, and production build
cd ../frontend
npm run typecheck
npm test
npm run build
```

### Windows PowerShell — run all primary tests

Start in the repository root (`SE1_GroupProject`):

```powershell
# Backend tests
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py test editor -v 2
python -m unittest discover -s tests -p 'test_*.py' -v
python manage.py test accounts teams config --settings=config.settings_auth_test

# Frontend tests
cd ..\frontend
npm run typecheck
npm test
npm run build
```

The `editor` tests cover the Django editor endpoints, draft saving, validation, and CSRF protections. The Python `unittest` command tests Markdown parsing and graph generation. `npm test` checks TypeScript graph mapping and source-selection helpers; `npm run typecheck` catches TypeScript errors, and `npm run build` verifies that the frontend compiles.

If your Python virtual environment is missing, create it from `backend/` (`python3 -m venv .venv` on macOS) and install packages with `python -m pip install -r requirements.txt`. If frontend dependencies are missing, run `npm ci` in `frontend/` before rerunning the checks.

### Browser integration tests (optional)

From `frontend/`, install the Playwright Chromium browser if needed and run:

```bash
npx playwright install chromium
npm run test:e2e
```

The browser tests exercise the actual editor UI. Depending on the Playwright configuration, you may need to have Django serving the editor at `http://127.0.0.1:8000/`, plus the Vite build watcher, before running them.

**After testing:** `npm run build` can regenerate the tracked files under `backend/editor/static/editor/dist/`. Use `git status` from the repository root to review those changes before committing; generated files are not necessarily source-code changes.

## Main files

| File or folder | Purpose |
| --- | --- |
| `backend/config/settings.py` | Dialogue editor configuration: SQLite, editor app, and local settings. |
| `backend/config/urls.py` | Dialogue editor routes. |
| `backend/config/settings_neon.py` | Separate Neon configuration for accounts and teams. |
| `backend/config/urls_neon.py` | Accounts demo routes for Django admin and the health endpoint. |
| `backend/config/settings_auth_test.py` | SQLite-only test configuration for accounts and teams. |
| `backend/accounts/` | Custom email-based user model, admin, and tests. |
| `backend/teams/` | Team and membership models, admin, and tests. |
| `backend/editor/` | Editor page, draft saving, and parse endpoints. |
| `backend/dialogue_graph/` | Markdown parsing, validation, and graph generation. |
| `frontend/src/main.tsx` | Editor controls, API requests, and graph-editing actions. |
| `frontend/src/components/` | React Flow graph, custom nodes, and edges. |
| `frontend/src/graph/toFlow.ts` | Graph layout and edge routing. |
| `fixtures/` | Sample Markdown and expected graph output. |

See `FILE_GUIDE.md` for a more detailed breakdown. `MERGE_NOTES.md` records the original sprint merge approach.

## Troubleshooting

- **`requirements.txt` not found:** Run `pip install -r requirements.txt` inside `backend/`.

- **`manage.py` not found:** Move into `backend/` before running Django commands.

- **Vite says `build --watch`:** That's expected. Open the editor through Django at port 8000, not a Vite URL.

- **Frontend changes aren't showing up:** Check the Vite terminal for errors and refresh your browser.

- **Port already in use:** Stop the older server before restarting it. The editor is intended for port 8000; accounts uses 8001.

- **TypeScript reports missing CSS or Vite declarations:** Run `npm install` in `frontend/`, then restart the TypeScript server in your editor.

- **Neon demo doesn't start:** Check that `.env` exists in the project root and contains valid credentials. Do not post credentials in chat or commit them to the repository.

## Current limitations

The Markdown parser is still a regex-based prototype, not the planned Lark implementation. It handles basic dialogue, choices, jumps, conditions, and metadata, but not the full planned language for quests, characters, inventories, and complex state.

The dialogue editor does not yet use login, team membership permissions, or a Neon project model. Draft ownership is based on a browser session and stored locally in SQLite. Node positions are not permanently saved, and cross-file links are not implemented yet. JSON graph data exists, but a separate JSON download/export feature is still planned.

The accounts demo uses Django admin, not a custom user-facing login page. Integration with the editor is planned for a future sprint.

This setup is for local development and demos, not public deployment.
