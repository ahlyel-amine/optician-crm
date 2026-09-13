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

    from plateforme.control_plane.provisioning import derive_db_name

    # The base name this client's databases derive from — **not** `client.db_name`, which
    # after a cutover points at the restore target while the original is still there,
    # retained on purpose. Missing it leaves a database owned by a role the next line
    # tries to drop: `DependentObjectsStillExist: role ... cannot be dropped`.
    base = derive_db_name(client.pk)
    names = {base}
    if client.db_name:
        names.add(client.db_name)
    with maintenance_connection() as cur:
        cur.execute(
            "SELECT datname FROM pg_database WHERE starts_with(datname, %s)", (base,)
        )
        names.update(name for (name,) in cur.fetchall())
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


# --------------------------------------------------------------------------------------
# TENANT-09 — the restore drill
# --------------------------------------------------------------------------------------
def _mutate_after_backup(client) -> None:
    """Change the data, so a restore that does nothing at all cannot pass.

    Three kinds of change, because a restore could plausibly get one of them right by
    accident: a row deleted, a row's column value changed, and a row inserted.
    """
    from plateforme.tenancy.context import tenant_context

    from domaine.caisse.models import EcritureCaisse
    from domaine.magasins.models import Magasin
    from domaine.stock.models import MouvementStock

    with tenant_context(alias_for(client.pk)):
        MouvementStock.objects.order_by("id").first().delete()
        EcritureCaisse.objects.order_by("id").update(libelle="CLOBBERED")
        MouvementStock.objects.create(
            magasin=Magasin.objects.get(code="CENTRE"),
            reference_article="MUTANT-999",
            type_mouvement="sortie",
            quantite_delta=-999,
            motif="written after the backup was taken",
        )


@pytest.mark.slow
@pytest.mark.tenancy
@pytest.mark.django_db(transaction=True)
def test_tenant09_single_client_restore_produces_identical_data(
    allow_runtime_tenant_aliases,
):
    """One client is restored to its backed-up state; its neighbour is untouched.

    Every line is load-bearing:

    * **`_mutate_after_backup`** is what makes this a real test rather than a tautology.
      Without it, a `restore_client` that did nothing at all would pass.
    * **`tenant_checksum(a) == before_a`** is verification, not a `pg_restore` exit code.
      An exit code proves a process ran; the digest proves the data came back.
    * **`tenant_checksum(b) == before_b`** is what proves **per-database** restore rather
      than per-instance restore — which is exactly what TENANT-09 says PITR does not give
      us. The neighbour shares a PostgreSQL instance with A, so a server-level restore
      would move B's digest too.
    """
    from plateforme.control_plane.backup import backup_client, restore_client
    from plateforme.control_plane.checksum import tenant_checksum
    from plateforme.control_plane.provisioning import provision_client

    code_a, code_b = "test-rest-a", "test-rest-b"
    try:
        a = provision_client(
            code=code_a, raison_sociale="Optique Restore A", magasins=["Centre"]
        )
        b = provision_client(
            code=code_b, raison_sociale="Optique Restore B", magasins=["Centre"]
        )
        _seed_distinguishable_data(a, marker="AAA")
        _seed_distinguishable_data(b, marker="BBB")

        before_a = tenant_checksum(alias_for(a.pk))
        before_b = tenant_checksum(alias_for(b.pk))
        assert before_a != before_b, (
            "the two clients hash identically, so the neighbour assertion below would "
            "pass even if A's data had been written into B."
        )

        run = backup_client(a.pk)
        assert run.status == BackupRun.OK, run.error

        _mutate_after_backup(a)
        mutated = tenant_checksum(alias_for(a.pk))
        assert mutated != before_a, (
            "the mutation did not change the digest, so a no-op restore would pass this "
            "test. It would be a tautology."
        )

        result = restore_client(a, run, cutover=True)

        a.refresh_from_db(using="default")
        assert a.db_name == result["restored_db"]
        assert a.db_name != result["previous_db"]

        register_after_cutover = a.connection_params(direct=True)
        from plateforme.tenancy.registry import register_client_database

        register_client_database(**register_after_cutover)

        assert tenant_checksum(alias_for(a.pk)) == before_a, (
            "client A's data did not come back to its backed-up state."
        )
        assert tenant_checksum(alias_for(b.pk)) == before_b, (
            "client B's digest moved. The restore was not confined to one logical "
            "database — which is precisely what TENANT-09 says per-instance PITR does "
            "not satisfy."
        )
    finally:
        _destroy(code_a)
        _destroy(code_b)


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant09_restore_never_writes_into_the_live_database(
    allow_runtime_tenant_aliases,
):
    """The restore target is a new database name, and the live one is untouched until cutover.

    Restoring in place over a live database is irreversible. Restoring beside it is not:
    the control-plane row is the switch, so a bad restore is undone by pointing `db_name`
    back at the database that is still sitting there (threat T-02-43).
    """
    from plateforme.control_plane.backup import backup_client, restore_client
    from plateforme.control_plane.checksum import tenant_checksum
    from plateforme.control_plane.provisioning import provision_client

    code = "test-rest-safe"
    try:
        client = provision_client(
            code=code, raison_sociale="Optique Safe", magasins=["Centre"]
        )
        _seed_distinguishable_data(client, marker="SAFE")
        run = backup_client(client.pk)

        _mutate_after_backup(client)
        live_before = tenant_checksum(alias_for(client.pk))
        live_name = client.db_name

        result = restore_client(client, run, cutover=False)

        assert result["restored_db"] != live_name
        assert result["restored_db"].startswith(f"{live_name}_restore_")
        assert not result["cutover"]

        client.refresh_from_db(using="default")
        assert client.db_name == live_name, (
            "db_name moved without --cutover. The switch must be explicit."
        )
        assert tenant_checksum(alias_for(client.pk)) == live_before, (
            "the live database changed during a restore that was not a cutover."
        )

        with maintenance_connection() as cur:
            assert database_exists(cur, result["restored_db"])
            assert database_exists(cur, live_name)
    finally:
        _destroy(code)


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant09_restore_creates_the_role_when_it_is_absent(
    allow_runtime_tenant_aliases,
):
    """`pg_dump` does not dump roles — they are cluster-wide. Restore must recreate them.

    This is the single most commonly missed step in a logical restore (Pitfall 10, threat
    T-02-47): the restore succeeds, and then nothing can connect to what it produced. The
    test therefore drops the role first — simulating a restore onto a fresh instance — and
    asserts afterwards that the restored database is **connectable as that role**, not
    merely that it exists.
    """
    from psycopg import sql

    import psycopg

    from plateforme.control_plane.backup import backup_client, restore_client
    from plateforme.control_plane.provisioning import provision_client

    code = "test-rest-role"
    try:
        client = provision_client(
            code=code, raison_sociale="Optique Role", magasins=["Centre"]
        )
        _seed_distinguishable_data(client, marker="ROLE")
        run = backup_client(client.pk)

        # Simulate a fresh instance: the database is dumped, the role is not.
        alias = alias_for(client.pk)
        if alias in connections.settings:
            try:
                connections[alias].close()
                del connections[alias]
            except (AttributeError, KeyError):
                pass
        with maintenance_connection() as cur:
            drop_database_force(cur, client.db_name)
            cur.execute(
                sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(client.db_user))
            )
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (client.db_user,))
            assert cur.fetchone() is None, "the role was not actually dropped"

        result = restore_client(client, run, cutover=True)

        with maintenance_connection() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (client.db_user,))
            assert cur.fetchone() is not None, (
                "the restore did not recreate the role. The database exists and nobody "
                "can connect to it."
            )

        # Connectable as that role — the assertion that "the role exists" does not make.
        conn = psycopg.connect(
            host=settings.PG_ADMIN_HOST,
            port=settings.PG_ADMIN_PORT,
            user=client.db_user,
            password=client.db_password,
            dbname=result["restored_db"],
            connect_timeout=5,
        )
        with conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM stock_mouvementstock")
            assert cur.fetchone()[0] == 3
        conn.close()
    finally:
        _destroy(code)


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant09_restore_refuses_a_dump_from_a_different_schema_version(
    allow_runtime_tenant_aliases,
):
    """Digests are only comparable within one schema version, so a mismatch is refused.

    And `--force` overrides it, because "the operator has decided this is acceptable" is a
    real situation during a disaster and a tool that cannot be overridden gets worked
    around instead (threat T-02-48).
    """
    from plateforme.control_plane.backup import (
        RestoreRefused,
        backup_client,
        restore_client,
    )
    from plateforme.control_plane.provisioning import provision_client

    code = "test-rest-schema"
    try:
        client = provision_client(
            code=code, raison_sociale="Optique Schema", magasins=["Centre"]
        )
        run = backup_client(client.pk)

        # The client has moved to a different schema version since the dump.
        Client.objects.using("default").filter(pk=client.pk).update(
            schema_digest="0" * 64
        )
        client.refresh_from_db(using="default")

        with pytest.raises(RestoreRefused, match="schema"):
            restore_client(client, run, cutover=False)

        with maintenance_connection() as cur:
            cur.execute(
                "SELECT count(*) FROM pg_database WHERE starts_with(datname, %s)",
                (f"{client.db_name}_restore_",),
            )
            assert cur.fetchone()[0] == 0, (
                "the refusal happened after a database had already been created. The "
                "schema check must come first."
            )

        result = restore_client(client, run, cutover=False, force=True)
        assert result["restored_db"].startswith(f"{client.db_name}_restore_")
    finally:
        _destroy(code)


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant09_restore_refuses_a_corrupted_artifact(allow_runtime_tenant_aliases):
    """A tampered or truncated archive fails on the hash, before `pg_restore` runs.

    Halfway through `pg_restore` is the wrong place to discover it: that leaves a
    partially populated database that has to be identified and dropped by hand
    (threat T-02-49).
    """
    from plateforme.control_plane.backup import (
        RestoreRefused,
        backup_client,
        restore_client,
    )
    from plateforme.control_plane.provisioning import provision_client

    code = "test-rest-sha"
    try:
        client = provision_client(
            code=code, raison_sociale="Optique Sha", magasins=["Centre"]
        )
        run = backup_client(client.pk)

        BackupRun.objects.using("default").filter(pk=run.pk).update(sha256="f" * 64)
        run.refresh_from_db(using="default")

        with pytest.raises(RestoreRefused, match="corrupted or substituted"):
            restore_client(client, run, cutover=False)

        with maintenance_connection() as cur:
            cur.execute(
                "SELECT count(*) FROM pg_database WHERE starts_with(datname, %s)",
                (f"{client.db_name}_restore_",),
            )
            assert cur.fetchone()[0] == 0
    finally:
        _destroy(code)


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant09_restore_never_restores_into_an_existing_database(
    allow_runtime_tenant_aliases,
):
    """A restore creates its own database, or refuses. It never adopts a populated one.

    `create_database` is guarded by an existence check, which is correct for provisioning
    — a killed run must adopt the database it already created — and wrong here. Restoring
    into a populated database means `pg_restore` runs into existing objects and, with
    `--exit-on-error`, aborts partway, leaving something that looks restored.

    Found during this plan's own drill, on exactly the flow the runbook prescribes:
    restore to verify, then restore again to cut over, both landing on the same
    timestamped name. The timestamp now carries seconds and the collision is refused.
    """
    from plateforme.control_plane.backup import (
        RestoreRefused,
        backup_client,
        restore_client,
        restore_target_name,
    )
    from plateforme.control_plane.provisioning import provision_client

    code = "test-rest-twice"
    try:
        client = provision_client(
            code=code, raison_sociale="Optique Twice", magasins=["Centre"]
        )
        run = backup_client(client.pk)

        # Occupy the name the next restore would choose.
        with patch(
            "plateforme.control_plane.backup.restore_target_name",
            return_value=restore_target_name(client, "FIXEDSTAMP"),
        ):
            first = restore_client(client, run, cutover=False)
            assert first["restored_db"].endswith("FIXEDSTAMP")

            with pytest.raises(RestoreRefused, match="already exists"):
                restore_client(client, run, cutover=False)
    finally:
        _destroy(code)


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant09_backup_keys_are_unique_even_within_one_second(
    allow_runtime_tenant_aliases,
):
    """Two dumps of one client never share an object key.

    An artifact silently overwritten by a later run is the worst kind of backup bug: the
    audit row still says `ok`, and it points at somebody else's snapshot. The `BackupRun`
    primary key is in the key, so uniqueness is by construction rather than by assuming no
    two dumps start in the same second.
    """
    from plateforme.control_plane.backup import backup_client
    from plateforme.control_plane.provisioning import provision_client

    code = "test-bk-key"
    try:
        client = provision_client(
            code=code, raison_sociale="Optique Key", magasins=["Centre"]
        )
        with patch(
            "plateforme.control_plane.backup._timestamp", return_value="20260101T000000Z"
        ):
            first = backup_client(client.pk)
            second = backup_client(client.pk)

        assert first.object_key != second.object_key, (
            f"two dumps taken in the same second share the key {first.object_key!r}; the "
            "second silently overwrote the first, and BackupRun still says both are ok."
        )
        assert first.sha256 and second.sha256
    finally:
        _destroy(code)


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant09_restore_refuses_a_backup_belonging_to_another_client(
    allow_runtime_tenant_aliases,
):
    """Restoring client B's dump into client A's database would be a cross-client leak.

    Not a warning — a refusal, before anything is created. The operator reaches for this
    command during an incident, which is exactly when a `--code` typo happens.
    """
    from plateforme.control_plane.backup import (
        RestoreRefused,
        backup_client,
        restore_client,
    )
    from plateforme.control_plane.provisioning import provision_client

    code_a, code_b = "test-mix-a", "test-mix-b"
    try:
        a = provision_client(
            code=code_a, raison_sociale="Optique Mix A", magasins=["Centre"]
        )
        b = provision_client(
            code=code_b, raison_sociale="Optique Mix B", magasins=["Centre"]
        )
        run_b = backup_client(b.pk)

        with pytest.raises(RestoreRefused, match="belongs to client"):
            restore_client(a, run_b, cutover=True)

        a.refresh_from_db(using="default")
        assert a.db_name.endswith(f"{a.pk:06d}"), "client A was cut over to B's data"
    finally:
        _destroy(code_a)
        _destroy(code_b)
