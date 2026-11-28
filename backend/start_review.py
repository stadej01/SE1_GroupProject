"""Start a disposable local review of the checked-out branch."""

import os
import secrets

import django
from django.conf import settings
from django.core.management import call_command


def main():
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings_e2e"
    os.environ["DJANGO_ALLOWED_HOSTS"] = "localhost,127.0.0.1"
    os.environ["DJANGO_SECRET_KEY"] = secrets.token_urlsafe(48)
    # Request threads share this SQLite database for the lifetime of this process.
    os.environ["DJANGO_DATABASE_PATH"] = "file:pr-review?mode=memory&cache=shared"
    # Browsers share localhost cookies across ports, including the Neon demo.
    settings.SESSION_COOKIE_NAME = "se1_review_sessionid"
    settings.CSRF_COOKIE_NAME = "se1_review_csrftoken"
    settings.JWT_COOKIE_NAME = "se1_review_token"
    django.setup()
    call_command("migrate", interactive=False)
    print("Local PR review: accounts and projects last until you stop this server.", flush=True)
    call_command("runserver", "127.0.0.1:8767", use_reloader=False, skip_checks=False)


if __name__ == "__main__":
    main()
