"""TENANT-03 — migration fan-out across every client database.

With one database per client, a deploy is not "run migrate". It is "run migrate against
N databases, and know which of them did not make it". The two things that matter are
therefore reporting and failure isolation, and both are tested here.

`--check` mode is the CI/deploy gate: it probes every ACTIVE client, applies nothing, and
exits 1 if any client is behind. Recorded `applied_heads` and probed reality can diverge
(someone ran `migrate` by hand), so "recorded: behind" and "probed: behind" are different
facts and the command must keep them distinguishable.
"""

from __future__ import annotations

import io
import os
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.management import CommandError, call_command

from plateforme.control_plane.models import Client, MigrationRun, MigrationRunResult
from plateforme.tenancy.maintenance import drop_database_force, maintenance_connection
from plateforme.tenancy.registry import alias_for


def _destroy(code: str) -> None:
    """Drop what a test provisioned, by exact name. Mirrors tests/test_provisioning.py."""
    from django.db import connections
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
    with maintenance_connection() as cur:
        if client.db_name:
            assert client.db_name.startswith(settings.TENANT_DB_NAME_PREFIX)
            drop_database_force(cur, client.db_name)
        if client.db_user:
            assert client.db_user.startswith(settings.TENANT_DB_USER_PREFIX)
            cur.execute(
                sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(client.db_user))
            )
    MigrationRunResult.objects.using("default").filter(client=client).delete()
    Client.objects.using("default").filter(pk=client.pk).delete()


def _run(*args, **kwargs) -> tuple[int, str]:
    """Run `migrate_all`, returning `(exit_code, stdout)`.

    The command signals "some client is behind" or "some client failed" by raising
    `CommandError(..., returncode=N)`, which `execute_from_command_line` turns into
    `sys.exit(N)`. Under `call_command` it propagates, so the exit code is readable here
    without a subprocess — and the acceptance criteria check the real shell exit code
    separately, because a deploy pipeline gates on that and not on this.
    """
    out = io.StringIO()
    try:
        call_command("migrate_all", *args, stdout=out, stderr=out, **kwargs)
    except CommandError as exc:
        return (getattr(exc, "returncode", 1), out.getvalue())
    return (0, out.getvalue())


# --------------------------------------------------------------------------------------
# The two named TENANT-03 tests
# --------------------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant03_migration_fanout_reports_which_clients_are_behind(
    allow_runtime_tenant_aliases,
):
    """`migrate_all --check` names the clients that are behind, and exits non-zero.

    Exit code matters as much as the output — this is what a deploy pipeline gates on,
    and a command that prints a warning and exits 0 gates nothing.

    Three assertions, and the middle one is the load-bearing one: the gate must be clean
    *before* the rollback, or "it exits 1" proves only that it always exits 1.
    """
    from plateforme.control_plane.provisioning import provision_client

    behind_code, current_code = "test-behind", "test-current"
    try:
        behind = provision_client(
            code=behind_code, raison_sociale="Optique Behind", magasins=["Centre"]
        )
        provision_client(
            code=current_code, raison_sociale="Optique Current", magasins=["Centre"]
        )

        code_before, _ = _run("--check", "--parallel", "1")
        assert code_before == 0, "the gate was already red before anything was rolled back"

        call_command(
            "migrate", "magasins", "zero", database=alias_for(behind.pk), verbosity=0
        )

        exit_code, report = _run("--check", "--parallel", "1")

        assert exit_code == 1, (
            f"--check exited {exit_code} with a client behind. A gate that exits 0 while "
            f"printing a warning gates nothing.\n{report}"
        )
        assert behind_code in report, f"the behind client is not named:\n{report}"
        assert "behind" in report

        # The up-to-date client is reported, and reported as current.
        current_line = next(
            line for line in report.splitlines() if current_code in line
        )
        assert "behind" not in current_line, (
            f"the up-to-date client was reported as behind: {current_line!r}"
        )

        # --check applies nothing: the rolled-back client is still rolled back.
        from plateforme.control_plane.schema_version import pending_plan

        assert pending_plan(alias_for(behind.pk)), (
            "--check applied the migrations it was only supposed to probe."
        )
    finally:
        _destroy(behind_code)
        _destroy(current_code)


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_tenant03_one_client_failing_does_not_stop_the_others(
    allow_runtime_tenant_aliases,
):
    """Client 47 failing must not stop clients 48 through 300. Explicitly required.

    The middle client's database is dropped out from under it, which is deterministic in
    Compose in a way that "revoke some privilege" is not. The other two must still reach
    head and be reported `ok`.

    **The three-row assertion is the point.** Two `ok` rows and a non-zero exit code are
    also what you would see if the fan-out had skipped the broken client entirely; only
    the count proves it was attempted. The fan-out uses a *process* pool for exactly this
    reason — a process boundary makes failure isolation structurally true rather than
    hopefully true.
    """
    from plateforme.control_plane.provisioning import provision_client

    codes = ["test-fan-1", "test-fan-2", "test-fan-3"]
    try:
        clients = [
            provision_client(code=c, raison_sociale=f"Optique {c}", magasins=["Centre"])
            for c in codes
        ]

        # Break the middle one, and roll the other two back so there is real work to do.
        for client in (clients[0], clients[2]):
            call_command(
                "migrate", "magasins", "zero", database=alias_for(client.pk), verbosity=0
            )
        broken = clients[1]
        from django.db import connections

        if alias_for(broken.pk) in connections.settings:
            try:
                connections[alias_for(broken.pk)].close()
                del connections[alias_for(broken.pk)]
            except (AttributeError, KeyError):
                pass
        with maintenance_connection() as cur:
            drop_database_force(cur, broken.db_name)

        # --parallel 3, so this genuinely exercises the ProcessPoolExecutor rather than
        # the in-process --parallel 1 path. `migrate_fleet` runs in the parent, so
        # wrapping it is safe under spawn — wrapping `migrate_one` would not be, because
        # a local closure is not picklable.
        from plateforme.control_plane import fanout

        captured: dict = {}
        real_fleet = fanout.migrate_fleet

        def _capture(jobs, **kwargs):
            captured["results"] = real_fleet(jobs, **kwargs)
            return captured["results"]

        with patch.object(fanout, "migrate_fleet", _capture):
            exit_code, report = _run("--parallel", "3")

        assert exit_code != 0, f"a failed client did not make the run fail:\n{report}"

        # The work really crossed a process boundary. Without this, the test would pass
        # just as happily against a thread pool — and "failure isolation is structural"
        # is a claim about processes, not about hoping an exception is caught.
        worker_pids = {r["pid"] for r in captured["results"]}
        assert os.getpid() not in worker_pids, (
            f"migrate_one ran in the parent process ({os.getpid()}); the process pool "
            "was not used, so isolation rests on the except clause alone."
        )
        assert len(worker_pids) > 1, (
            f"all three clients ran in one child process: {worker_pids}. The pool is not "
            "actually parallel."
        )

        run = MigrationRun.objects.using("default").order_by("-pk").first()
        results = {
            r.client.code: r
            for r in MigrationRunResult.objects.using("default").filter(run=run)
        }

        assert len(results) == 3, (
            f"expected one result row per client, got {sorted(results)}. Two ok rows and "
            "a non-zero exit code look identical whether the broken client was attempted "
            "or skipped; the count is what distinguishes them."
        )
        assert results[codes[0]].status == "ok", results[codes[0]].error
        assert results[codes[2]].status == "ok", results[codes[2]].error
        assert results[codes[1]].status == "failed"
        assert results[codes[1]].error, "a failed client must carry its error text"

        # The survivors really did reach head, not merely avoid an exception.
        from plateforme.control_plane.schema_version import pending_plan

        for client in (clients[0], clients[2]):
            assert pending_plan(alias_for(client.pk)) == []

        assert run.failed == 1 and run.succeeded == 2
    finally:
        for code in codes:
            _destroy(code)


# --------------------------------------------------------------------------------------
# Cheap, and not slow
# --------------------------------------------------------------------------------------
@pytest.mark.django_db
def test_tenant03_check_mode_applies_nothing():
    """`--check` must never invoke `migrate`. It is a probe, and a deploy gate.

    Asserted against the child-process function rather than against the database, because
    the claim is about what the command *does*, and the cheapest honest way to say "it
    did not migrate" is that `call_command("migrate", ...)` was never reached.
    """
    from tests.factories import ClientFactory

    ClientFactory(code="chk-1", status=Client.ACTIVE, db_name="test_client_c000999")

    with patch("plateforme.control_plane.fanout.migrate_one") as worker:
        worker.side_effect = lambda job: {
            "pk": job["pk"],
            "code": job["code"],
            "db_name": job["db_name"],
            "host": job["host"],
            "status": "ok",
            "heads_before": {},
            "heads_after": {},
            "duration_seconds": 0.0,
            "error": "",
        }
        with patch("django.core.management.call_command") as inner:
            _run("--check", "--parallel", "1")
            migrate_calls = [
                c for c in inner.call_args_list if c.args and c.args[0] == "migrate"
            ]
            assert not migrate_calls, f"--check invoked migrate: {migrate_calls}"

    # And the jobs it built all carried check_only. The non-empty assertion first,
    # because `all([])` is True and a command that ran nothing would otherwise pass.
    assert worker.call_args_list, "the fan-out probed no client at all"
    assert all(call.args[0]["check_only"] for call in worker.call_args_list)


@pytest.mark.django_db
def test_tenant03_only_active_clients_are_migrated():
    """A half-provisioned client is invisible to the fan-out, exactly as it is to the router.

    FAILED, SUSPENDED, PENDING and DELETED clients are not merely skipped with a warning;
    they never enter the job list, so no connection to a half-built database is ever
    attempted (threat T-02-33).
    """
    from tests.factories import ClientFactory

    ClientFactory(code="act-1", status=Client.ACTIVE, db_name="test_client_c000901")
    ClientFactory(code="fail-1", status=Client.FAILED, db_name="test_client_c000902")
    ClientFactory(code="susp-1", status=Client.SUSPENDED, db_name="test_client_c000903")
    ClientFactory(code="pend-1", status=Client.PENDING)

    with patch("plateforme.control_plane.fanout.migrate_one") as worker:
        worker.side_effect = lambda job: {
            "pk": job["pk"],
            "code": job["code"],
            "db_name": job["db_name"],
            "host": job["host"],
            "status": "ok",
            "heads_before": {},
            "heads_after": {},
            "duration_seconds": 0.0,
            "error": "",
        }
        exit_code, report = _run("--parallel", "1")

    attempted = {call.args[0]["code"] for call in worker.call_args_list}
    assert attempted == {"act-1"}, (
        f"the fan-out attempted {sorted(attempted)}; only ACTIVE clients may be migrated."
    )
    assert exit_code == 0
    for code in ("fail-1", "susp-1", "pend-1"):
        assert code not in report


@pytest.mark.django_db
def test_tenant03_report_columns_are_stable_and_named():
    """The per-client table carries the exact columns a deploy diff is taken against.

    Named columns in a fixed order, so two deploys' output can be diffed. Not cosmetic:
    the output of this command is the artefact an operator keeps when something goes
    wrong at 2am.
    """
    from tests.factories import ClientFactory

    ClientFactory(code="col-1", status=Client.ACTIVE, db_name="test_client_c000904")

    with patch("plateforme.control_plane.fanout.migrate_one") as worker:
        worker.side_effect = lambda job: {
            "pk": job["pk"],
            "code": job["code"],
            "db_name": job["db_name"],
            "host": job["host"],
            "status": "ok",
            "heads_before": {"magasins": "0001_initial"},
            "heads_after": {"magasins": "0001_initial"},
            "duration_seconds": 0.12,
            "error": "",
        }
        _, report = _run("--parallel", "1")

    header = next(line for line in report.splitlines() if "code" in line)
    expected = ["code", "db_name", "host", "before", "after", "status", "duration", "error"]
    positions = [header.find(col) for col in expected]
    assert all(p >= 0 for p in positions), f"missing columns in header: {header!r}"
    assert positions == sorted(positions), (
        f"columns are out of order, so two runs cannot be diffed: {header!r}"
    )
