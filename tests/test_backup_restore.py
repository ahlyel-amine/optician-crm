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


# --------------------------------------------------------------------------------------
# TENANT-09 — tenant_checksum, the part the requirement actually turns on
# --------------------------------------------------------------------------------------
@pytest.mark.tenancy
def test_tenant09_checksum_is_independent_of_physical_row_order(tenant_a):
    """The identical rows, laid out in a different physical order, hash the same.

    The **row hashes** are ordered, not the rows. `pg_restore` does not preserve physical
    row order, so a digest that depended on it would report every single restore as a
    failure — and the natural reaction to a verification step that always fails is to stop
    running it.

    The rows are deleted and re-inserted **with their original primary keys and
    timestamps**, in reverse order, so the *only* thing that changes is the heap layout.
    The test proves the layout really did change before asserting the digest did not; a
    version that skipped that would pass against a digest that is order-dependent, on a
    table small enough that the order happened not to move.

    Deliberately within **one** database. The plan suggests building the same rows in two
    databases, which cannot work and should not: two independently migrated tenants differ
    in `django_migrations.applied` and in every `created_at`, so their digests are
    correctly unequal. That is not the property under test — a restore compares one
    database against its own earlier state.
    """
    from django.db import connections

    from plateforme.control_plane.checksum import tenant_checksum

    from domaine.magasins.models import Magasin
    from domaine.stock.models import MouvementStock

    magasin = Magasin.objects.create(code="ORD", nom="Ordre")
    for ref, qty in [("A-001", 10), ("B-002", 20), ("C-003", 30)]:
        MouvementStock.objects.create(
            magasin=magasin, reference_article=ref, type_mouvement="entree",
            quantite_delta=qty,
        )

    columns = (
        "id, magasin_id, reference_article, type_mouvement, quantite_delta, motif, "
        "created_at"
    )
    with connections["tenant_a"].cursor() as cur:
        cur.execute(f"SELECT {columns} FROM stock_mouvementstock ORDER BY id")
        rows = cur.fetchall()
        cur.execute("SELECT id FROM stock_mouvementstock")
        layout_before = [r[0] for r in cur.fetchall()]

    before = tenant_checksum("tenant_a")

    with connections["tenant_a"].cursor() as cur:
        cur.execute("DELETE FROM stock_mouvementstock")
        placeholders = ", ".join(["%s"] * len(rows[0]))
        for row in reversed(rows):
            cur.execute(
                f"INSERT INTO stock_mouvementstock ({columns}) VALUES ({placeholders})",
                row,
            )
        cur.execute("SELECT id FROM stock_mouvementstock")
        layout_after = [r[0] for r in cur.fetchall()]

    assert layout_before != layout_after, (
        f"the physical layout did not change ({layout_before} -> {layout_after}), so this "
        "test would pass against an order-dependent digest. It proves nothing as written."
    )
    assert sorted(layout_before) == sorted(layout_after), "the rows themselves changed"

    assert tenant_checksum("tenant_a") == before, (
        f"the same rows in a different physical order ({layout_before} -> "
        f"{layout_after}) produced a different digest. The digest must order the row "
        "hashes, not rely on the rows arriving in order."
    )


@pytest.mark.tenancy
def test_tenant09_checksum_detects_a_single_changed_column_value(tenant_a):
    """One column changed in one row changes the digest. A checksum that cannot fail is none.

    And the control in the other direction: changing nothing must not change it, or the
    digest is simply unstable and every restore would "fail".
    """
    from plateforme.control_plane.checksum import tenant_checksum

    from domaine.magasins.models import Magasin
    from domaine.stock.models import MouvementStock

    magasin = Magasin.objects.create(code="CHG", nom="Change")
    mouvement = MouvementStock.objects.create(
        magasin=magasin, reference_article="REF-1", type_mouvement="entree",
        quantite_delta=5, motif="original",
    )

    before = tenant_checksum("tenant_a")
    assert tenant_checksum("tenant_a") == before, "the digest is not stable at rest"

    MouvementStock.objects.filter(pk=mouvement.pk).update(motif="altered")
    after = tenant_checksum("tenant_a")

    assert after != before, (
        "one column value changed and the digest did not. Row counts have this property "
        "too, which is exactly why they are not verification."
    )

    MouvementStock.objects.filter(pk=mouvement.pk).update(motif="original")
    assert tenant_checksum("tenant_a") == before, "the digest is not reversible"


@pytest.mark.tenancy
def test_tenant09_checksum_includes_sequence_positions(tenant_a):
    """A restored database with reset sequences is **not** identical, even if every row matches.

    Not academic here: Phase 6's facture numbering comes from a counter row, and a
    restored database whose sequences were reset would re-issue primary keys that already
    exist in the retained audit trail.

    The sequence is advanced without inserting a row, so only the sequence position
    differs — the tables are byte-identical.
    """
    from django.db import connections

    from plateforme.control_plane.checksum import tenant_checksum

    from domaine.magasins.models import Magasin

    Magasin.objects.create(code="SEQ", nom="Sequence")
    before = tenant_checksum("tenant_a")

    with connections["tenant_a"].cursor() as cur:
        cur.execute("SELECT pg_get_serial_sequence('magasins_magasin', 'id')")
        sequence = cur.fetchone()[0]
        assert sequence, "no sequence found — the test cannot prove anything"
        cur.execute("SELECT nextval(%s)", (sequence,))

    after = tenant_checksum("tenant_a")
    assert after != before, (
        "advancing a sequence did not change the digest. A restore that reset the "
        "sequences would be reported as identical, and the next insert would collide."
    )


@pytest.mark.tenancy
def test_tenant09_checksum_is_reproducible_across_session_timezones(tenant_a):
    """The digest does not depend on the session `TimeZone`, because the command pins it.

    `timestamptz` renders per session timezone, and every ledger row carries a
    `created_at`. Without `SET TIME ZONE 'UTC'` the digest computed by an operator in
    Casablanca would differ from the one computed by a worker in UTC, and the restore
    would be reported as a mismatch.

    The `Africa/Casablanca` half is load-bearing: with a UTC-only test the pin could be
    removed and nothing would notice.
    """
    from django.db import connections

    from plateforme.control_plane.checksum import tenant_checksum

    from domaine.caisse.models import EcritureCaisse
    from domaine.magasins.models import Magasin

    magasin = Magasin.objects.create(code="TZ", nom="Timezone")
    EcritureCaisse.objects.create(
        magasin=magasin, sens="entree", montant=Decimal("42.42"), libelle="tz"
    )

    with connections["tenant_a"].cursor() as cur:
        cur.execute("SET TIME ZONE 'UTC'")
    in_utc = tenant_checksum("tenant_a")

    with connections["tenant_a"].cursor() as cur:
        cur.execute("SET TIME ZONE 'Africa/Casablanca'")
    in_casablanca = tenant_checksum("tenant_a")

    with connections["tenant_a"].cursor() as cur:
        cur.execute("SHOW TimeZone")
        assert cur.fetchone()[0] == "Africa/Casablanca", (
            "tenant_checksum changed the session TimeZone and did not put it back. It "
            "pins UTC for its own reproducibility, and leaving that behind on a "
            "connection that returns to a pool is exactly the session-state problem "
            "transaction pooling has (threat T-02-02)."
        )

    assert in_utc == in_casablanca, (
        "the digest depends on the session timezone, so `SET TIME ZONE 'UTC'` is not "
        "taking effect. timestamptz renders per session TZ and every ledger row has a "
        "created_at."
    )


@pytest.mark.tenancy
def test_tenant09_checksum_detail_localises_a_mismatch_to_one_table(tenant_a):
    """`tenant_checksum_detail` says *which* table differs, not merely that something does.

    Reporting "different" at 3am against a restore of a client's ten years of records is
    not an answer anybody can act on.
    """
    from plateforme.control_plane.checksum import tenant_checksum_detail

    from domaine.magasins.models import Magasin
    from domaine.stock.models import MouvementStock

    magasin = Magasin.objects.create(code="DET", nom="Detail")
    mouvement = MouvementStock.objects.create(
        magasin=magasin, reference_article="D-1", type_mouvement="entree",
        quantite_delta=1,
    )

    before = tenant_checksum_detail("tenant_a")
    assert "stock_mouvementstock" in before
    assert "magasins_magasin" in before
    assert "__sequences__" in before

    MouvementStock.objects.filter(pk=mouvement.pk).update(quantite_delta=2)
    after = tenant_checksum_detail("tenant_a")

    changed = {t for t in before if before[t] != after.get(t)}
    assert changed == {"stock_mouvementstock"}, (
        f"a change in one table moved the digest of {sorted(changed)}. The per-table "
        "breakdown must localise a mismatch, or it adds nothing over the single digest."
    )
