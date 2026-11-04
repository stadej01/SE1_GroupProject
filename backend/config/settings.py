
"""
Local dialogue-editor settings.

This demo uses SQLite and does not connect to Neon.
The accounts and teams demo uses config.settings_neon.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DJANGO_DEBUG", "1").strip().lower() in (
    "1", "true", "yes", "on"
)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")

if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            "Set DJANGO_SECRET_KEY when DJANGO_DEBUG=0."
        )
    SECRET_KEY = "local-dialogue-demo-only-do-not-use-in-production"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]"
    ).split(",")
    if host.strip()
]

# The editor remains independent of accounts, teams, and Neon.
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "editor",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Local SQLite database for editor drafts.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get(
            "DJANGO_DATABASE_PATH",
            str(BASE_DIR / "db.sqlite3")
        ),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

CSRF_FAILURE_VIEW = "editor.views.csrf_failure"
DATA_UPLOAD_MAX_MEMORY_SIZE = 2_000_000

# Separate browser cookies for the two local Django demos.
SESSION_COOKIE_NAME = "se1_editor_sessionid"
CSRF_COOKIE_NAME = "se1_editor_csrftoken"
