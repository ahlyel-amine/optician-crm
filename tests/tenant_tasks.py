"""Celery tasks used only by the tenancy tests.

Kept out of `test_*.py` so pytest does not try to collect them, and out of
`plateforme/` so no production module gains a test-only dependency.
"""

from __future__ import annotations

from config.celery import app
from domaine.magasins.models import Magasin
from plateforme.tenancy.tasks import TenantTask


@app.task(base=TenantTask, name="tests.count_magasins")
def count_magasins(**kwargs):
    """A business task: it must be impossible to run without knowing whose data it reads."""
    return Magasin.objects.count()


@app.task(base=TenantTask, name="tests.always_fails")
def always_fails(**kwargs):
    """Raises from inside the bound tenant scope, to exercise the unwind path."""
    raise RuntimeError("the task failed")
