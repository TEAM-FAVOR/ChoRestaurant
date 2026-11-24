"""
Development settings for Restaurant Ordering & Delivery Management System.
Uses PostgreSQL when DATABASE_URL is configured, with automatic SQLite fallback for local development.
Uses local MEDIA_ROOT storage by default unless CLOUDINARY_URL is explicitly enabled with USE_CLOUDINARY_IN_DEV=True.
"""
import os

from .base import *  # noqa: F401, F403

DEBUG = get_env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = get_env_list(
    "DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1", "[::1]", "testserver"]
)

# Database: PostgreSQL via DATABASE_URL if provided, else SQLite for immediate local dev/testing
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL:
    DATABASES = {
        "default": parse_database_url(DATABASE_URL),
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Media storage: Local FileSystemStorage in dev (or Cloudinary if explicitly requested)
if CLOUDINARY_URL and get_env_bool("USE_CLOUDINARY_IN_DEV", False):
    INSTALLED_APPS = [*INSTALLED_APPS, "cloudinary_storage", "cloudinary"]
    STORAGES["default"] = {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    }

# Redis is the default channel layer in development; opt into in-memory for isolated tests.
if get_env_bool("USE_IN_MEMORY_CHANNEL_LAYER", False):
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }

# Email: Console backend for development
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
