"""Print a client database's data digest. Used by the restore drill and ad hoc.

`--detail` prints the per-table breakdown, which is what turns "the databases differ" into
"`stock_mouvementstock` differs" — the only form of that sentence anyone can act on at 3am.

The digest is only comparable **within one schema version**, so the client's
`schema_digest` is printed beside it. A column added by a later migration changes every
table's digest.
"""

from django.core.management.base import BaseCommand, CommandError

from plateforme.control_plane.checksum import tenant_checksum, tenant_checksum_detail
from plateforme.control_plane.models import Client
from plateforme.tenancy.registry import alias_for, register_client_database


class Command(BaseCommand):
    help = "Print the data digest of a client database (TENANT-09 verification)."

    def add_arguments(self, parser):
        parser.add_argument("--code", help="Client code. Resolves through the control plane.")
        parser.add_argument(
            "--alias", help="An already-registered connection alias, instead of --code."
        )
        parser.add_argument(
            "--detail", action="store_true", help="Also print the per-table digests."
        )

    def handle(self, *args, **options):
        if bool(options["code"]) == bool(options["alias"]):
            raise CommandError("Pass exactly one of --code or --alias.")

        if options["alias"]:
            alias, schema_digest = options["alias"], None
        else:
            try:
                client = Client.objects.using("default").get(code=options["code"])
            except Client.DoesNotExist:
                raise CommandError(f"No client with code {options['code']!r}.") from None
            # Direct to PostgreSQL: this may well be run against a restore target that
            # PgBouncer has never heard of.
            alias = register_client_database(**client.connection_params(direct=True))
            schema_digest = client.schema_digest

        if options["detail"]:
            for table, digest in sorted(tenant_checksum_detail(alias).items()):
                self.stdout.write(f"{digest}  {table}")
            self.stdout.write("")

        self.stdout.write(tenant_checksum(alias))
        if schema_digest is not None:
            self.stdout.write(
                f"schema_digest {schema_digest}  "
                "(digests are only comparable within one schema version)"
            )
