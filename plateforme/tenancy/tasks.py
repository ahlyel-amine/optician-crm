"""`TenantTask` — the Celery half of the tenant context lifecycle.

**Never pass a model instance to a task.** Pass `client_id` plus primary keys, and let
the task re-bind and re-load. A pickled instance carries a stale `_state.db`, is bound to
a schema version that may have moved by the time the task runs, and defeats the whole
point of re-establishing context on the worker.

Why a custom `Task.__call__` rather than the `task_prerun` / `task_postrun` signal pair:
Celery's tracer honours a custom `__call__`
(`fun = task if task_has_custom(task, '__call__') else task.run`), and unlike a signal
this can enforce fail-closed on the *argument* side — a signal receiver cannot refuse a
task for having no `client_id`.

Belt and braces: the `task_prerun` receiver below refuses a process that arrives already
bound. The prefork worker reuses processes, so the same class of leak exists there as on a
reused thread. `TenancyConfig.ready()` imports this module so the receiver is connected at
startup, deterministically, rather than whenever task autodiscovery happens to reach it.
"""

from __future__ import annotations

import logging

import celery
from celery.signals import task_prerun
from django.conf import settings

from plateforme.tenancy.context import (
    NoTenantBound,
    TenantContextLeak,
    clear,
    is_bound,
    tenant_context,
)
from plateforme.tenancy.registry import alias_for, register_client_database

logger = logging.getLogger("plateforme.tenancy")


class TenantTask(celery.Task):
    """Base for every business task. Refuses to run without a routable client."""

    abstract = True

    def __call__(self, *args, **kwargs):
        from plateforme.control_plane.models import Client

        client_id = kwargs.get("client_id")
        if client_id is None:
            raise NoTenantBound(
                f"{self.name} was invoked without a client_id — refusing. Business tasks "
                "must be told whose data they are touching; never pass a model instance."
            )

        # `.get(..., status=ACTIVE)` rather than a filter plus a check: a non-ACTIVE
        # client must raise, not be silently skipped. A half-provisioned, failed or
        # suspended client is not routable (threat T-02-18).
        client = Client.objects.using("default").get(pk=client_id, status=Client.ACTIVE)
        register_client_database(**client.connection_params())

        with tenant_context(alias_for(client.pk)):
            return super().__call__(*args, **kwargs)


@task_prerun.connect
def refuse_a_worker_that_arrives_already_bound(sender=None, **kwargs):
    """The prefork equivalent of the middleware's entry guard.

    Worker *processes* are reused just as worker threads are, so a task that failed to
    unwind its scope would hand its client to the next task on that process.
    """
    if is_bound():
        logger.critical(
            "tenant context leaked onto celery worker",
            extra={"task": getattr(sender, "name", "?")},
        )
        clear()
        if settings.TENANCY_STRICT:
            raise TenantContextLeak(
                "A tenant context survived a previous task on this worker process."
            )
