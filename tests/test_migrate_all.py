"""TENANT-03 — migration fan-out across every client database.

With one database per client, a deploy is not "run migrate". It is "run migrate against
N databases, and know which of them did not make it". The two things that matter are
therefore reporting and failure isolation, and both are tested here.

`--check` mode is the CI/deploy gate: it probes every ACTIVE client, applies nothing, and
exits 1 if any client is behind. Recorded `applied_heads` and probed reality can diverge
(someone ran `migrate` by hand), so "recorded: behind" and "probed: behind" are different
facts and the command must keep them distinguishable.
"""

import pytest


@pytest.mark.pending
@pytest.mark.slow
def test_tenant03_migration_fanout_reports_which_clients_are_behind():
    """`migrate_all --check` names the clients that are behind, and exits non-zero.

    Provision two clients, roll one back by a migration, then run `migrate_all --check`
    and assert: the behind client appears in the report with its `before` head, the
    up-to-date client is reported as current, and the command exits 1.

    Exit code matters as much as the output — this is what a deploy pipeline gates on,
    and a command that prints a warning and exits 0 gates nothing.

    Pending: needs the `migrate_all` command.
    """
    pytest.fail("pending: implemented by plan 02-05")


@pytest.mark.pending
@pytest.mark.slow
def test_tenant03_one_client_failing_does_not_stop_the_others():
    """Client 47 failing must not stop clients 48 through 300. Explicitly required.

    Provision three clients, break one (drop its database, or leave it at an
    inconsistent history), run `migrate_all`, and assert the other two reached head and
    are reported `ok`, the broken one is reported `failed` with its error, and the
    overall exit code is non-zero.

    The fan-out uses a **process** pool rather than a thread pool for exactly this: a
    process boundary makes failure isolation structurally true rather than hopefully
    true. An unhandled exception, a `sys.exit` from inside Django's error handling, or a
    corrupted in-memory migration graph cannot escape a child process. `--fail-fast`
    exists but is off by default.

    Pending: needs the `migrate_all` command.
    """
    pytest.fail("pending: implemented by plan 02-05")
