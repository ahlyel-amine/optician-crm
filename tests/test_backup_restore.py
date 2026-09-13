"""TENANT-09 — per-client logical backup and restore.

The requirement is explicit that per-instance PITR does not satisfy it, which settles the
approach: implement per-client logical backup and restore ourselves, provider-independent.
`pg_dump` dumps a single database; roles and tablespaces are cluster-wide and are **not**
in the dump, which is the single most commonly missed step in a logical restore.

Restore goes into a **new** database name, is verified, and is cut over by updating
`Client.db_name` in one transactional UPDATE on `default` — never restored in place over
a live database. That makes restore reversible and makes the control-plane row the switch.

The word the requirement turns on is **verified**. Row counts are not verification: they
pass while every column value is wrong. Verification here is an ordered per-table `md5`
digest folded into one value, including sequence positions, compared before and after,
with a deliberate mutation in between so that a no-op "restore" cannot pass.
"""

from __future__ import annotations

import subprocess
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.conf import settings
from django.db import connections

from plateforme.control_plane.models import BackupRun, Client
from plateforme.tenancy.maintenance import (
    database_exists,
    drop_database_force,
    maintenance_connection,
)
from plateforme.tenancy.registry import alias_for


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def _destroy(code: str) -> None:
    """Drop everything the named client owns, by exact name. Never by pattern."""
    from psycopg import sql

    client = Client.objects.using("default").filter(code=code).first()
    if client is None:
        return

    alias = alias_for(client.pk)
    if alias in connections.settings:
        try:
            connections[alias].close()
            del connections[alias]
        except (AttributeError, KeyError):
            pass

    names = {client.db_name} if client.db_name else set()
    with maintenance_connection() as cur:
        # Also collect any `<db_name>_restore_<ts>` databases this test left behind. The
        # prefix check below is what keeps this from being a pattern drop.
        cur.execute(
            "SELECT datname FROM pg_database WHERE starts_with(datname, %s)",
            (f"{settings.TENANT_DB_NAME_PREFIX}",),
        )
        for (name,) in cur.fetchall():
            if client.db_name and name.startswith(f"{client.db_name}_restore_"):
                names.add(name)
        for name in names:
            assert name.startswith(settings.TENANT_DB_NAME_PREFIX), name
            drop_database_force(cur, name)
        if client.db_user:
            assert client.db_user.startswith(settings.TENANT_DB_USER_PREFIX)
            cur.execute(
                sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(client.db_user))
            )

    # The artifacts too. A dump is health data at rest in production, and a test that
    # leaves them behind trains everyone to ignore the directory (threat T-02-45).
    from pathlib import Path

    root = Path(settings.BACKUP_LOCAL_ROOT) / "client" / client.code
    if root.exists():
        for artifact in root.rglob("*.dump"):
            artifact.unlink(missing_ok=True)
        for directory in sorted(root.rglob("*"), reverse=True):
            if directory.is_dir():
                directory.rmdir()
        root.rmdir()

    BackupRun.objects.using("default").filter(client=client).delete()
    Client.objects.using("default").filter(pk=client.pk).delete()


def _seed_distinguishable_data(client, *, marker: str) -> None:
    """Write rows whose values differ per client, so a mix-up is visible in the digest."""
    from plateforme.tenancy.context import tenant_context

    from domaine.caisse.models import EcritureCaisse
    from domaine.magasins.models import Magasin
    from domaine.stock.models import MouvementStock

    with tenant_context(alias_for(client.pk)):
        magasin = Magasin.objects.get(code="CENTRE")
        for i in range(1, 4):
            MouvementStock.objects.create(
                magasin=magasin,
                reference_article=f"{marker}-ART-{i:03d}",
                type_mouvement="entree",
                quantite_delta=i * 10,
                motif=f"seed {marker}",
            )
            EcritureCaisse.objects.create(
                magasin=magasin,
                sens="entree",
                montant=Decimal(f"{i}00.{i}{i}"),
                libelle=f"{marker} vente {i}",
            )


# --------------------------------------------------------------------------------------
# TENANT-09 — the scheduled fan-out
# --------------------------------------------------------------------------------------
@pytest.mark.django_db
def test_tenant09_backup_runs_for_every_active_client():
    """The scheduled fan-out covers every ACTIVE client, and only ACTIVE ones.

    Asserted on the enqueued arguments, **by `client_id` and never by model instance**
    (`plateforme/tenancy/tasks.py`: a pickled instance carries a stale `_state.db` and a
    schema version that may have moved by the time the worker runs it).

    A backup system that silently skips a client is worse than none, because it is
    trusted. `BackupRun` is what makes coverage auditable rather than assumed.
    """
    from plateforme.control_plane import tasks
    from tests.factories import ClientFactory

    active = [
        ClientFactory(
            code=f"bk-act-{i}", status=Client.ACTIVE, db_name=f"test_client_c00080{i}"
        )
        for i in range(1, 4)
    ]
    ClientFactory(code="bk-fail", status=Client.FAILED, db_name="test_client_c000811")
    ClientFactory(code="bk-susp", status=Client.SUSPENDED, db_name="test_client_c000812")
    ClientFactory(code="bk-pend", status=Client.PENDING)

    with patch.object(tasks.backup_client_task, "apply_async") as enqueue:
        enqueued = tasks.backup_all_active_clients()

    assert enqueue.call_count == 3, (
        f"the fan-out enqueued {enqueue.call_count} task(s); exactly the three ACTIVE "
        "clients were expected."
    )
    assert sorted(enqueued) == sorted(c.pk for c in active)

    for call in enqueue.call_args_list:
        kwargs = call.kwargs.get("kwargs", {})
        assert set(kwargs) == {"client_id"}, (
            f"the task was enqueued with {sorted(kwargs)}. Tasks take client_id and "
            "nothing else; never a model instance."
        )
        assert isinstance(kwargs["client_id"], int)


@pytest.mark.django_db
def test_tenant09_backup_task_without_client_id_fails_closed():
    """No `client_id`, no run. The control-plane task inherits the same discipline.

    It does not need tenant *binding* — `pg_dump` is a subprocess, not an ORM query — but
    a backup task that quietly did nothing when handed no argument would be the worst
    possible failure, because `BackupRun` would show no row and nobody looks for an
    absence.
    """
    from plateforme.control_plane import tasks

    with pytest.raises((TypeError, ValueError)):
        tasks.backup_client_task.run()

    with pytest.raises(ValueError):
        tasks.backup_client_task.run(client_id=None)


@pytest.mark.django_db
def test_tenant09_one_client_failing_still_records_runs_for_the_rest():
    """A failing client must not stop the fan-out, and must leave evidence of its failure.

    Same reasoning as `migrate_all`: the absence of a `BackupRun` row is indistinguishable
    from "never attempted", which is exactly the state a trusted backup system must never
    be in silently.
    """
    from plateforme.control_plane import backup, tasks
    from tests.factories import ClientFactory

    good = ClientFactory(
        code="bk-ok", status=Client.ACTIVE, db_name="test_client_c000821"
    )
    bad = ClientFactory(
        code="bk-bad", status=Client.ACTIVE, db_name="test_client_c000822"
    )

    def _fake(client_id):
        client = Client.objects.using("default").get(pk=client_id)
        run = BackupRun.objects.using("default").create(
            client=client, status=BackupRun.RUNNING
        )
        if client_id == bad.pk:
            run.status = BackupRun.FAILED
            run.error = "pg_dump exited 1"
            run.save(using="default")
            raise RuntimeError("pg_dump exited 1")
        run.status = BackupRun.OK
        run.bytes = 1
        run.save(using="default")
        return run

    with patch.object(backup, "backup_client", side_effect=_fake):
        for pk in tasks.backup_all_active_clients(enqueue=False):
            try:
                tasks.backup_client_task.run(client_id=pk)
            except RuntimeError:
                pass

    runs = {r.client.code: r.status for r in BackupRun.objects.using("default").all()}
    assert runs == {"bk-ok": BackupRun.OK, "bk-bad": BackupRun.FAILED}, runs
    assert BackupRun.objects.using("default").get(client=bad).error
    assert BackupRun.objects.using("default").get(client=good).status == BackupRun.OK


# --------------------------------------------------------------------------------------
# TENANT-09 — a real dump
# --------------------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant09_backup_produces_a_restorable_artifact(allow_runtime_tenant_aliases):
    """A valid custom-format archive, not merely a file that was written.

    `pg_restore --list` is what distinguishes the two: it parses the archive's table of
    contents. A zero-byte file, a truncated dump or a plain-SQL file written under the
    wrong `--format` all pass "the file exists" and fail here.
    """
    from plateforme.control_plane.backup import backup_client
    from plateforme.control_plane.provisioning import provision_client
    from plateforme.control_plane.storage import get_storage

    code = "test-bk-art"
    try:
        client = provision_client(
            code=code, raison_sociale="Optique Backup", magasins=["Centre"]
        )
        _seed_distinguishable_data(client, marker="ART")

        run = backup_client(client.pk)

        assert run.status == BackupRun.OK, run.error
        assert run.bytes > 0
        assert len(run.sha256) == 64
        assert run.object_key
        assert run.schema_digest == client.schema_digest
        assert run.finished_at is not None

        local = get_storage().get(run.object_key, None)
        try:
            listing = subprocess.run(
                [settings.PG_RESTORE_BIN, "--list", str(local)],
                capture_output=True,
                text=True,
                check=False,
            )
            assert listing.returncode == 0, listing.stderr
            assert "TABLE DATA" in listing.stdout, (
                "the archive's table of contents has no table data — the dump is empty "
                f"or is not a custom-format archive:\n{listing.stdout[:800]}"
            )
            assert "stock_mouvementstock" in listing.stdout
        finally:
            local.unlink(missing_ok=True)
    finally:
        _destroy(code)


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant09_backup_records_the_schema_digest_of_what_it_dumped(
    allow_runtime_tenant_aliases,
):
    """A digest is only comparable within one schema version, so record the version.

    A column added by a later migration changes **every** table digest. Without
    `BackupRun.schema_digest` a restore could be verified against a checksum taken under a
    different schema and reported as a mismatch — or, worse, compared successfully by
    accident (threat T-02-48).
    """
    from plateforme.control_plane.backup import backup_client
    from plateforme.control_plane.provisioning import provision_client

    code = "test-bk-digest"
    try:
        client = provision_client(
            code=code, raison_sociale="Optique Digest", magasins=["Centre"]
        )
        run = backup_client(client.pk)

        assert run.schema_digest, "no schema_digest was recorded with the dump"
        assert run.schema_digest == client.schema_digest

        # And it is a real digest of this schema, not a constant.
        from plateforme.control_plane.schema_version import (
            read_applied_heads,
            schema_digest,
        )

        assert run.schema_digest == schema_digest(read_applied_heads(alias_for(client.pk)))
    finally:
        _destroy(code)


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant09_backup_never_leaves_the_dump_on_local_disk(
    allow_runtime_tenant_aliases,
):
    """The temporary dump is removed on every path. It is health data at rest.

    A `pg_dump` of a client database is a complete copy of that optician's ordonnances.
    `/tmp` is world-readable on most systems and survives the process (threat T-02-45).
    Asserted on the failure path too, because that is the path a `finally` is for.
    """
    from plateforme.control_plane import backup
    from plateforme.control_plane.provisioning import provision_client

    code = "test-bk-tmp"
    seen: list = []
    try:
        client = provision_client(
            code=code, raison_sociale="Optique Tmp", magasins=["Centre"]
        )

        real_run = subprocess.run

        def _spy(args, **kwargs):
            if args and str(args[0]).endswith("pg_dump"):
                for arg in args:
                    if str(arg).startswith("--file="):
                        seen.append(str(arg).split("=", 1)[1])
            return real_run(args, **kwargs)

        with patch.object(backup.subprocess, "run", side_effect=_spy):
            backup.backup_client(client.pk)
        assert seen, "pg_dump was never invoked with --file="
        from pathlib import Path

        assert not Path(seen[0]).exists(), (
            f"{seen[0]} survived a successful backup. A dump of a client database is "
            "health data at rest and must not linger on local disk."
        )

        # Failure path.
        seen.clear()

        def _spy_fail(args, **kwargs):
            if args and str(args[0]).endswith("pg_dump"):
                for arg in args:
                    if str(arg).startswith("--file="):
                        seen.append(str(arg).split("=", 1)[1])
                raise RuntimeError("pg_dump blew up")
            return real_run(args, **kwargs)

        with patch.object(backup.subprocess, "run", side_effect=_spy_fail):
            with pytest.raises(RuntimeError):
                backup.backup_client(client.pk)
        assert seen
        assert not Path(seen[0]).exists(), (
            f"{seen[0]} survived a *failed* backup — the cleanup is not in a finally."
        )
        assert (
            BackupRun.objects.using("default")
            .filter(client_id=client.pk, status=BackupRun.FAILED)
            .exists()
        ), "a failed dump left no BackupRun row, so the failure is invisible"
    finally:
        _destroy(code)
