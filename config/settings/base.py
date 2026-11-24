"""
Base Django settings for Restaurant Ordering & Delivery Management System.
Owned and coordinated by Developer 1 (Backend Infrastructure, Authentication & Database).
"""
import os
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables from .env if present
load_dotenv(BASE_DIR / ".env")


def get_env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def get_env_list(key: str, default: list[str] | None = None) -> list[str]:
    val = os.environ.get(key)
    if not val:
        return default or []
    return [item.strip() for item in val.split(",") if item.strip()]


def parse_database_url(url: str) -> dict:
    """
    Parse a PostgreSQL or SQLite DATABASE_URL into a Django DATABASES dictionary.
    Example: postgres://user:pass@localhost:5432/restaurant
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()

    if scheme in ("postgres", "postgresql", "pgsql"):
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed.path.lstrip("/")),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "localhost",
            "PORT": str(parsed.port or 5432),
            "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "60")),
        }
    if scheme == "sqlite":
        db_path = unquote(parsed.path.lstrip("/"))
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / db_path) if db_path else str(BASE_DIR / "db.sqlite3"),
        }
    raise ValueError(f"Unsupported DATABASE_URL scheme: {scheme}")


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev1-foundation-key-change-in-production",
)

DEBUG = get_env_bool("DJANGO_DEBUG", False)

ALLOWED_HOSTS = get_env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1", "[::1]"])

# -----------------------------------------------------------------------------
# Application definition
# -----------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "channels",
    "rest_framework",
]

# Developer 1 core apps + Shared repository app stubs for Developers 3, 4, 5
LOCAL_APPS = [
    "apps.core.apps.CoreConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.menu.apps.MenuConfig",
    "apps.orders.apps.OrdersConfig",
    "apps.payments.apps.PaymentsConfig",
    "apps.delivery.apps.DeliveryConfig",
    "apps.notifications.apps.NotificationsConfig",
    "apps.promotions.apps.PromotionsConfig",
    "apps.reviews.apps.ReviewsConfig",
    "apps.dashboard.apps.DashboardConfig",
]

INSTALLED_APPS = ["daphne"] + DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# Custom User Model (CRITICAL: Must be defined before first migration)
AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.restaurant_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# -----------------------------------------------------------------------------
# Password validation & security
# -----------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# -----------------------------------------------------------------------------
# Internationalization & Localization (Confirmed: Ghana & GHS)
# -----------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Accra"
USE_I18N = True
USE_TZ = True

DEFAULT_COUNTRY = os.environ.get("DEFAULT_COUNTRY", "Ghana")
DEFAULT_CURRENCY = os.environ.get("DEFAULT_CURRENCY", "GHS")
CURRENCY_SYMBOL = os.environ.get("CURRENCY_SYMBOL", "GH₵")

# -----------------------------------------------------------------------------
# Restaurant & Delivery Fee Defaults (Used by Core, Orders & Dashboard)
# -----------------------------------------------------------------------------
RESTAURANT_NAME = os.environ.get("RESTAURANT_NAME", "Cho Restaurant")
RESTAURANT_LATITUDE = Decimal(os.environ.get("RESTAURANT_LATITUDE", "5.603717"))
RESTAURANT_LONGITUDE = Decimal(os.environ.get("RESTAURANT_LONGITUDE", "-0.186964"))

DELIVERY_FEE_MODE = os.environ.get("DELIVERY_FEE_MODE", "DISTANCE")
FLAT_DELIVERY_FEE = Decimal(os.environ.get("FLAT_DELIVERY_FEE", "15.00"))
BASE_DELIVERY_FEE = Decimal(os.environ.get("BASE_DELIVERY_FEE", "10.00"))
BASE_DISTANCE_KM = Decimal(os.environ.get("BASE_DISTANCE_KM", "3.00"))
PER_KM_FEE = Decimal(os.environ.get("PER_KM_FEE", "3.00"))
MAX_DELIVERY_RADIUS_KM = Decimal(os.environ.get("MAX_DELIVERY_RADIUS_KM", "15.00"))
FREE_DELIVERY_THRESHOLD = Decimal(os.environ.get("FREE_DELIVERY_THRESHOLD", "200.00"))

# -----------------------------------------------------------------------------
# Static and Media Files (Cloudinary + Local Storage)
# -----------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL", "").strip()

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# -----------------------------------------------------------------------------
# Django REST Framework Configuration
# -----------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# -----------------------------------------------------------------------------
# Redis, Celery & Channels Configuration
# -----------------------------------------------------------------------------
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = get_env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = get_env_bool("CELERY_TASK_EAGER_PROPAGATES", False)
CELERY_BEAT_SCHEDULE = {
    "prune-rider-locations-hourly": {
        "task": "delivery.prune_rider_locations",
        "schedule": 3600.0,
    },
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
            "capacity": 100,
            "expiry": 10,
        },
    }
}

GPS_MIN_INTERVAL_SECONDS = int(os.environ.get("GPS_MIN_INTERVAL_SECONDS", "2"))
LOCATION_HISTORY_RETENTION_MINUTES = int(
    os.environ.get("LOCATION_HISTORY_RETENTION_MINUTES", "60")
)
RIDER_LOCATION_STALE_MINUTES = int(os.environ.get("RIDER_LOCATION_STALE_MINUTES", "15"))
NOTIFICATION_SMS_GATEWAY_URL = os.environ.get("NOTIFICATION_SMS_GATEWAY_URL", "")

# -----------------------------------------------------------------------------
# Paystack & Email Configuration
# -----------------------------------------------------------------------------
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
PAYSTACK_PUBLIC_KEY = os.environ.get("PAYSTACK_PUBLIC_KEY", "")

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@chorestaurant.com")
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)

# Default primary key field type (Matches BIGSERIAL in schema.sql)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
