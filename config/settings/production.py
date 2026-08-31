from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False

MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405

if SECRET_KEY == "unsafe-development-key":  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be configured in production.")

if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":  # noqa: F405
    raise ImproperlyConfigured("Production requires a PostgreSQL DATABASE_URL.")

CLOUDINARY_URL = env("CLOUDINARY_URL")  # noqa: F405
STORAGES["default"] = {"BACKEND": "apps.core.storage.CloudinaryMediaStorage"}  # noqa: F405

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)  # noqa: F405
SECURE_HSTS_SECONDS = env.int("DJANGO_HSTS_SECONDS", default=31_536_000)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if BYPASS_EMAIL_VERIFICATION:  # noqa: F405
    EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("EMAIL_HOST")  # noqa: F405
    EMAIL_PORT = env.int("EMAIL_PORT", default=587)  # noqa: F405
    EMAIL_HOST_USER = env("EMAIL_HOST_USER")  # noqa: F405
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")  # noqa: F405
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)  # noqa: F405
    DEFAULT_FROM_EMAIL = env(  # noqa: F405
        "DEFAULT_FROM_EMAIL",
        default="ClimbingSide <no-reply@example.com>",
    )
