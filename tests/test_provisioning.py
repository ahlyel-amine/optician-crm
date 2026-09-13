"""TENANT-01 / TENANT-05 / TENANT-06 — provisioning a client's database.

`CREATE DATABASE` cannot be executed inside a transaction block, so "completes or rolls
back cleanly" (TENANT-05) **cannot** be one atomic transaction. It is a status state
machine with compensating cleanup, where the control-plane `Client` row is the durable
record of intent and the only transactional part of it.

The invariant that makes TENANT-05 true: **only ACTIVE clients are ever routed to or
migrated.** A half-provisioned client is simply not visible to the rest of the system.
FAILED rows are visible to the operator, not to the router.

These tests do real `CREATE DATABASE` against Compose, so they are `slow` and need
`transaction=True` — the transaction that `TestCase` opens would make the DDL impossible.
"""

import pytest


@pytest.mark.pending
@pytest.mark.slow
def test_tenant01_provision_client_creates_database_at_migration_head():
    """TENANT-01: after `provision_client`, a real database exists, migrated to head.

    Assert three things, not one: the database appears in `pg_database`; its
    `django_migrations` table lists every business-app leaf node, so it is at head and
    not merely created; and the `Client` row is ACTIVE with `applied_heads` recorded and
    `provisioned_at` set.

    Asserting on `applied_heads` rather than on a version integer is the point of
    TENANT-02's shape: several business apps have independent migration chains.

    Pending: needs `provision_client`.
    """
    pytest.fail("pending: implemented by plan 02-04")


@pytest.mark.pending
@pytest.mark.slow
def test_tenant05_failed_provisioning_leaves_no_active_client():
    """A provisioning run that fails leaves the row FAILED, never ACTIVE.

    Force a failure partway through (for example by making `migrate` raise) and assert
    the `Client` ends FAILED with `last_error` populated, and that no client with that
    code is ACTIVE. An ACTIVE row is a promise to the router that a working database
    exists behind it; the `active_client_has_db_name` CHECK constraint is the same
    promise stated at the database level (threat T-02-08).

    Pending: needs `provision_client`.
    """
    pytest.fail("pending: implemented by plan 02-04")


@pytest.mark.pending
@pytest.mark.slow
def test_tenant05_rerun_after_kill_converges_to_active():
    """A run killed at any step converges to ACTIVE when rerun. That is what idempotent means.

    Interrupt after `CREATE DATABASE` but before `migrate`, then rerun `provision_client`
    with the same `code` and assert it reaches ACTIVE.

    Each step is individually idempotent: identity via `get_or_create(code=...)` with
    `db_name` derived from the pk and never regenerated; `CREATE ROLE` and
    `CREATE DATABASE` guarded by existence checks; `migrate` idempotent for free through
    `django_migrations`; seeding `get_or_create` only; activation a single transactional
    UPDATE.

    Pending: needs `provision_client`.
    """
    pytest.fail("pending: implemented by plan 02-04")


@pytest.mark.pending
@pytest.mark.slow
def test_tenant05_rerun_creates_no_second_database():
    """Rerunning provisioning must not orphan a database.

    Count `pg_database` entries matching the client prefix before and after the rerun and
    assert the count is unchanged and that `Client.db_name` still names the original.

    This is why `db_name` is derived from the primary key rather than generated fresh:
    a regenerated name on rerun would leave the first database behind with no `Client`
    row pointing at it, and a true orphan is only reapable by hand.

    Pending: needs `provision_client`.
    """
    pytest.fail("pending: implemented by plan 02-04")


@pytest.mark.pending
def test_tenant06_management_command_delegates_to_provision_client():
    """TENANT-06: the command parses arguments and calls `provision_client`. Nothing more.

    Patch `provision_client`, run the command with `--code`, `--raison-sociale` and
    repeated `--magasin`, and assert it was called once with exactly those arguments.

    The requirement is that **the command contains no provisioning logic of its own** —
    the self-serve signup flow in Phase 12 calls the same function from a Celery task, so
    any logic that lives in the command is logic self-serve will not have.

    Pending: needs the `provision_client` management command.
    """
    pytest.fail("pending: implemented by plan 02-04")
