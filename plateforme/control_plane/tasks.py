"""Control-plane Celery tasks. One periodic task that fans out `client_id`s.

These are **not** `TenantTask` subclasses, and that is deliberate rather than an omission:
`pg_dump` is a subprocess, not an ORM query, so there is nothing to bind. What they do
inherit is the discipline — **primitives only, never a model instance** — for the reasons
in `plateforme/tenancy/tasks.py`: a pickled instance carries a stale `_state.db` and a
schema version that may have moved by the time a worker picks the task up.

The shape is the one `02-RESEARCH.md` "Don't Hand-Roll" prescribes: one periodic task in
the control plane that enqueues one `client_id` per ACTIVE client, registered through
`django-celery-beat` so the schedule is operator-visible and editable. Not a per-tenant
custom scheduler.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger("plateforme.control_plane")


@shared_task(name="control_plane.backup_client")
def backup_client_task(client_id: int = None):
    """Dump one client. Refuses a missing `client_id` rather than quietly doing nothing.

    A backup task that no-ops when handed no argument is the worst possible failure mode:
    `BackupRun` shows no row, and nobody goes looking for an absence.
    """
    if client_id is None:
        raise ValueError(
            "backup_client_task was invoked without a client_id — refusing. Backup tasks "
            "must be told whose database they are dumping; never pass a model instance."
        )

    from plateforme.control_plane import backup

    run = backup.backup_client(client_id)
    return run.pk


@shared_task(name="control_plane.backup_all_active_clients")
def backup_all_active_clients(enqueue: bool = True) -> list[int]:
    """The Beat fan-out. Enqueues one `backup_client_task` per **ACTIVE** client.

    Only ACTIVE, for the same reason the router and `migrate_all` see only ACTIVE: a
    half-provisioned client's database may not exist, and a failed dump against it would
    be noise that trains the operator to ignore backup failures.

    Returns the primary keys it covered, so a caller (and the test) can assert coverage
    without reaching into the broker.
    """
    from plateforme.control_plane.models import Client

    pks = list(
        Client.objects.using("default")
        .filter(status=Client.ACTIVE)
        .order_by("pk")
        .values_list("pk", flat=True)
    )

    if enqueue:
        for pk in pks:
            # kwargs only, and only a primitive — a bare integer primary key, never the
            # model instance it identifies. An acceptance grep enforces the absence of
            # the instance-passing form.
            backup_client_task.apply_async(kwargs={"client_id": pk})

    logger.info("backup fan-out covering %d active client(s)", len(pks))
    return pks


@shared_task(name="control_plane.clear_expired_sessions")
def clear_expired_sessions() -> None:
    """Delete expired rows from `django_session`. Scheduled nightly by Beat.

    Control-plane, not per-tenant, and that is the point: `django_session` is **one**
    table on the shared control-plane database, written to by every optician in the
    fleet (CLAUDE.md #11, A-03-12). Nothing purges it on its own, and `SESSION_COOKIE_AGE`
    is thirty days, so without this task the table grows without bound — a denial of
    service by growth, and a forensic liability for rows nobody needs (threat T-03-52).

    **What a session row contains, stated rather than assumed:** a session key, an expiry
    date, and an encoded payload holding a user primary key, the auth backend path and a
    password hash fragment. No client business data, no health data — which is why this is
    a hygiene task and not a law-09-08 obligation. It is also why deleting expired rows
    destroys no record art. 211 CGI requires keeping: that article covers *écritures*, not
    sessions.

    `clearsessions` is a management command rather than an ORM call because the session
    engine owns its own storage: swapping to `cached_db` later must not need this task
    rewritten. It is the command's own job to know what "expired" means for the configured
    engine.
    """
    from django.core.management import call_command

    call_command("clearsessions")
    logger.info("expired sessions cleared from the control-plane database")
