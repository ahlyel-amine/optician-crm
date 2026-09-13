"""WSGI entrypoint.

WSGI, not ASGI: the tenancy context is a ContextVar bound per request on a worker
thread, and gunicorn's sync/thread workers give us a request-per-thread model that the
middleware's assert-unset-on-entry guard can reason about.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_wsgi_application()
