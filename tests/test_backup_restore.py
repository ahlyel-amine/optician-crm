"""TENANT-09 — per-client logical backup and restore.

The requirement is explicit that per-instance PITR does not satisfy it, which settles the
approach: implement per-client logical backup and restore ourselves, provider-independent.
`pg_dump` dumps a single database; roles and tablespaces are cluster-wide and are **not**
in the dump, which is the single most commonly missed step in a logical restore.

Restore goes into a **new** database name, is verified, and is cut over by updating
`Client.db_name` in one transactional UPDATE on `default` — never restored in place over
a live database. That makes restore reversible and makes the control-plane row the switch.
"""

import pytest


@pytest.mark.pending
@pytest.mark.slow
@pytest.mark.tenancy
def test_tenant09_single_client_restore_produces_identical_data():
    """One client is restored to its backed-up state; its neighbour is untouched.

    Shape, and every line of it is load-bearing::

        a = provision_client(code="REST-A", ...)   # real databases
        b = provision_client(code="REST-B", ...)
        seed_distinguishable_data(a); seed_distinguishable_data(b)
        before_a, before_b = tenant_checksum(a), tenant_checksum(b)
        key = backup_client(a)
        mutate_after_backup(a)          # so a no-op "restore" cannot pass
        restore_client(a, key, cutover=True)
        assert tenant_checksum(a) == before_a     # restored
        assert tenant_checksum(b) == before_b     # and the neighbour was untouched

    `mutate_after_backup` is what makes this a real test rather than a tautology, and the
    `before_b` assertion is what proves *per-database* restore rather than per-instance
    restore — which is precisely what TENANT-09 says PITR does not give us.

    "Identical" is an ordered per-table `md5` digest plus `pg_sequences.last_value`, not
    row counts: row counts pass while column values are wrong, and a restored database
    with reset sequences is not identical even when every row matches. The digest session
    must `SET TIME ZONE 'UTC'`, because `timestamptz` renders per session timezone.

    Pending: needs `backup_client`, `restore_client` and `tenant_checksum`.
    """
    pytest.fail("pending: implemented by plan 02-07")


@pytest.mark.pending
@pytest.mark.slow
def test_tenant09_backup_runs_for_every_active_client():
    """The scheduled fan-out covers every ACTIVE client, and only ACTIVE ones.

    Provision several clients in different statuses, run the scheduled backup task, and
    assert a `BackupRun` row exists for each ACTIVE client with its byte count and
    sha256, that no run was attempted for the PENDING / FAILED / SUSPENDED ones, and that
    one client failing still leaves runs recorded for the rest.

    A backup system that silently skips a client is worse than none, because it is
    trusted. The `BackupRun` table is what makes coverage auditable rather than assumed.

    Pending: needs the Celery Beat backup fan-out.
    """
    pytest.fail("pending: implemented by plan 02-07")
