import os

from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")


def env_list(name, default=""):
    value = os.getenv(name, default)

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "",
)


DEBUG = False

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS"
)


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "corsheaders",
    "django_filters",
    "drf_spectacular",

    # SellSys
    "common",
    "accounts",
    "companies.apps.CompaniesConfig",
    "branches",
    "billing",
    "catalog",
    "sales",
    "inventory",
    "purchases",
    "expenses",
    "cash",
    "reports",
    "rest_framework_simplejwt.token_blacklist",
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "sellsys.urls"


TEMPLATES = [
    {
        "BACKEND": (
            "django.template.backends.django."
            "DjangoTemplates"
        ),
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                (
                    "django.template.context_processors."
                    "request"
                ),
                (
                    "django.contrib.auth.context_processors."
                    "auth"
                ),
                (
                    "django.contrib.messages.context_processors."
                    "messages"
                ),
            ],
        },
    },
]


WSGI_APPLICATION = "sellsys.wsgi.application"


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


LANGUAGE_CODE = "es-gt"

TIME_ZONE = "America/Guatemala"

USE_I18N = True

USE_TZ = True


STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"


AUTH_USER_MODEL = "accounts.User"


CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS"
)

CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS"
)


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        (
            "rest_framework_simplejwt."
            "authentication.JWTAuthentication"
        ),
    ],

    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],

    "DEFAULT_FILTER_BACKENDS": [
        (
            "django_filters.rest_framework."
            "DjangoFilterBackend"
        ),
    ],

    "DEFAULT_SCHEMA_CLASS": (
        "drf_spectacular.openapi.AutoSchema"
    ),

    "EXCEPTION_HANDLER": (
        "common.exceptions."
        "custom_exception_handler"
    ),
}

JWT_SIGNING_KEY = os.getenv(
    "JWT_SIGNING_KEY",
    SECRET_KEY,
)

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(
            os.getenv(
                "JWT_ACCESS_MINUTES",
                "480",
            )
        )
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(
            os.getenv(
                "JWT_REFRESH_DAYS",
                "7",
            )
        )
    ),
    "AUTH_HEADER_TYPES": (
        "Bearer",
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,

    "SIGNING_KEY": JWT_SIGNING_KEY,
}



DEFAULT_AUTO_FIELD = (
    "django.db.models.BigAutoField"
)

STORAGES = {
    "default": {
        "BACKEND": (
            "django.core.files.storage."
            "FileSystemStorage"
        ),
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage."
            "CompressedManifestStaticFilesStorage"
        ),
    },
}

LOG_LEVEL = os.getenv(
    "DJANGO_LOG_LEVEL",
    "INFO",
)


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "verbose": {
            "format": (
                "{levelname} "
                "{asctime} "
                "{name} "
                "{message}"
            ),
            "style": "{",
        },
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },

    "root": {
        "handlers": [
            "console",
        ],
        "level": LOG_LEVEL,
    },

    "loggers": {
        "django": {
            "handlers": [
                "console",
            ],
            "level": LOG_LEVEL,
            "propagate": False,
        },

        "django.request": {
            "handlers": [
                "console",
            ],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "SellSys API",
    "DESCRIPTION": (
        "API de gestión comercial "
        "multiempresa de SellSys"
    ),
    "VERSION": "1.0.0",

    "ENUM_NAME_OVERRIDES": {
        "SaleStatusEnum": (
            "sales.models.SaleStatus"
        ),
    },
}


ENABLE_API_DOCS = False