# Dialogue Scripting Tool

A browser editor for writing dialogue as Markdown and arranging it as a node graph.
Register, create a project, edit its dialogue, and save its text and node positions.
Neon stores project data; a private GitHub repository stores Markdown and its history.

## Quick start

### Before you start

Install Python **3.12** and Node.js **22.12 or newer** (with npm). Create free [Neon](https://console.neon.tech/) and [GitHub](https://github.com/) accounts.
Open one terminal in the repository root: the folder containing `backend/`, `frontend/`, and `.env.example`. Keep this terminal open through all six steps.

### 1. Install dependencies and build the frontend

From the repository root, run:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd ../frontend
npm ci
npm run build
cd ../backend
```

<details>
<summary>Windows PowerShell</summary>

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd ../frontend
npm ci
npm run build
cd ../backend
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in this terminal, then repeat the activation command and continue.
</details>

**You should see:** package installation completes and Vite reports `built in`. Your terminal is now in `backend/`, with the Python environment active.

### 2. Create your Neon database

In the Neon console, create a project. Open **Connect**, select your database, turn **Connection pooling** off, and copy the connection string for step 4. Keep the terminal in `backend/`. [Neon connection guide](https://neon.com/docs/connect/connect-from-any-app).

![Neon Connect with pooling off and credentials hidden](docs/images/project-api/neon-connect.png)

**You should see:** a connection string starting with `postgresql://`, with `sslmode=require` and no `-pooler` in the hostname.

### 3. Create your private GitHub repository and token

In your browser, [create a private repository](https://github.com/new) under your own account. Enable **Add a README file** to create its `main` branch.
Open **Settings > Developer settings > Personal access tokens > Fine-grained tokens** and generate a token. Select your account as **Resource owner**, choose **Only select repositories**, and select the new repository. Set **Contents** to **Read and write**, then copy the token for step 4. [GitHub token guide](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).

GitHub configuration is required for local runs. Without it, saved Markdown stays in server memory and projects fail to open after a server restart.
Keep the terminal in `backend/`.

**You should see:** a private repository with a README on `main`, and a token with access to that repository.

### 4. Create `.env` and check the settings

From `backend/`, copy the example and generate a secret key:

```bash
cp ../.env.example ../.env
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

<details>
<summary>Windows PowerShell</summary>

```powershell
Copy-Item ../.env.example ../.env
python -c "import secrets; print(secrets.token_urlsafe(50))"
```
</details>

Open `.env` in the repository root and fill in:

| Variable | Value |
| --- | --- |
| `DJANGO_SECRET_KEY` | The generated secret key |
| `DATABASE_URL` | The Neon connection string from step 2 |
| `GITHUB_REPOSITORY` | Your private repository as `owner/name` |
| `GITHUB_TOKEN` | The token from step 3 |

Keep `DJANGO_DEBUG=True` for local static files and login cookies over HTTP. Keep `GITHUB_BRANCH=main` and the supplied `DJANGO_ALLOWED_HOSTS`.
**This repository is public. Never commit `.env`.**

From `backend/`, run this command on both platforms:

```bash
python manage.py check --settings=config.settings_neon
```

**You should see:** `System check identified no issues`. This checks that Django can load the settings. Steps 5 and 6 check the database and GitHub connections.

### 5. Create the tables and start the service

From `backend/`, with the Python environment active, run on both platforms:

```bash
python manage.py migrate --plan --settings=config.settings_neon
python manage.py migrate --settings=config.settings_neon
python manage.py runserver 127.0.0.1:8000 --settings=config.settings_neon
```

Include `--settings=config.settings_neon` in every command above. `manage.py` defaults to the old SQLite demo. A merchant example with no login page means you started that demo.

**You should see:** migrations marked `OK` (or `No migrations to apply`), then `Starting development server at http://127.0.0.1:8000/`. Leave this terminal running and open [the app](http://127.0.0.1:8000/). The first page is **Log in**.

### 6. Create and save your first project

In the browser, choose **Create an account**, enter your details, and submit. Registration creates your personal team.
**You should see:** **Your projects**, your team, and a **New project** form.

Enter `My first dialogue` as the project name and click **Create project**.
**You should see:** an empty Markdown box and an empty graph.

Paste this into the Markdown box and click **Parse**:

```markdown
<!-- start: Node_Greeting -->
# Node_Greeting
<!-- category: shop, color: blue -->
Merchant: Welcome, traveler.
* "Browse the shop" -> Node_Shop

# Node_Shop
Merchant: Take your time.
<<jump: Node_Greeting>>
```

**You should see:** two nodes, two connections, and a **START** label on `Node_Greeting`. Parsing completes without a dialog.

Drag a node, click **Save**, wait for **Saved**, then refresh the page. Open your private GitHub repository and view its commits.
**You should see:** the same Markdown, two nodes, two connections, and the saved positions. GitHub has a commit named `Save My first dialogue (...) revision 2 by ...`, containing `projects/<project_id>.md`.

## Start again later

From the repository root:

```bash
cd backend
source .venv/bin/activate
python manage.py runserver 127.0.0.1:8000 --settings=config.settings_neon
```

<details>
<summary>Windows PowerShell</summary>

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py runserver 127.0.0.1:8000 --settings=config.settings_neon
```
</details>

**You should see:** the server address. Open [the app](http://127.0.0.1:8000/), log in, and choose your project. Its text, graph, and positions load automatically. Stop the server with `Ctrl+C`.

## Using the editor

- **Parse** builds the graph. Editing Markdown clears the old graph until you parse again.
- Click a node to select its source and edit its fields. **×** and **Cancel** close the details and discard changes that are not applied. While such changes exist, clicking an empty part of the graph or another node keeps the details open; otherwise an empty click closes them and a node click switches to that node.
- **+ New node**, connection handles, and the controls under **Connections** edit the graph. **Parse** or **Save** applies those graph edits to Markdown.
- **Save** stores Markdown and positions. Each successful save advances the revision. A Markdown change also creates a GitHub commit.
- Invalid Markdown can be saved. Parse shows errors and source lines to fix.
- **Starting nodes** selects conversation entry nodes. **Layout**, under **View**, switches between horizontal and vertical graphs.
- Drag the line between the two panels to resize them. Double-click it to restore the default width.
- `Ctrl`/`⌘` + `Enter` parses; `Ctrl`/`⌘` + `S` saves.
- With unsaved text, graph edits, or moved nodes, **← Projects** asks whether to save or discard. Closing the tab, refreshing, and **Log out** use the browser's own prompt instead.

Use `# Node_ID` for a node, `Speaker: text` for dialogue, `* "Choice" -> Node_ID` for a choice, and `<<jump: Node_ID>>` for a jump. Put `<!-- start: Node_ID -->` before the first heading to mark a starting node. See [the merchant sample](fixtures/merchant.md) for a larger dialogue.

### Changing the frontend

In a second terminal, from `frontend/`, run `npm run dev` on either platform. It rebuilds files when you edit them. Refresh the Django page after a build.
**You should see:** Vite watching for file changes. Run `npm ci` after dependency changes; run `npm run build` for a single build.

## Run the tests

**Never run tests with `config.settings_neon`.** Use the commands below from the repository root. They use local SQLite databases and memory storage.

```bash
cd backend
source .venv/bin/activate
python manage.py test accounts teams config projects --settings=config.settings_auth_test
python manage.py test editor --settings=config.settings
python -m unittest discover -s tests -p 'test_*.py'
cd ../frontend
npm run typecheck
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

<details>
<summary>Windows PowerShell</summary>

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py test accounts teams config projects --settings=config.settings_auth_test
python manage.py test editor --settings=config.settings
python -m unittest discover -s tests -p 'test_*.py'
cd ../frontend
npm run typecheck
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```
</details>

**You should see:** Python tests finish with `OK`, frontend tests pass, typecheck exits successfully, and Playwright reports all tests passed.
Playwright starts its own services: the existing editor tests use port 8765; project tests use port 8766 with `config.settings_e2e`. Their ignored `.sqlite3` files persist between runs. Project tests create unique accounts each time.

For a manual browser check without cloud services, use `config.settings_e2e`. From `backend/`, with the Python environment active and the frontend built:

```bash
export DJANGO_DATABASE_PATH="$PWD/manual-e2e.sqlite3"
python manage.py migrate --settings=config.settings_e2e
python manage.py runserver 127.0.0.1:8766 --settings=config.settings_e2e
```

<details>
<summary>Windows PowerShell</summary>

```powershell
$env:DJANGO_DATABASE_PATH = "$PWD/manual-e2e.sqlite3"
python manage.py migrate --settings=config.settings_e2e
python manage.py runserver 127.0.0.1:8766 --settings=config.settings_e2e
```
</details>

**You should see:** the login page at [port 8766](http://127.0.0.1:8766/). This mode uses SQLite and memory storage; saved Markdown lasts for one server run. Close this terminal when finished.

## If something goes wrong

| What you see | What to do |
| --- | --- |
| `Set the DJANGO_SECRET_KEY environment variable` | Put `.env` beside `README.md` and fill in `DJANGO_SECRET_KEY`. Restart from `backend/`. |
| The merchant example opens without login | Stop the server. From `backend/`, run `python manage.py runserver 127.0.0.1:8000 --settings=config.settings_neon`. |
| `Frontend assets are missing` | From `frontend/`, run `npm ci` and `npm run build`, then refresh. |
| `Project storage is not available right now` | Correct `GITHUB_REPOSITORY`, `GITHUB_TOKEN`, and `GITHUB_BRANCH` in `.env`. Give the token Contents read and write access. Restart the server and retry Save. |
| `connection failed` and `Connection refused` | Replace `DATABASE_URL` with the direct connection string from Neon Connect, including `sslmode=require`, then restart. |
| `You do not belong to a team yet` | Add the account under **Teams > Team memberships** in Django admin, then refresh the home page. |
| `Error: That port is already in use.` | Press `Ctrl+C` in the terminal running the earlier server, then start this service again. |

## Reference

### Settings

| Module | Use |
| --- | --- |
| `config.settings_neon` | Local app with accounts, teams, projects, Neon, and GitHub |
| `config.settings_auth_test` | Automated account and project tests with temporary SQLite |
| `config.settings_e2e` | Browser checks with file-based SQLite and memory storage |
| `config.settings` | Old SQLite editor demo and its tests; `manage.py` default |

### Main files

| Path | Purpose |
| --- | --- |
| [backend/accounts/](backend/accounts/) | Email accounts, login, and registration |
| [backend/teams/](backend/teams/) | Teams and membership |
| [backend/projects/](backend/projects/) | Project pages, API, positions, and GitHub storage |
| [backend/config/](backend/config/) | Settings and shared routes |
| [backend/editor/](backend/editor/) | Editor page, assets, and parse endpoint |
| [backend/dialogue_graph/](backend/dialogue_graph/) | Markdown parser and graph validation |
| [frontend/src/main.tsx](frontend/src/main.tsx) | Editor controls and graph edits |
| [frontend/src/project/](frontend/src/project/) | Loading, saving, positions, and unsaved state |
| [frontend/src/components/](frontend/src/components/) | Graph, nodes, and edges |
| [frontend/e2e/](frontend/e2e/) | Browser tests |

### Project API

Requests use the browser's login session; writes also send its CSRF token.

| Request | Result |
| --- | --- |
| `POST /api/v1/projects` | Create with `name` and `team_id`; returns `201` |
| `GET /api/v1/projects/<project_id>` | Read Markdown, `revision`, and `layout_data` |
| `PUT /api/v1/projects/<project_id>/save` | Send `markdown_source`, `layout_data.nodes`, and `base_revision`; returns the new revision |

A stale save returns `409`. Failed storage reads or writes return `503`. The editor displays the reason and keeps unsaved text available.

### Inspect the latest project in Neon

Run this read-only query in the Neon **SQL Editor**:

```sql
select p.id, p.name, p.revision, p.head_commit_sha, n.node_id, n.x, n.y
from projects_project p
left join projects_nodeposition n on n.project_id = p.id
where p.id = (select id from projects_project order by created_at desc limit 1)
order by n.node_id;
```

**You should see:** one row per saved node, with the project's revision, GitHub commit SHA, and coordinates.

### Add another person to a team

From `backend/`, with the Python environment active, run `python manage.py createsuperuser --settings=config.settings_neon` on either platform and enter the requested details.
**You should see:** `Superuser created successfully.` Start the service with the Quick start command, then sign in at [Django admin](http://127.0.0.1:8000/admin/).

![Django admin login](docs/images/project-api/admin-login.png)

The other person first registers in the app. Under **Teams > Team memberships**, select their account and your team, then save.
**You should see:** the new membership. That person can now open your team's projects.

![Adding a team membership](docs/images/project-api/admin-team-membership.png)

### Old SQLite demo

From `backend/`, with the Python environment active:

```bash
python manage.py migrate --settings=config.settings && python manage.py runserver 127.0.0.1:8000 --settings=config.settings
```

<details>
<summary>Windows PowerShell</summary>

```powershell
python manage.py migrate --settings=config.settings
python manage.py runserver 127.0.0.1:8000 --settings=config.settings
```
</details>

**You should see:** the merchant editor at port 8000. This old demo will be removed later.

### Current limitations

- The parser uses a regex prototype. The planned Lark parser and full dialogue language are pending.
- Save stores text and positions without running the parser. Its `diagnostics` stays empty; positions for deleted nodes remain stored.
- Layout direction resets when a project reopens.
- Browsers do not allow a custom dialog when a tab closes. Only **← Projects** offers save or discard; other ways of leaving use the browser's built-in prompt.
- Write the first node of a new project in Markdown before adding more nodes through the graph.
- Registration and login pages are temporary. US-31b will replace them.
- The service targets local development and demos. Registration is open.
