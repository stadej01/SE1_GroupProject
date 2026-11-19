"""SQLite-only test settings for accounts, teams, and projects; NEVER connects to Neon.

Usage: python manage.py test accounts teams config projects --settings=config.settings_auth_test
"""
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("DJANGO_SECRET_KEY", "isolated-test-only-not-for-deployment")
from .settings_neon import *  # noqa: F401,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
DEBUG = False
CONTENT_STORE = "memory"
GITHUB_REPOSITORY = ""
