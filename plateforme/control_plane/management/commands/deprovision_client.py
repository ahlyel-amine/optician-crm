"""Drop a client's database. Requires an explicit `--yes-i-am-sure`.

Thin, for the same reason `provision_client` is thin: the logic lives in
`plateforme/control_plane/provisioning.py`, which is what a scheduled offboarding task
would call.

The `Client` row is **not** deleted — art. 211 CGI requires ten years of record retention
and the audit trail wants to know the client existed. The status is the tombstone.
"""

from django.core.management.base import BaseCommand, CommandError

from plateforme.control_plane.models import Client
from plateforme.control_plane.provisioning import deprovision_client


class Command(BaseCommand):
    help = "Drop a client's database. The control-plane row is kept as a tombstone."

    def add_arguments(self, parser):
        parser.add_argument("--code", required=True)
        parser.add_argument(
            "--yes-i-am-sure",
            dest="confirmed",
            action="store_true",
            help="Required. Without it this command refuses to do anything.",
        )

    def handle(self, *args, **options):
        if not options["confirmed"]:
            raise CommandError(
                "Refusing to drop a client database without --yes-i-am-sure. "
                "This destroys ten years of fiscal records unless a backup exists; "
                "take one with `manage.py backup_client` first."
            )

        try:
            client = Client.objects.using("default").get(code=options["code"])
        except Client.DoesNotExist:
            raise CommandError(f"No client with code {options['code']!r}.") from None

        deprovision_client(client)
        self.stdout.write(
            f"{client.code}: dropped {client.db_name}, row kept as {client.status}."
        )
