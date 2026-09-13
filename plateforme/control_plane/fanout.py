"""TENANT-03 — running one migration against N client databases without losing any of them.

**Processes, not threads.** `call_command("migrate", database=alias)` is I/O-bound, so a
thread pool would give similar throughput. The process boundary is not about throughput —
it is what makes *"client 47 failing does not stop clients 48 through 300"* structurally
true rather than hopefully true. An unhandled exception, a `sys.exit()` from deep inside
Django's error handling, or a migration graph corrupted in memory cannot escape a child
process. In a thread they all can.

The start method is **spawn**, explicitly, on every platform. `fork` would hand the child
a copy of every open psycopg socket and every lock held at the moment of the fork, which
is a corruption source rather than an optimisation. A spawned child builds its own
`connections` registry from scratch, which is why `migrate_one` calls `django.setup()`
first.

**Nothing at module level may import a Django model.** A spawned child imports this module
to resolve the function it is asked to run, and that happens before `django.setup()` — a
model import here would fail with `AppRegistryNotReady` in a child process, which is a
miserable thing to debug. Every Django import in this file is inside a function.

**The child never touches the control plane.** The parent reads `Client`, composes the
job, and writes every `MigrationRunResult`. Two reasons: a child that called
`django.setup()` and then read `Client` from `default` would read the settings module's
`NAME`, which under pytest is the *development* control plane rather than the test one —
so the fan-out would quietly migrate real clients during a test run. And the result dict
crosses a pickle boundary, so keeping it to primitives is a rule the job dict should obey
too.
"""

from __future__ import annotations

import multiprocessing
import time
from concurrent.futures import ProcessPoolExecutor

#: Each concurrent migration holds one or two connections. DDL locks are per-database, so
#: two `migrate` runs against two different databases do not contend (`02-RESEARCH.md`
#: assumption A4). If that turns out to be wrong the failure mode is slowness, not
#: corruption, and the fix is `--parallel 1`.
DEFAULT_PARALLEL = 4


def build_job(client, *, check_only: bool) -> dict:
    """The picklable description of one client's migration. Runs in the **parent**.

    `connection_params(direct=True)` — migrations go direct to PostgreSQL, never through
    PgBouncer. They run long DDL transactions, which is the opposite of what a transaction
    pool is for, and DDL session state left on a pooled server connection is handed to the
    next client (threat T-02-32).
    """
    return {
        "pk": client.pk,
        "code": client.code,
        "db_name": client.db_name,
        "host": client.db_host,
        "check_only": check_only,
        "connection": client.connection_params(direct=True),
    }


def migrate_one(job: dict) -> dict:
    """Migrate (or probe) one client. **Runs in a child process.**

    Returns a plain dict of primitives only — it crosses a process boundary by pickle, so
    no model instances, no exceptions, no connections.
    """
    import os

    import django

    # Each child has its own `connections` registry and must build it.
    django.setup()

    from plateforme.control_plane.schema_version import pending_plan, read_applied_heads
    from plateforme.tenancy.registry import register_client_database

    started = time.monotonic()
    result = {
        "pk": job["pk"],
        "code": job["code"],
        "db_name": job["db_name"],
        "host": job["host"],
        # Evidence, not telemetry. "Failure isolation is structural" is a claim about
        # process boundaries, and a test that does not check the work actually crossed one
        # would pass just as happily against a thread pool.
        "pid": os.getpid(),
        "status": "failed",
        "heads_before": {},
        "heads_after": {},
        "duration_seconds": 0.0,
        "error": "",
    }

    try:
        alias = register_client_database(**job["connection"])
        result["heads_before"] = read_applied_heads(alias)

        if job["check_only"]:
            # Probe only. `--check` is a deploy gate and must apply nothing.
            result["status"] = "behind" if pending_plan(alias) else "ok"
            result["heads_after"] = result["heads_before"]
        else:
            from django.core.management import call_command

            call_command("migrate", database=alias, interactive=False, verbosity=0)
            result["heads_after"] = read_applied_heads(alias)
            result["status"] = "ok"
    except Exception as exc:
        # NOTE: no re-raise. Client 47 failing must not stop clients 48..300.
        # This is the single line the requirement turns on; an exception escaping here
        # would propagate through the executor and abort the fleet.
        result["status"] = "failed"
        result["error"] = repr(exc)[:2000]
    finally:
        result["duration_seconds"] = round(time.monotonic() - started, 3)

    return result


def migrate_fleet(
    jobs: list[dict],
    *,
    parallel: int = DEFAULT_PARALLEL,
    fail_fast: bool = False,
) -> list[dict]:
    """Run `migrate_one` over every job, `parallel` at a time. Never raises for a client.

    `fail_fast` is **off by default**, because the requirement is the opposite: one
    client's failure must not stop the others. When it is on, no *new* work is submitted
    after the first failure, but results already in flight are still collected — a
    half-reported run would be worse than either extreme.
    """
    if not jobs:
        return []

    if parallel <= 1:
        # Still the same function, still the same result shape, just in this process.
        # Worth having as a real path: `--parallel 1` is the documented escape hatch if
        # cross-database lock contention ever turns out to be real.
        results = []
        for job in jobs:
            outcome = migrate_one(job)
            results.append(outcome)
            if fail_fast and outcome["status"] == "failed":
                break
        return results

    ctx = multiprocessing.get_context("spawn")
    results: list[dict] = []
    with ProcessPoolExecutor(max_workers=parallel, mp_context=ctx) as pool:
        pending = iter(jobs)
        futures = {}
        stop_submitting = False

        def _submit_next():
            try:
                job = next(pending)
            except StopIteration:
                return False
            futures[pool.submit(migrate_one, job)] = job
            return True

        for _ in range(parallel):
            if not _submit_next():
                break

        while futures:
            from concurrent.futures import FIRST_COMPLETED, wait

            done, _ = wait(list(futures), return_when=FIRST_COMPLETED)
            for future in done:
                futures.pop(future)
                outcome = future.result()
                results.append(outcome)
                if fail_fast and outcome["status"] == "failed":
                    stop_submitting = True
            if not stop_submitting:
                for _ in range(parallel - len(futures)):
                    if not _submit_next():
                        break

    results.sort(key=lambda r: r["code"])
    return results
