"""Local development settings."""

from .base import *  # noqa: F403
from .base import REST_FRAMEWORK

DEBUG = True
ALLOWED_HOSTS = ["*"]

# The browsable API, and **only** here. Its `<select>` dropdowns render related objects'
# `__str__`, so they enumerate rows the caller may not be entitled to see (threat
# A-03-06). Useful at a developer's desk, a disclosure in production — hence one module,
# asserted by `test_perm06_le_renderer_html_est_absent_hors_developpement`.
# A fresh dict, never `.append()`: `REST_FRAMEWORK` is imported by reference from `base`,
# and mutating the list in place would also change it for anything else holding it.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

# Served over plain HTTP locally, so secure-only cookies would never be sent back.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
