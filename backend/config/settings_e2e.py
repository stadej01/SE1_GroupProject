"""Local browser checks with SQLite and memory storage; never Neon or GitHub."""

import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("DJANGO_SECRET_KEY", "isolated-browser-only-not-for-deployment")

from .settings_neon import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ["DJANGO_DATABASE_PATH"],
    }
}
CONTENT_STORE = "memory"
GITHUB_REPOSITORY = ""
# Simple passwords are allowed only in this isolated local environment.
AUTH_PASSWORD_VALIDATORS = []
DEBUG = True
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
