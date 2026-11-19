"""Real PostgreSQL and a real test branch, for checks that SQLite cannot prove.

Run through tests/integration/. It refuses a remote database and a main branch,
so these checks cannot reach an environment that holds real data.
"""

import os
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

_database_url = os.environ["INTEGRATION_DATABASE_URL"]
_branch = os.environ["INTEGRATION_GITHUB_BRANCH"]
if urlparse(_database_url).hostname not in ("127.0.0.1", "localhost", "::1"):
    raise ImproperlyConfigured("Integration checks run only on a local PostgreSQL.")
if _branch in ("main", "master"):
    raise ImproperlyConfigured("Integration checks need a separate test branch.")

# Values already in the environment win over the repository's .env file.
os.environ["DATABASE_URL"] = _database_url
os.environ["GITHUB_REPOSITORY"] = os.environ["INTEGRATION_GITHUB_REPOSITORY"]
os.environ["GITHUB_TOKEN"] = os.environ["INTEGRATION_GITHUB_TOKEN"]
os.environ["GITHUB_BRANCH"] = _branch
os.environ["DJANGO_SECRET_KEY"] = "integration-checks-only-not-for-deployment"
os.environ["DJANGO_DEBUG"] = "True"

from .settings_neon import *  # noqa: E402,F401,F403
