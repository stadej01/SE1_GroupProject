"""
Settings for the hosted test environment on Amazon Lightsail.

The container runs behind Lightsail's HTTPS endpoint. Configuration comes from
the container's environment variables, the same names as in .env.
"""

from .settings_neon import *  # noqa: F401,F403
from .settings_neon import BASE_DIR, MIDDLEWARE, env

DEBUG = False

# Lightsail ends HTTPS at its load balancer and forwards plain HTTP.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# WhiteNoise serves the collected static files, including the Vite build.
STATIC_ROOT = BASE_DIR / "staticfiles"
MIDDLEWARE = [
    MIDDLEWARE[0],
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
