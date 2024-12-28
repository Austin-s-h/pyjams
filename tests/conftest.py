import django
from django.conf import settings


def pytest_configure() -> None:
    settings.configure(
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
        ],
        SECRET_KEY="test-key",
        SPOTIFY_CLIENT_ID="test-client-id",
        SPOTIFY_CLIENT_SECRET="test-client-secret",
        SPOTIFY_REDIRECT_URI="http://localhost:8000/callback",
        DJANGO_SETTINGS_MODULE="pyjams.settings",
    )
    django.setup()
