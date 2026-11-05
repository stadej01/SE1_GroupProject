
"""
Django settings for the shared accounts, projects, and editor service.
"""

from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

# Read environment variables from the project .env file.
env = environ.Env()
environ.Env.read_env(BASE_DIR.parent / ".env")

# Missing values are reported together by projects.checks when the app starts.
SECRET_KEY = env("DJANGO_SECRET_KEY", default="")
DEBUG = env.bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", "[::1]"]
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "accounts.apps.AccountsConfig",
    "teams.apps.TeamsConfig",
    "projects.apps.ProjectsConfig",
    "editor",
]

# Draft belongs to the old SQLite demo, not the shared project database.
MIGRATION_MODULES = {"editor": None}

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "accounts:login"
CSRF_FAILURE_VIEW = "config.views.csrf_failure"

JWT_LIFETIME_SECONDS = 60 * 60

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.JWTAuthentication",
        "accounts.authentication.SessionLoginAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls_neon"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Neon is only used by this settings configuration.
_database_url = env("DATABASE_URL", default="")
DATABASES = {
    "default": (
        env.db_url_config(_database_url)
        if _database_url
        else {"ENGINE": "django.db.backends.dummy"}
    ),
}

# Each project's Markdown is a file in a private GitHub repository (owner/name).
# Only test settings may replace it with memory storage.
CONTENT_STORE = "github"
GITHUB_REPOSITORY = env("GITHUB_REPOSITORY", default="")
GITHUB_TOKEN = env("GITHUB_TOKEN", default="")
GITHUB_BRANCH = env("GITHUB_BRANCH", default="main")

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# Separate cookies for the two demos.
SESSION_COOKIE_NAME = "se1_neon_sessionid"
CSRF_COOKIE_NAME = "se1_neon_csrftoken"
