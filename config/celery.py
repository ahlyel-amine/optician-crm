"""The Celery application.

Every business task inherits `plateforme.tenancy.tasks.TenantTask`, which refuses to run
without a routable `client_id`. Control-plane tasks (backup fan-out, `migrate_all`,
orphan reaping) are ordinary tasks that operate on `default` and iterate clients
themselves.

Defining the app opens no broker connection — that happens on the first publish or when a
worker starts — so importing this module is safe from `manage.py`, from tests and from
the WSGI application.
"""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("optique")

# Settings are read from Django with the CELERY_ prefix, so the broker URL, the result
# backend, the timezone and the beat scheduler all live in one place.
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
