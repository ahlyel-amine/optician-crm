"""Local development settings."""

from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Served over plain HTTP locally, so secure-only cookies would never be sent back.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
