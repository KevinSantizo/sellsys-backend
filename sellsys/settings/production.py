import os

from .base import *


DEBUG = False


if not SECRET_KEY:
    raise RuntimeError(
        "DJANGO_SECRET_KEY es obligatoria "
        "en producción."
    )


if not os.getenv(
    "JWT_SIGNING_KEY"
):
    raise RuntimeError(
        "JWT_SIGNING_KEY es obligatoria "
        "en producción."
    )


if not ALLOWED_HOSTS:
    raise RuntimeError(
        "DJANGO_ALLOWED_HOSTS es obligatorio "
        "en producción."
    )

REQUIRED_DATABASE_ENV_VARS = (
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
)

missing_database_vars = [
    variable
    for variable in REQUIRED_DATABASE_ENV_VARS
    if not os.getenv(variable)
]

if missing_database_vars:
    raise RuntimeError(
        "Faltan variables de entorno "
        "obligatorias para PostgreSQL: "
        + ", ".join(missing_database_vars)
    )



DATABASES = {
    "default": {
        "ENGINE": (
            "django.db.backends.postgresql"
        ),
        "NAME": os.getenv(
            "POSTGRES_DB"
        ),
        "USER": os.getenv(
            "POSTGRES_USER"
        ),
        "PASSWORD": os.getenv(
            "POSTGRES_PASSWORD"
        ),
        "HOST": os.getenv(
            "POSTGRES_HOST"
        ),
        "PORT": os.getenv(
            "POSTGRES_PORT",
            "6543",
        ),

        # Vercel es serverless.
        "CONN_MAX_AGE": 0,

        "CONN_HEALTH_CHECKS": True,

        # Recomendado con transaction pooling.
        "DISABLE_SERVER_SIDE_CURSORS": True,

        "OPTIONS": {
            "sslmode": os.getenv(
                "POSTGRES_SSLMODE",
                "require",
            ),
            "prepare_threshold": None,
        },
    }
}


SECURE_SSL_REDIRECT = True

SESSION_COOKIE_SECURE = True

SESSION_COOKIE_HTTPONLY = True

CSRF_COOKIE_SECURE = True

CSRF_COOKIE_HTTPONLY = True

SECURE_CONTENT_TYPE_NOSNIFF = True

X_FRAME_OPTIONS = "DENY"

SECURE_REFERRER_POLICY = (
    "strict-origin-when-cross-origin"
)


SECURE_HSTS_SECONDS = 3600

SECURE_HSTS_INCLUDE_SUBDOMAINS = False

SECURE_HSTS_PRELOAD = False


SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)


ENABLE_API_DOCS = False