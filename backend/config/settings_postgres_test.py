"""Local PostgreSQL for checks that SQLite cannot prove, such as row locks between team changes.

From backend/, with a local PostgreSQL server you can create databases on:

    export INTEGRATION_DATABASE_URL=postgresql://user@127.0.0.1:5432/postgres
    python manage.py test teams.test_concurrency --settings=config.settings_postgres_test

Django creates and drops its own test database. Remote databases are refused.
"""

import os
from urllib.parse import urlparse

import environ
from django.core.exceptions import ImproperlyConfigured

_database_url = os.environ.get("INTEGRATION_DATABASE_URL", "")
if urlparse(_database_url).hostname not in ("127.0.0.1", "localhost", "::1"):
    raise ImproperlyConfigured("PostgreSQL checks run only on a local server.")

# Values already in the environment win over the repository's .env file.
os.environ["DATABASE_URL"] = _database_url
os.environ.setdefault("DJANGO_SECRET_KEY", "postgres-tests-only-not-for-deployment")

from .settings_neon import *  # noqa: E402,F401,F403

DATABASES = {"default": environ.Env.db_url_config(_database_url)}
DEBUG = False
CONTENT_STORE = "memory"
GITHUB_REPOSITORY = ""
