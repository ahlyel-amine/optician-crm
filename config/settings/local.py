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

# Development tolerance only, for the SPA served by Vite on a different port than
# Django. This sits **behind** the same-origin proxy, it does not replace it: with
# `changeOrigin: false` in `web/vite.config.ts` the browser's `Origin` already matches
# the host Django reconstructs, and this list is never read. It covers calling
# `127.0.0.1:8010` directly, and a machine where Vite's port differs.
# **Never in `base.py`.** In production, trusting `localhost` hands a trusted origin to
# anyone who controls a local name resolution.
CSRF_TRUSTED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
