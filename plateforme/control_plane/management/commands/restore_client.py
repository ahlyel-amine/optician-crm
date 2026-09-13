"""Restore one client's logical database beside the live one, verify it, then cut over.

A thin wrapper, same rule as `provision_client` and `backup_client`: the procedure lives in
`plateforme/control_plane/backup.py:restore_client`, so a future automated
disaster-recovery drill runs the same code an operator does.

The full procedure, including the step everyone forgets: `docs/restore-runbook.md`.
"""

from django.core.management.base import BaseCommand, CommandError

from plateforme.control_plane.backup import RestoreRefused, restore_client
from plateforme.control_plane.models import BackupRun, Client


class Command(BaseCommand):
    help = "Restore a client database from a BackupRun into a NEW database, and verify it."

    def add_arguments(self, parser):
        parser.add_argument("--code", required=True)
        parser.add_argument(
            "--backup",
            required=True,
            help="A BackupRun id, or the object key of the artifact.",
        )
        parser.add_argument(
            "--cutover",
            action="store_true",
            help=(
                "Point Client.db_name at the restored database. OFF by default: verify "
                "first, then cut over."
            ),
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Proceed even when the dump's schema version differs from the client's.",
        )

    def handle(self, *args, **options):
        try:
            client = Client.objects.using("default").get(code=options["code"])
        except Client.DoesNotExist:
            raise CommandError(f"No client with code {options['code']!r}.") from None

        runs = BackupRun.objects.using("default").filter(client=client)
        token = options["backup"]
        run = (
            runs.filter(pk=int(token)).first()
            if token.isdigit()
            else runs.filter(object_key=token).first()
        )
        if run is None:
            raise CommandError(
                f"No BackupRun {token!r} for {client.code}. Available:\n"
                + "\n".join(
                    f"  {r.pk}  {r.started_at:%Y-%m-%dT%H:%MZ}  {r.status:7}  "
                    f"{r.object_key}"
                    for r in runs.order_by("-started_at")[:10]
                )
            )
        if run.status != BackupRun.OK:
            raise CommandError(
                f"BackupRun {run.pk} is {run.status}, not ok. Restoring from a dump that "
                "did not finish would produce a partial database."
            )

        try:
            restore_client(
                client,
                run,
                cutover=options["cutover"],
                force=options["force"],
                stdout=self.stdout,
            )
        except RestoreRefused as exc:
            raise CommandError(str(exc)) from None
