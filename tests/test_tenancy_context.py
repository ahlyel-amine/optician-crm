"""TENANT-04 — the tenant context, and the single highest-risk line in the system.

Worker threads and prefork worker processes are reused. Anything left in a `ContextVar`
outlives the request that set it, so the next request on that thread inherits it. That is
a cross-client read, which `CLAUDE.md` classifies as a security failure rather than a bug.

`CLAUDE.md` non-negotiable #8 as corrected by `02-RESEARCH.md`: the context is cleared
with `set(_UNSET)`, **never** `reset(token)`. `ContextVar.reset(token)` restores the
*previous* value — `cv.set("LEAKED"); tok = cv.set("current"); cv.reset(tok)` leaves
`"LEAKED"` bound — so a `finally: reset(token)` on a thread already carrying a leak
faithfully re-installs it.

All imports of `plateforme.tenancy.*` are function-local so that a missing module is a
per-test failure rather than a collection error.
"""

import contextvars

import pytest


def test_tenant04_clear_does_not_restore_an_earlier_value():
    """`clear()` unbinds. It does not restore whatever was bound before — that is the bug.

    `bind("tenant_a")`, then `bind("tenant_b")`, then `clear()`: the context must end
    **unbound**, not back on `tenant_a`.

    The second half of this test is the contrast, asserted explicitly so that nobody
    "simplifies" `clear()` back into `reset(token)`: on a raw `ContextVar`,
    `cv.set("LEAKED"); tok = cv.set("current"); cv.reset(tok)` leaves `"LEAKED"` bound.
    On a reused worker thread already carrying a leak from an earlier request, a
    `finally: reset(token)` therefore re-installs that leak, faithfully and silently.

    `CLAUDE.md` non-negotiable #8, as corrected: `set(_UNSET)` plus an
    assert-unset-on-entry guard, never `reset(token)`.
    """
    from plateforme.tenancy.context import (
        NoTenantBound,
        bind,
        clear,
        current_alias,
        is_bound,
    )

    bind("tenant_a")
    bind("tenant_b")
    clear()

    assert is_bound() is False, (
        "clear() left the context bound. Almost certainly it was implemented as "
        "reset(token), which restores the previous value instead of unbinding."
    )
    with pytest.raises(NoTenantBound):
        current_alias()

    # The contrast. This is what `clear()` must NOT do.
    raw = contextvars.ContextVar("leak_demo")
    raw.set("LEAKED")
    token = raw.set("current")
    raw.reset(token)
    assert raw.get() == "LEAKED", (
        "ContextVar.reset(token) is expected to restore the *previous* value. If this "
        "assertion ever fails, CPython changed and the reasoning in context.py should "
        "be re-derived from scratch rather than adjusted."
    )


def test_tenant04_current_alias_raises_when_unbound():
    """`current_alias()` raises on a fresh context. Not None, not "default".

    Returning `None` would make `db_for_read` return `None`, and Django's
    `ConnectionRouter._router_func` falls through to `DEFAULT_DB_ALIAS` when every router
    declines — a silent read of the control-plane database with another client's query
    (threat T-02-14). Returning `"default"` would be the same leak, written down.
    """
    from plateforme.tenancy.context import NoTenantBound, clear, current_alias, is_bound

    clear()
    assert is_bound() is False
    with pytest.raises(NoTenantBound):
        current_alias()


def test_tenant04_tenant_context_scope_restores_the_outer_scope():
    """Nested `tenant_context` scopes restore the outer alias; the outermost exits unbound.

    This is the one place where restoring the previous value is *correct*, and the
    distinction from request teardown is worth stating: a nested scope is a lexical
    construct whose caller genuinely had a valid alias bound, whereas a request's
    `finally` runs on a thread that is about to be handed to a stranger.
    """
    from plateforme.tenancy.context import clear, current_alias, is_bound, tenant_context

    clear()
    with tenant_context("tenant_a"):
        assert current_alias() == "tenant_a"
        with tenant_context("tenant_b"):
            assert current_alias() == "tenant_b"
        assert current_alias() == "tenant_a", (
            "Exiting a nested scope did not restore the outer alias."
        )
    assert is_bound() is False, (
        "Exiting the outermost scope left the context bound. The scope entered from "
        "unbound, so it must exit to unbound."
    )


@pytest.mark.pending
@pytest.mark.tenancy
def test_tenant04_context_does_not_leak_between_requests_on_one_thread():
    """Two requests, two different clients, **one reused thread** — and no leak.

    Three details decide whether this reproduces the bug. Get all three right or the
    test is theatre:

    (a) **One thread, two requests.** `ThreadPoolExecutor(max_workers=1)`, both requests
        submitted to it. A fresh thread starts with an empty context and hides the bug
        permanently — verified.
    (b) **The two requests must be for *different* clients.** Same-client reuse passes
        while leaking.
    (c) **Assert on data, not on the variable.** `assert is_bound() is False` catches a
        missing `clear()`, but does *not* catch a `reset(token)` that restored an older
        leak. Request two must return only client B's rows.

    Structure: request one, through the middleware for client A, creates and reads a
    distinguishable `Magasin`; request two on the same pool thread for client B asserts
    it sees only B's rows; a third submission then asserts `is_bound()` is False on that
    same thread.

    Threat T-02-15. Roadmap success criterion 4 is met by this test or not at all.

    Pending: needs the context, the registry and `TenantMiddleware`.
    """
    pytest.fail("pending: implemented by plan 02-03")


@pytest.mark.pending
def test_tenant04_middleware_refuses_a_thread_that_arrives_already_bound():
    """The entry guard: a thread that arrives already bound is refused, loudly.

    Bind an alias on the calling thread, invoke the middleware, and assert it raises
    `TenantContextLeak` under `TENANCY_STRICT = True` (which `config/settings/test.py`
    sets) and logs at CRITICAL.

    The cheap negative test of the guard itself. A guard nobody tests is a guard that
    silently stops working, and this particular guard is the difference between a loud
    failure and a silent cross-client read.

    Pending: needs `TenantMiddleware`.
    """
    pytest.fail("pending: implemented by plan 02-03")


@pytest.mark.pending
def test_tenant04_middleware_clears_on_the_exception_path():
    """`clear()` lives in a `finally`, so it runs on the exception path too.

    Make the view raise; assert the exception propagates **and** `is_bound()` is False
    afterwards. A `clear()` placed after `get_response(request)` instead of in a
    `finally` passes every happy-path test and leaks on every 500.

    Pending: needs `TenantMiddleware`.
    """
    pytest.fail("pending: implemented by plan 02-03")


@pytest.mark.pending
def test_tenant04_celery_task_without_client_id_fails_closed():
    """A task invoked with no `client_id` refuses to run. So does one naming a non-ACTIVE client.

    Two assertions, because they guard different things:

    * No `client_id` kwarg at all -> `NoTenantBound`. A task that ran with no context
      would either raise deep inside a query or, worse, read the control plane.
    * A `client_id` whose `Client.status != ACTIVE` -> also refused. A half-provisioned,
      failed or suspended client must not be routable; that invariant is what makes
      TENANT-05 true (threat T-02-18).

    Pending: needs `plateforme.tenancy.tasks.TenantTask`.
    """
    pytest.fail("pending: implemented by plan 02-03")


@pytest.mark.pending
def test_tenant04_celery_task_clears_context_even_when_the_task_raises():
    """The task's context scope unwinds on the exception path, without relying on Celery.

    Invoke a task that raises inside `tenant_context`; assert the exception propagates
    and the context is unbound afterwards.

    Celery dispatches `task_postrun` from inside a `finally:` in its tracer, so it does
    fire when a task raises — but our own scope must not depend on that, because the
    prefork worker reuses processes and a future Celery change would be a silent leak.

    Pending: needs `plateforme.tenancy.tasks.TenantTask`.
    """
    pytest.fail("pending: implemented by plan 02-03")
