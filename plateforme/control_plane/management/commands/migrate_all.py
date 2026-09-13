"""TENANT-03 — apply a migration across the fleet, and report what happened to each client.

    manage.py migrate_all [--check] [--parallel N] [--client CODE ...] [--fail-fast]

**Exit codes are the contract**, because this command is a deploy gate:

=========  ====================================================================
`--check`  **1** if any ACTIVE client is behind, **0** otherwise. Applies nothing.
apply      **1** if any client failed, **0** otherwise.
=========  ====================================================================

A gate that prints a warning and exits 0 gates nothing, so both are asserted by tests and
by `02-VALIDATION.md`'s phase gate (*"`manage.py migrate_all --check` exits 0"*).

**The scaling escape hatch, recorded and deliberately not built.** At a few hundred
clients the natural shape is to enqueue one Celery task per client and return a
`MigrationRun` id the operator watches in the admin — retries and observability for free.
The synchronous command is built first because that is what a deploy actually needs, and
a deploy that returns a job id it cannot wait on is not a gate. Add the Celery variant
when a run stops fitting inside a deploy window, not before.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from plateforme.control_plane import fanout
from plateforme.control_plane.models import (
    Client,
    MigrationRun,
    MigrationRunResult,
    MigrationRunMode,
    MigrationRunStatus,
)
from plateforme.control_plane.schema_version import code_heads, schema_digest

COLUMNS = ("code", "db_name", "host", "before", "after", "status", "duration", "error")
WIDTHS = (16, 22, 18, 22, 22, 8, 9, 40)


def _heads_summary(heads: dict) -> str:
    """`magasins=0001_initial` for the business apps only, in a stable order.

    Filtered the same way `schema_digest` is: `migrate` records control-plane migrations
    in a tenant's `django_migrations` too, and printing them would bury the one column
    that changes.
    """
    from plateforme.tenancy.router import BUSINESS_APPS

    parts = [f"{k}={v}" for k, v in sorted(heads.items()) if k in BUSINESS_APPS]
    return ",".join(parts) or "-"


class Command(BaseCommand):
    help = "Apply migrations to every ACTIVE client database, or (--check) probe them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check", action="store_true",
            help="Probe every ACTIVE client, apply nothing, exit 1 if any is behind.",
        )
        parser.add_argument(
            "--parallel", type=int, default=fanout.DEFAULT_PARALLEL,
            help="Clients migrated concurrently, each in its own process. Default 4.",
        )
        parser.add_argument(
            "--client", dest="clients", action="append", metavar="CODE",
            help="Restrict to these client codes. Repeatable.",
        )
        parser.add_argument(
            "--fail-fast", dest="fail_fast", action="store_true", default=False,
            help=(
                "Stop submitting new work after the first failure. OFF by default: the "
                "requirement is that one client failing does not stop the others."
            ),
        )
        parser.add_argument(
            "--triggered-by", dest="triggered_by", default="command",
            help="Recorded on the MigrationRun row: command / celery / deploy.",
        )

    def handle(self, *args, **options):
        check_only = options["check"]

        # Only ACTIVE. A half-provisioned client is invisible to migration fan-out for
        # exactly the reason it is invisible to the router (threat T-02-33).
        clients = Client.objects.using("default").filter(status=Client.ACTIVE)
        if options["clients"]:
            clients = clients.filter(code__in=options["clients"])
        clients = list(clients.order_by("code"))

        run = MigrationRun.objects.using("default").create(
            triggered_by=options["triggered_by"],
            target_heads=code_heads(),
            mode=MigrationRunMode.CHECK if check_only else MigrationRunMode.APPLY,
        )

        jobs = [fanout.build_job(c, check_only=check_only) for c in clients]
        results = fanout.migrate_fleet(
            jobs, parallel=options["parallel"], fail_fast=options["fail_fast"]
        )

        by_pk = {c.pk: c for c in clients}
        self._print_table(results)
        counts = self._persist(run, results, by_pk, check_only=check_only)

        self.stdout.write(
            f"{counts['ok']} ok, {counts['failed']} failed, {counts['behind']} behind "
            f"({len(clients)} ACTIVE client(s), run #{run.pk})"
        )

        if check_only and counts["behind"]:
            raise CommandError(
                f"{counts['behind']} ACTIVE client(s) are behind the code's migration "
                "head. Deploying now would leave them on an older schema.",
                returncode=1,
            )
        if counts["failed"]:
            raise CommandError(
                f"{counts['failed']} client(s) failed to migrate. See run #{run.pk} in "
                "the operator admin for the per-client error.",
                returncode=1,
            )

    # -- output ------------------------------------------------------------------------
    def _print_table(self, results):
        """Fixed column order, so two deploys' output can be diffed."""
        header = "".join(c.ljust(w) for c, w in zip(COLUMNS, WIDTHS, strict=True))
        self.stdout.write(header)
        self.stdout.write("-" * len(header))
        for r in results:
            row = (
                r["code"],
                r["db_name"] or "-",
                r["host"] or "-",
                _heads_summary(r["heads_before"]),
                _heads_summary(r["heads_after"]),
                r["status"],
                f"{r['duration_seconds']:.3f}s",
                (r["error"] or "")[:WIDTHS[-1]],
            )
            self.stdout.write(
                "".join(str(v).ljust(w) for v, w in zip(row, WIDTHS, strict=True)).rstrip()
            )

    # -- persistence -------------------------------------------------------------------
    def _persist(self, run, results, by_pk, *, check_only):
        counts = {"ok": 0, "failed": 0, "behind": 0, "skipped": 0}
        now = timezone.now()

        with transaction.atomic(using="default"):
            for r in results:
                counts[r["status"]] = counts.get(r["status"], 0) + 1
                client = by_pk[r["pk"]]
                MigrationRunResult.objects.using("default").create(
                    run=run,
                    client=client,
                    status=r["status"],
                    heads_before=r["heads_before"],
                    heads_after=r["heads_after"],
                    duration_seconds=r["duration_seconds"],
                    error=r["error"],
                )
                if check_only or r["status"] != "ok":
                    # In check mode the *probed* truth is authoritative but it is not the
                    # recorded truth — recording it here would erase the distinction the
                    # control plane exists to keep (threat T-02-36). Only a successful
                    # apply updates `applied_heads`.
                    continue
                Client.objects.using("default").filter(pk=client.pk).update(
                    applied_heads=r["heads_after"],
                    schema_digest=schema_digest(r["heads_after"]),
                    schema_checked_at=now,
                )

            MigrationRun.objects.using("default").filter(pk=run.pk).update(
                finished_at=now,
                succeeded=counts["ok"],
                failed=counts["failed"],
                behind=counts["behind"],
                status=(
                    MigrationRunStatus.FAILED
                    if counts["failed"]
                    else MigrationRunStatus.OK
                ),
            )
        run.refresh_from_db(using="default")
        return counts
