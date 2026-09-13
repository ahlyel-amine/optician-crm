"""TENANT-06 — the operator entry point. Arguments in, `provision_client(...)` out.

Deliberately thin. Phase 12's self-serve signup calls the same function from a Celery
task, so one code path with two entry points is the whole of TENANT-06 — and any logic
that settles here is logic self-serve will not have. Asserted by
`test_tenant06_command_module_contains_no_provisioning_logic`, which reads this source.
"""

from django.core.management.base import BaseCommand, CommandError

from plateforme.control_plane.provisioning import provision_client


class Command(BaseCommand):
    help = "Provision a client business: create its database, migrate it, seed magasins."

    def add_arguments(self, parser):
        parser.add_argument("--code", required=True, help="Operator-facing client code.")
        parser.add_argument(
            "--raison-sociale", dest="raison_sociale", required=True,
            help="Registered company name.",
        )
        parser.add_argument(
            "--db-host", dest="db_host", default=None,
            help="Override where this client's traffic goes. Defaults to the pooler.",
        )
        parser.add_argument(
            "--magasin", dest="magasins", action="append", metavar="NOM",
            help="Repeat once per magasin, e.g. --magasin Centre --magasin Maarif.",
        )

    def handle(self, *args, **options):
        magasins = options.get("magasins") or []
        if not magasins:
            # Presence only. The *rule* lives in seed_new_client so the self-serve path
            # inherits it; refusing here just avoids creating a database we would then
            # have to fail at step 4.
            raise CommandError(
                "At least one --magasin is required: a client business with zero "
                "magasins cannot sell anything and is not a valid state."
            )

        client = provision_client(
            code=options["code"],
            raison_sociale=options["raison_sociale"],
            magasins=magasins,
            db_host=options["db_host"],
        )

        # The password is never printed. It is generated server-side and stored
        # encrypted; an operator who needs it has a different problem (threat T-02-26).
        self.stdout.write(
            f"{client.code}\n"
            f"  status         {client.status}\n"
            f"  db_name        {client.db_name}\n"
            f"  db_host        {client.db_host}:{client.db_port}\n"
            f"  schema_digest  {client.schema_digest}"
        )
