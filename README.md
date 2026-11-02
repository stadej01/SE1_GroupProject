# SE1_GroupProject

## Install

Use Python 3.12. Run commands from the repository root and choose one installation method.

### uv

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip sync backend/requirements.txt
```

### Python venv and pip

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
```

On Windows PowerShell, use `py -3.12` to create the environment and
`.\.venv\Scripts\Activate.ps1` to activate it.

To change dependencies, edit `backend/requirements.in`, then regenerate the
pinned requirements with uv:

```bash
uv pip compile --universal --python-version 3.12 backend/requirements.in --output-file backend/requirements.txt
```

Install the updated requirements using the chosen installation method.

## Configure

Create a local environment file and generate a Django key:

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Put the generated key in `DJANGO_SECRET_KEY`.

To get a `DATABASE_URL`, create a free Neon project with only the Postgres
database service. In the project's **Connect** dialog, turn off **Connection
pooling** and copy the URL into `.env`. Tests create and drop a temporary
database, which fails through a pooled connection. Put the real URL only in
`.env`, because `.env.example` is committed.

| Variable | Configuration |
| --- | --- |
| `DJANGO_SECRET_KEY` | Generated Django key. |
| `DJANGO_DEBUG` | `True` for local development; defaults to `False`. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames, such as `localhost,127.0.0.1`. |
| `DATABASE_URL` | Neon Postgres connection URL, without connection pooling. |
| `GITHUB_REPOSITORY` | Private repository for project Markdown, as `owner/name`. Optional. |
| `GITHUB_TOKEN` | Fine-grained token for that repository. |
| `GITHUB_BRANCH` | Branch that receives saves; defaults to `main`. |

Each project's Markdown is saved as `projects/<project_id>.md` in a private
GitHub repository, with one commit for each save that changes it. To set it up:

1. Create a private repository on GitHub and select **Add a README file**, so
   the `main` branch exists.
2. Under **Settings > Developer settings > Personal access tokens > Fine-grained
   tokens**, create a token for that repository only, with **Contents** set to
   **Read and write**.
3. Put the repository's `owner/name` in `GITHUB_REPOSITORY` and the token in
   `GITHUB_TOKEN`.

Without `GITHUB_REPOSITORY`, the server keeps saved Markdown in process memory
instead, and restarting the server clears it.

Django reads `.env` from the repository root. Process environment variables take
precedence over values in that file. Git ignores `.env`; `.env.example` documents
the required configuration.

## Run

Check the configuration, apply migrations, and create an administrator:

```bash
python backend/manage.py check
python backend/manage.py migrate
python backend/manage.py createsuperuser
python backend/manage.py runserver 127.0.0.1:8000
```

Enter an email address, display name, and password when creating the superuser.

- Open <http://127.0.0.1:8000/admin/> and sign in with the administrator's email and password.
- Under **Accounts > Users**, add a user with an email, display name, and password.
- Open the saved user's record to check the stored values.
- Open <http://127.0.0.1:8000/api/v1/health/> for the application health response, `{"status": "ok"}`.

Stop the development server with Ctrl+C.

### Project API

Request and response bodies follow section 4.1 of the Sprint 2 design document.

| Request | Purpose | Responses |
| --- | --- | --- |
| `POST /api/v1/projects` | Create a project for a team | `201`, `401`, `403`, `422` |
| `GET /api/v1/projects/<project_id>` | Open a project with its Markdown and node positions | `200`, `401`, `403`, `404`, `503` |
| `PUT /api/v1/projects/<project_id>/save` | Save Markdown and node positions | `200`, `400`, `401`, `403`, `409`, `503` |

A save sends the `base_revision` it started from. If another save happened
first, the response is `409` and nothing changes.

Opening a project returns Markdown, revision, and node positions from the same
saved state. If GitHub cannot return the previous saved Markdown or commit the
new content, Save returns `503` and preserves the project's revision, content
reference, and node positions. Open returns `503` while GitHub is unavailable.

To try the API with the development server running:

1. In the admin, under **Teams > Teams**, add a team. Under
   **Teams > Team memberships**, add your account to that team. The team's ID is
   the number in its admin page URL.
2. While signed in to the admin, open <http://127.0.0.1:8000/api/v1/projects>
   and post `{"name": "Act 1 Dialogue", "team_id": 1}` with your team's ID. The
   response includes the new `project_id`.
3. Open `http://127.0.0.1:8000/api/v1/projects/<project_id>/save` and send a PUT
   request with this body:

   ```json
   {
     "markdown_source": "# Node_1\nHello!\n",
     "layout_data": {"nodes": [{"id": "Node_1", "position": {"x": 120, "y": 300}}]},
     "base_revision": 1
   }
   ```

4. Open `http://127.0.0.1:8000/api/v1/projects/<project_id>` to see the saved
   Markdown, position, and revision 2. Sending the same PUT request again
   returns `409`.
5. With GitHub configured, the repository has a commit that adds
   `projects/<project_id>.md`.

Without GitHub configured, restarting the server clears saved Markdown, and
opening or saving a project whose Markdown was cleared returns `503`. Project
records and node positions stay in the database.

## Test

```bash
python backend/manage.py test accounts config teams projects
```

The tests cover email authentication, user creation, unique emails regardless of
capitalization, required display names, superuser creation, admin user creation
and retrieval, and the health endpoint, which rejects methods other than GET and
HEAD with `405`.

Django creates a separate test database. Use a development database role with
permission to create the test database.

The `teams` tests cover membership checks (a member, a non-member, and an anonymous user) and the rule that a user can belong to a team only once.

The `projects` tests cover creating, opening, and saving projects, revision
conflicts, team access, malformed layouts, and storage failures. Regression
tests cover consistent snapshots during interleaved saves and unchanged project
data after failures to read the previous saved Markdown. GitHub storage tests
use a simulated GitHub API: commits, reading earlier versions, position-only
saves without a commit, GitHub errors, and a database failure after a commit.
