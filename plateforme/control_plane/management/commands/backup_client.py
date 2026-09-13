"""Dump one client's database. A thin wrapper, same rule as `provision_client`.

The Beat fan-out calls `backup.backup_client(client_id)` through a Celery task, so any
logic that settled here would be logic the schedule does not have.
"""

from django.core.management.base import BaseCommand, CommandError

from plateforme.control_plane.backup import backup_client
from plateforme.control_plane.models import Client


class Command(BaseCommand):
    help = "Dump one client's database to the configured backup storage."

    def add_arguments(self, parser):
        parser.add_argument("--code", required=True)

    def handle(self, *args, **options):
        try:
            client = Client.objects.using("default").get(code=options["code"])
        except Client.DoesNotExist:
            raise CommandError(f"No client with code {options['code']!r}.") from None

        run = backup_client(client.pk)
        self.stdout.write(
            f"{client.code}\n"
            f"  status         {run.status}\n"
            f"  object_key     {run.object_key}\n"
            f"  bytes          {run.bytes}\n"
            f"  sha256         {run.sha256}\n"
            f"  schema_digest  {run.schema_digest}\n"
            f"  backup_run_id  {run.pk}"
        )
