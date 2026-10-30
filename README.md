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

## Test

```bash
python backend/manage.py test accounts config
```

The tests cover email authentication, user creation, unique emails, superuser
creation, admin user creation and retrieval, and the health endpoint.

Django creates a separate test database. Use a development database role with
permission to create the test database.
