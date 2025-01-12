"""Django settings for pyjams project.

Generated by 'django-admin startproject' using Django 5.1.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.1/ref/settings/
"""

import os
import secrets
from pathlib import Path

import dj_database_url
from django.contrib.messages import constants as messages

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Before using your Heroku app in production, make sure to review Django's deployment checklist:
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# Django requires a unique secret key for each Django app, that is used by several of its
# security features. To simplify initial setup (without hardcoding the secret in the source
# code) we set this to a random value every time the app starts. However, this will mean many
# Django features break whenever an app restarts (for example, sessions will be logged out).
# In your production Heroku apps you should set the `DJANGO_SECRET_KEY` config var explicitly.
# Make sure to use a long unique value, like you would for a password. See:
# https://docs.djangoproject.com/en/5.1/ref/settings/#std-setting-SECRET_KEY
# https://devcenter.heroku.com/articles/config-vars
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    default=secrets.token_urlsafe(nbytes=64),
)

# The `DYNO` env var is set on Heroku CI, but it's not a real Heroku app, so we have to
# also explicitly exclude CI:
# https://devcenter.heroku.com/articles/heroku-ci#immutable-environment-variables
IS_HEROKU_APP = "DYNO" in os.environ and "CI" not in os.environ

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = not IS_HEROKU_APP

# On Heroku, it's safe to use a wildcard for `ALLOWED_HOSTS``, since the Heroku router performs
# validation of the Host header in the incoming HTTP request. On other platforms you may need to
# list the expected hostnames explicitly in production to prevent HTTP Host header attacks. See:
# https://docs.djangoproject.com/en/5.1/ref/settings/#std-setting-ALLOWED_HOSTS
ALLOWED_HOSTS = ["*"] if IS_HEROKU_APP else ["localhost", "127.0.0.1", "[::1]", "0.0.0.0", "[::]", "*"]

# Security Settings
if IS_HEROKU_APP:
    # SSL and Security Headers
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    # Cookie Settings
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # HSTS Settings
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Additional Security Headers
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

    # CSRF Trusted Origins
    CSRF_TRUSTED_ORIGINS = [
        "https://pyjams.sansterbioanalytics.com",
        "https://pyjams-app-9cff897c521d.herokuapp.com",
        "https://www.sansterbioanalytics.com",
    ]
# Get port from environment variable or default to 8000
PORT = int(os.environ.get("PORT", 5006))

# Application definition

# Several optional Django features that are present in the default `startproject` template have
# been disabled since they are not used by this example app. To use them, uncomment the relevant
# entries in `INSTALLED_APPS`, `MIDDLEWARE`, `TEMPLATES` and `urls.py`. See:
# https://docs.djangoproject.com/en/5.1/ref/contrib/admin/
# https://docs.djangoproject.com/en/5.1/topics/auth/
# https://docs.djangoproject.com/en/5.1/ref/contrib/contenttypes/
# https://docs.djangoproject.com/en/5.1/topics/http/sessions/
# https://docs.djangoproject.com/en/5.1/ref/contrib/messages/
INSTALLED_APPS = [
    "whitenoise.runserver_nostatic",  # Must be before django.contrib.staticfiles
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "pyjams.apps.PyjamsConfig",  # Use the AppConfig
]
# Django doesn't support serving static assets in a production-ready way, so we use the
# excellent WhiteNoise package to do so instead. The WhiteNoise middleware must be listed
# after Django's `SecurityMiddleware` so that security redirects are still performed.
# See: https://whitenoise.readthedocs.io

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "pyjams.middleware.SpotifySessionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "pyjams.utils.spotify.SpotifyAuthenticationBackend",
]

# Custom User Model
AUTH_USER_MODEL = "pyjams.User"

ROOT_URLCONF = "pyjams.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "pyjams" / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.static",
            ],
        },
    },
]

WSGI_APPLICATION = "pyjams.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

if IS_HEROKU_APP:
    # In production on Heroku the database configuration is derived from the `DATABASE_URL`
    # environment variable by the dj-database-url package. `DATABASE_URL` will be set
    # automatically by Heroku when a database addon is attached to your Heroku app. See:
    # https://devcenter.heroku.com/articles/provisioning-heroku-postgres#application-config-vars
    # https://github.com/jazzband/dj-database-url
    DATABASES = {
        "default": dj_database_url.config(
            env="DATABASE_URL",
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True,
        ),
    }
else:
    # When running locally in development or in CI, a sqlite database file will be used instead
    # to simplify initial setup. Longer term it's recommended to use Postgres locally too.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": f"{BASE_DIR}/db.sqlite3",
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
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


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "pyjams" / "static"]

# Ensure this directory exists for development
if not IS_HEROKU_APP:
    STATIC_DEV_DIR = BASE_DIR / "static"
    STATIC_DEV_DIR.mkdir(exist_ok=True)
    STATICFILES_DIRS = [STATIC_DEV_DIR]

# WhiteNoise Configuration
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
WHITENOISE_MANIFEST_STRICT = False
WHITENOISE_USE_FINDERS = True

# Enable WhiteNoise's GZip and Brotli compression of static assets
WHITENOISE_COMPRESSION_ENABLED = True

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Authentication settings
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# Messages settings
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

# Message tags to match Bootstrap classes


MESSAGE_TAGS = {
    messages.DEBUG: "alert-info",
    messages.INFO: "alert-info",
    messages.SUCCESS: "alert-success",
    messages.WARNING: "alert-warning",
    messages.ERROR: "alert-danger",
}


# Spotify Settings
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
if IS_HEROKU_APP:
    SPOTIFY_REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "https://pyjams.sansterbioanalytics.com/callback/")
else:
    SPOTIFY_REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:5006/callback/")
if not all([SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET]):
    raise ValueError("Missing SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET environment variables")
SPOTIFY_SCOPE = "playlist-modify-public playlist-modify-private user-read-private user-read-email"

# Session Settings - Optimized for OAuth flows
# Session Settings
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_SERIALIZER = "django.contrib.sessions.serializers.JSONSerializer"
SESSION_COOKIE_NAME = "pyjams_sessionid"
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_SAVE_EVERY_REQUEST = True  # Important for OAuth flow

# Enable signed cookie-based sessions as fallback
SESSION_FALLBACK = True
SESSION_COOKIE_DOMAIN = None  # Allow all subdomains

# CSRF Settings
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5006",
    "http://127.0.0.1:5006",
]
if IS_HEROKU_APP:
    CSRF_TRUSTED_ORIGINS.extend(
        [
            # Add your production domains here
            "https://*.herokuapp.com",
            "https://*.sansterbioanalytics.com",
        ]
    )
# Logging Configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
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
        "handlers": ["console"],
        "level": "INFO",
    },
}

# Control trailing slashes
APPEND_SLASH = True  # Keep this if you want trailing slashes enforced

# Set primary domain
PRIMARY_DOMAIN = "pyjams.sansterbioanalytics.com"
