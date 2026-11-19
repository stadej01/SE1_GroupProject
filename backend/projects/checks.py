"""Configuration the full app needs before it starts."""

import re

from django.conf import settings
from django.core.checks import Error, register
from django.core.exceptions import ImproperlyConfigured

SECRET_KEY_PLACEHOLDER = "replace-with-a-generated-secret-key"
SETUP_HINT = (
    "Complete the configuration steps in README.md. "
    "With a shared .env, check the file you received."
)


def _secret_key():
    try:
        return settings.SECRET_KEY
    except ImproperlyConfigured:  # Django refuses to return an empty key.
        return ""


@register()
def required_configuration(app_configs, **kwargs):
    """Report settings by name only, so a value never reaches the output."""
    if settings.CONTENT_STORE == "memory":
        return []

    problems = []
    if _secret_key() in ("", SECRET_KEY_PLACEHOLDER):
        problems.append("Generate DJANGO_SECRET_KEY")
    if settings.DATABASES["default"]["ENGINE"] == "django.db.backends.dummy":
        problems.append("Set DATABASE_URL")
    if not settings.GITHUB_REPOSITORY:
        problems.append("Set GITHUB_REPOSITORY")
    elif not re.fullmatch(r"[\w.-]+/[\w.-]+", settings.GITHUB_REPOSITORY):
        problems.append("Write GITHUB_REPOSITORY as owner/name")
    if not settings.GITHUB_TOKEN:
        problems.append("Set GITHUB_TOKEN")
    if not settings.GITHUB_BRANCH:
        problems.append("Set GITHUB_BRANCH")

    return [
        Error(f"{problem} in .env.", hint=SETUP_HINT, id="projects.E001")
        for problem in problems
    ]
