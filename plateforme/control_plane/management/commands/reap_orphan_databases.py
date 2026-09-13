"""Report `pg_database` entries carrying the client prefix that no `Client` row claims.

**A database created before a kill is not an orphan.** Its `Client` row exists in
CREATING_DB or FAILED and a rerun of `provision_client` adopts it, because `db_name` is
derived from the primary key. A true orphan therefore only arises from manual meddling —
someone created a database by hand, or deleted a `Client` row that should have been left
as a tombstone.

That is why the predicate excludes every `Client.db_name` in **any** status, not just the
ACTIVE ones (threat T-02-25). A command that drops databases from a diff is one bad
predicate away from destroying a live client, so:

* `--dry-run` is the default, and it is what the Celery Beat schedule should run;
* dropping requires `--yes-i-am-sure`;
* and only names `derive_db_name` could have produced are ever considered, checked twice —
  once with `starts_with` in the query and once per name immediately before the drop.

**Why `is_client_database_name` and not a `LIKE` pattern.** The obvious predicate,
`datname LIKE 'optique_c%'`, is wrong in a way that destroys data: `_` is a
single-character wildcard in SQL `LIKE`, so that pattern matches **`optique_control`**.
The first run of this command against the development stack duly reported the control
plane itself as an orphan. `str.startswith` shares the blind spot. Only the full shape —
prefix plus exactly six digits — is safe.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from plateforme.control_plane.models import Client
from plateforme.control_plane.provisioning import is_client_database_name
from plateforme.tenancy.maintenance import drop_database_force, maintenance_connection


class Command(BaseCommand):
    help = "Report (and, with --yes-i-am-sure, drop) client databases no Client row claims."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes-i-am-sure",
            dest="confirmed",
            action="store_true",
            help="Actually drop the orphans. Without it this command only reports.",
        )

    def handle(self, *args, **options):
        prefix = settings.TENANT_DB_NAME_PREFIX
        # Every status, deliberately. See the module docstring.
        claimed = set(
            Client.objects.using("default")
            .exclude(db_name__isnull=True)
            .exclude(db_name="")
            .values_list("db_name", flat=True)
        )

        with maintenance_connection() as cur:
            # starts_with(), not LIKE: `_` is a LIKE wildcard and `optique_c%` matches
            # `optique_control`. The full-shape check below is the real predicate.
            cur.execute(
                "SELECT datname FROM pg_database "
                "WHERE starts_with(datname, %s) ORDER BY datname",
                (prefix,),
            )
            candidates = [
                row[0] for row in cur.fetchall() if is_client_database_name(row[0])
            ]
            orphans = [name for name in candidates if name not in claimed]

            self.stdout.write(
                f"{len(candidates)} database(s) with prefix {prefix!r}; "
                f"{len(claimed)} claimed by a Client row; {len(orphans)} orphan(s)."
            )
            for name in orphans:
                if not is_client_database_name(name):
                    # Unreachable given the filter above, and that is the point: if
                    # someone widens it, this refuses rather than obeys.
                    self.stderr.write(f"refusing {name!r}: not a client database name")
                    continue
                if options["confirmed"]:
                    drop_database_force(cur, name)
                    self.stdout.write(f"dropped  {name}")
                else:
                    self.stdout.write(f"orphan   {name}  (dry run; not dropped)")

        if orphans and not options["confirmed"]:
            self.stdout.write(
                "Dry run. Pass --yes-i-am-sure to drop. Check first that none of these "
                "belongs to a client whose row was removed by mistake — a dropped "
                "database is not recoverable from the control plane."
            )
