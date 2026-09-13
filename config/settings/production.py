"""Production settings."""

from .base import *  # noqa: F403
from .base import DATABASES, env

DEBUG = False
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

# TLS to PgBouncer. Note this is an OPTIONS *connection parameter*, not a pool setting —
# the OPTIONS dict still carries no connection-pool key and no prepare_threshold.
DATABASES["default"]["OPTIONS"]["sslmode"] = "require"

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
