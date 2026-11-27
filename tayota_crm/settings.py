import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent


def env_flag(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


DEBUG = env_flag("DJANGO_DEBUG", True)
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-local-development-only-do-not-deploy",
)
if not DEBUG and "DJANGO_SECRET_KEY" not in os.environ:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be configured in production.")
if not DEBUG and not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY cannot be empty in production.")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1"
    ).split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "crm.apps.CrmConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
if not DEBUG:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "tayota_crm.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "tayota_crm.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    DATABASES["default"] = dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        ssl_require=not DEBUG,
    )
    if not DEBUG and DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
        raise ImproperlyConfigured("Production DATABASE_URL must use PostgreSQL.")
elif not DEBUG:
    raise ImproperlyConfigured("DATABASE_URL must point to the production database.")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
WHITENOISE_USE_FINDERS = DEBUG
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Generated documents (invoice PDFs) go to a private S3 bucket when one is
# configured. On AWS the EC2 instance role supplies the credentials, so no
# access keys live in settings or environment properties. Files are always
# streamed through the app after a permission check, never linked directly.
DOCUMENTS_BUCKET = os.environ.get("DJANGO_S3_DOCUMENTS_BUCKET", "").strip()
if DOCUMENTS_BUCKET:
    DEFAULT_STORAGE = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": DOCUMENTS_BUCKET,
            "region_name": os.environ.get("AWS_REGION", "us-east-1"),
            "default_acl": None,
            "querystring_auth": True,
            "file_overwrite": False,
            "object_parameters": {"ServerSideEncryption": "AES256"},
        },
    }
else:
    DEFAULT_STORAGE = {"BACKEND": "django.core.files.storage.FileSystemStorage"}

STORAGES = {
    "default": DEFAULT_STORAGE,
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        )
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_flag("DJANGO_SECURE_SSL_REDIRECT", not DEBUG)
SECURE_REDIRECT_EXEMPT = [r"^health/$"]
# Cookie and HSTS hardening tracks whether the site is actually served over
# HTTPS. Keep the secure defaults; set DJANGO_SERVE_HTTPS=False only for an
# environment intentionally served over plain HTTP (for example a
# single-instance Elastic Beanstalk environment with no TLS certificate),
# because secure cookies are never sent over HTTP and would break sign-in.
SERVE_HTTPS = env_flag("DJANGO_SERVE_HTTPS", not DEBUG)
SESSION_COOKIE_SECURE = SERVE_HTTPS
CSRF_COOKIE_SECURE = SERVE_HTTPS
SECURE_HSTS_SECONDS = 31536000 if SERVE_HTTPS else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = SERVE_HTTPS
