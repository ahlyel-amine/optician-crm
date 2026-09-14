"""TENANT-04 — the tenant context, and the single highest-risk line in the system.

Worker threads and prefork worker processes are reused. Anything left in a `ContextVar`
outlives the request that set it, so the next request on that thread inherits it. That is
a cross-client read, which `CLAUDE.md` classifies as a security failure rather than a bug.

`CLAUDE.md` non-negotiable #8 as corrected by `02-RESEARCH.md`: the context is cleared
with `set(_UNSET)`, **never** with the token-based undo. Handed a token, a `ContextVar`
restores the *previous* value — `cv.set("LEAKED")`, `tok = cv.set("current")`, undo with
`tok`, and `"LEAKED"` is bound again — so a `finally` that undoes by token, running on a
thread that already carried a leak, faithfully re-installs it.
"""

import contextvars
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

import pytest
from django.conf import settings
from django.db import close_old_connections, connections
from django.test import RequestFactory

from conftest import TENANT_DBS
from domaine.magasins.models import Magasin
from plateforme.control_plane.models import Client
from plateforme.tenancy import middleware as middleware_module
from plateforme.tenancy import tasks as tasks_module

# ------------------------------------------------------------------------------------
# The context primitives
# ------------------------------------------------------------------------------------


def test_tenant04_clear_does_not_restore_an_earlier_value():
    """`clear()` unbinds. It does not restore whatever was bound before — that is the bug.

    `bind("tenant_a")`, then `bind("tenant_b")`, then `clear()`: the context must end
    **unbound**, not back on `tenant_a`.

    The second half of this test is the contrast, asserted explicitly so that nobody
    "simplifies" `clear()` into the token-based undo: on a raw `ContextVar`,
    `cv.set("LEAKED"); tok = cv.set("current")` followed by undoing `tok` leaves
    `"LEAKED"` bound. On a reused worker thread already carrying a leak from an earlier
    request, a `finally` written that way therefore re-installs the leak, faithfully and
    silently.

    `CLAUDE.md` non-negotiable #8, as corrected.
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
        "clear() left the context bound. Almost certainly it was implemented as a "
        "token-based undo, which restores the previous value instead of unbinding."
    )
    with pytest.raises(NoTenantBound):
        current_alias()

    # The contrast. This is what `clear()` must NOT do.
    raw = contextvars.ContextVar("leak_demo")
    raw.set("LEAKED")
    token = raw.set("current")
    raw.reset(token)
    assert raw.get() == "LEAKED", (
        "A ContextVar handed a token is expected to restore the *previous* value. If "
        "this assertion ever fails, CPython changed and the reasoning in context.py "
        "should be re-derived from scratch rather than adjusted."
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


# ------------------------------------------------------------------------------------
# The middleware
# ------------------------------------------------------------------------------------


class _Principal:
    """Stands in for Phase 3's authenticated user carrying a control-plane client id.

    Deliberately not a request header and not a query parameter: a tenant identity the
    caller can set freely is tenant spoofing (threat T-02-13).

    Phase 3 made this stand-in real rather than replacing it: `comptes.Utilisateur` carries
    a nullable `client` FK, so `user.client_id` is exactly what the middleware already
    read. The bearer-token claim an earlier draft of this docstring announced was never
    built — it would have authenticated inside DRF, after every middleware, leaving nothing
    bound. The middleware's contract is unchanged.
    """

    def __init__(self, client_id=None, authenticated=True):
        self.client_id = client_id
        self.is_authenticated = authenticated
        self.is_anonymous = not authenticated


#: pk -> static test alias, consulted by the patched `alias_for` below.
_ALIAS_BY_PK: dict[int, str] = {}


def _make_client(code: str, alias: str) -> Client:
    """An ACTIVE control-plane row standing for the client behind a static test alias.

    Its `db_name` is unique per client, as the real column is, and the alias it resolves
    to is recorded in `_ALIAS_BY_PK` for the `bound_to_test_aliases` fixture.
    """
    default_cfg = connections["default"].settings_dict
    client = Client.objects.using("default").create(
        code=code,
        raison_sociale=f"Optique {code}",
        status=Client.ACTIVE,
        db_name=f"optique_{code.replace('-', '_')}",
        db_host=settings.PG_ADMIN_HOST,
        db_port=settings.PG_ADMIN_PORT,
        db_user=default_cfg["USER"],
    )
    client.set_db_password(default_cfg["PASSWORD"])
    client.save(using="default")
    _ALIAS_BY_PK[client.pk] = alias
    return client


@pytest.fixture(autouse=True)
def bound_to_test_aliases():
    """Resolve every client to its static test alias instead of a runtime-created one.

    Two lines are redirected, and only two: `alias_for`, so a client binds `tenant_a` or
    `tenant_b`, and `register_client_database`, which becomes a no-op because those
    aliases are already declared in `config/settings/test.py`. The middleware's and the
    task's own logic — the entry guard, the ACTIVE-only resolution, the bind, the
    `finally: clear()` — runs untouched.

    Why redirect at all: Django's `TransactionTestCase` refuses connections to any alias
    outside the test's `databases` list, and an alias registered *during* the test is not
    in that list. Binding the static aliases keeps both tenant databases inside the
    per-test transaction, so this test rolls back like any other — and it is exactly the
    arrangement `.planning/TESTING.md` §3 prescribes: *"Runtime registration is tested
    separately, not used as the fixture."*

    Separately is `tests/test_tenancy_registry.py` and the 300-alias load check in
    `tests/test_connection_budget.py`, both of which exercise
    `register_client_database` for real.

    What is under test here is the **context lifecycle on a reused worker thread**, and
    all three of its load-bearing properties survive intact: one thread, two genuinely
    different client databases, and assertions on data.
    """
    _ALIAS_BY_PK.clear()
    patches = [
        mock.patch.object(module, "alias_for", lambda pk: _ALIAS_BY_PK[pk])
        for module in (middleware_module, tasks_module)
    ]
    patches += [
        mock.patch.object(
            module, "register_client_database", lambda **kwargs: kwargs["alias"]
        )
        for module in (middleware_module, tasks_module)
    ]
    for patch in patches:
        patch.start()
    try:
        yield
    finally:
        for patch in reversed(patches):
            patch.stop()
        _ALIAS_BY_PK.clear()


@pytest.mark.django_db(transaction=True, databases=TENANT_DBS)
def test_tenant04_context_does_not_leak_between_requests_on_one_thread():
    """Two requests, two different clients, **one reused thread** — and no leak.

    Three details decide whether this reproduces the bug. All three are asserted, not
    assumed:

    (a) **One thread, two requests.** A `ThreadPoolExecutor(max_workers=1)`, with both
        requests submitted to it — which is what gunicorn's gthread worker does. A fresh
        thread starts with an empty context and hides the bug permanently, so the test
        records the thread identity of every submission and asserts they are equal. A
        later refactor that accidentally spawns a thread per request fails here rather
        than passing silently.
    (b) **Different clients.** Same-client reuse passes while leaking, so request one is
        client A and request two is client B.
    (c) **Assert on data.** `is_bound() is False` catches a missing `clear()` but not a
        token-based undo that restored an older leak. Request two must see only client
        B's rows — and request three, which resolves **no** client, must be unable to
        read business data at all.

        Request three is what makes the data assertion bite. With `bind()` overwriting
        the contextvar, a missing `clear()` is invisible to a second *authenticated*
        request, because it rebinds anyway. The leak shows up on the next request that
        binds nothing — a health check, the login endpoint, the operator admin — which
        then inherits the previous client and reads their data. That is the production
        shape of this bug, and it is the one mutation testing confirms this test kills.

    `transaction=True` is mandatory here, and for the reason `.planning/TESTING.md` §4
    names: `TestCase` wraps the test in a transaction on the *main* thread's connection,
    and the pool thread holds a different connection, so it cannot see the uncommitted
    `Client` rows. Without it `resolve_client` returns `None`, nothing binds, and the
    test fails for a reason that has nothing to do with leaking. Observed, then fixed.

    The two clients bind the static `tenant_a` and `tenant_b` aliases — see the
    `bound_to_test_aliases` fixture for why, and for what that does and does not weaken.

    Threat T-02-15. Roadmap success criterion 4 is met by this test or not at all.
    """
    from plateforme.tenancy.context import NoTenantBound, clear, is_bound
    from plateforme.tenancy.middleware import TenantMiddleware

    client_a = _make_client("leak-a", "tenant_a")
    client_b = _make_client("leak-b", "tenant_b")

    seen_threads = []

    def _thread_identity():
        """`Thread.name`, not `get_ident()`.

        `threading.get_ident()` returns an OS-level id that is **recycled once a thread
        exits** — so a version of this test that starts and joins a fresh thread per
        request reports a single identity and passes against leaking code. Verified by
        mutation. `Thread.__init__` assigns names from a monotonic counter, so two
        distinct Thread objects never share one, while a reused pool worker keeps its
        name across submissions. That is exactly the distinction this assertion needs.
        """
        return threading.current_thread().name

    def view(request):
        if request.marker == "ANON":
            # No client resolved, so no business data may be reachable. A leaked context
            # would quietly answer with the previous client's rows instead of raising.
            try:
                return ("LEAKED", sorted(Magasin.objects.values_list("code", flat=True)))
            except NoTenantBound:
                return ("REFUSED", [])
        Magasin.objects.create(code=f"{request.marker}-MAG", nom=request.marker)
        return sorted(Magasin.objects.values_list("code", flat=True))

    middleware = TenantMiddleware(view)
    factory = RequestFactory()

    def serve(client, marker):
        seen_threads.append(_thread_identity())
        request = factory.get("/ventes/")
        request.user = _Principal(client_id=client.pk) if client else _Principal(
            authenticated=False
        )
        request.marker = marker
        try:
            return middleware(request)
        finally:
            # What Django's WSGI handler does at `request_finished`. The middleware must
            # not do this itself — `close_old_connections` is already wired to
            # `request_started` and `request_finished` — but calling the middleware
            # directly skips those signals, and a pool thread that keeps its connection
            # open blocks the test-database teardown.
            close_old_connections()

    def probe():
        seen_threads.append(_thread_identity())
        try:
            return is_bound()
        finally:
            close_old_connections()

    clear()
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        rows_a = pool.submit(serve, client_a, "A").result()
        rows_b = pool.submit(serve, client_b, "B").result()
        anonymous = pool.submit(serve, None, "ANON").result()
        still_bound = pool.submit(probe).result()
    finally:
        pool.shutdown(wait=True)

    assert len(set(seen_threads)) == 1, (
        f"The submissions ran on {len(set(seen_threads))} different threads. A "
        "fresh thread starts with an empty context and hides this bug permanently — the "
        "pool must reuse one thread, exactly as gunicorn's gthread worker does."
    )

    assert rows_a == ["A-MAG"]
    assert rows_b == ["B-MAG"], (
        f"Request two, for client B on the reused thread, saw {rows_b}. It must see only "
        "client B's rows. Seeing A-MAG means the context from request one survived, and "
        "client B just read another optician's data."
    )
    assert anonymous == ("REFUSED", []), (
        f"An unauthenticated request on the reused thread read {anonymous[1]}. It bound "
        "no client, so every business query on that path must raise NoTenantBound. "
        "Reading rows here means it inherited the previous request's client — one "
        "optician's data served on another's request."
    )
    assert still_bound is False, (
        "The worker thread is still bound after both requests finished. The next request "
        "this thread serves would inherit that client."
    )


@pytest.mark.django_db(databases=TENANT_DBS)
def test_tenant04_middleware_refuses_a_thread_that_arrives_already_bound(caplog):
    """The entry guard: a thread that arrives already bound is refused, loudly.

    Under `TENANCY_STRICT = True` — which `config/settings/test.py` sets — the middleware
    raises `TenantContextLeak` and logs at CRITICAL.

    The cheap negative test of the guard itself. A guard nobody tests is a guard that
    silently stops working, and this particular guard is the difference between a loud
    failure and a silent cross-client read.
    """
    from plateforme.tenancy.context import TenantContextLeak, bind, clear, is_bound
    from plateforme.tenancy.middleware import TenantMiddleware

    assert settings.TENANCY_STRICT is True

    middleware = TenantMiddleware(lambda request: "never reached")
    request = RequestFactory().get("/ventes/")
    request.user = _Principal(authenticated=False)

    bind("tenant_a")
    try:
        with caplog.at_level(logging.CRITICAL, logger="plateforme.tenancy"):
            with pytest.raises(TenantContextLeak):
                middleware(request)
    finally:
        clear()

    assert any(record.levelno == logging.CRITICAL for record in caplog.records), (
        "The leak guard did not log at CRITICAL. This is the highest-severity event the "
        "application can emit; it has to page someone, not appear in a debug log."
    )
    assert is_bound() is False, (
        "The guard raised but left the leaked context in place, so the next request on "
        "this thread inherits it anyway."
    )


@pytest.mark.django_db(databases=TENANT_DBS)
def test_tenant04_middleware_clears_on_the_exception_path():
    """`clear()` lives in a `finally`, so it runs on the exception path too.

    A `clear()` placed after `get_response(request)` instead of in a `finally` passes
    every happy-path test and leaks on every 500 — which is exactly when a leak is most
    likely, because the request that failed is the one that behaved unusually.
    """
    from plateforme.tenancy.context import clear, is_bound
    from plateforme.tenancy.middleware import TenantMiddleware

    client = _make_client("exc-a", "tenant_a")

    class Boom(RuntimeError):
        pass

    def exploding_view(request):
        raise Boom("the view failed")

    middleware = TenantMiddleware(exploding_view)
    request = RequestFactory().get("/ventes/")
    request.user = _Principal(client_id=client.pk)

    clear()
    with pytest.raises(Boom):
        middleware(request)

    assert is_bound() is False, (
        "The context survived an exception in the view. clear() must be in a finally, "
        "on every path."
    )


@pytest.mark.django_db(databases=TENANT_DBS)
def test_tenant04_middleware_ignores_an_unauthenticated_request():
    """Unauthenticated paths bind nothing, and that is correct rather than a gap.

    Health checks, the login endpoint and the operator admin have no client. Leaving the
    context unbound there means any business query on those paths raises — which is the
    behaviour we want, because such a query would have no client to belong to.
    """
    from plateforme.tenancy.context import clear, is_bound
    from plateforme.tenancy.middleware import TenantMiddleware

    captured = {}

    def view(request):
        captured["bound_during_view"] = is_bound()
        return "ok"

    middleware = TenantMiddleware(view)
    request = RequestFactory().get("/healthz")
    request.user = _Principal(authenticated=False)

    clear()
    assert middleware(request) == "ok"
    assert captured["bound_during_view"] is False
    assert is_bound() is False


@pytest.mark.django_db(databases=TENANT_DBS)
def test_tenant04_middleware_refuses_a_client_that_is_not_active():
    """Only ACTIVE clients resolve. A half-provisioned or suspended one is invisible.

    That invariant is what makes TENANT-05 true: provisioning is a state machine, not a
    transaction, so a client can sit in CREATING_DB or FAILED with a database that is
    incomplete. The router must never be pointed at one.
    """
    from plateforme.tenancy.context import clear, is_bound
    from plateforme.tenancy.middleware import TenantMiddleware

    client = _make_client("susp-a", "tenant_a")
    Client.objects.using("default").filter(pk=client.pk).update(status=Client.SUSPENDED)

    captured = {}
    middleware = TenantMiddleware(
        lambda request: captured.setdefault("bound", is_bound()) or "ok"
    )
    request = RequestFactory().get("/ventes/")
    request.user = _Principal(client_id=client.pk)

    clear()
    middleware(request)
    assert captured["bound"] is False, (
        "A SUSPENDED client resolved and was bound. Only ACTIVE clients are routable."
    )


def test_tenant04_middleware_never_reads_the_tenant_from_the_request():
    """Threat T-02-13: the client identity comes from the authenticated principal only.

    A tenant id taken from a header, a subdomain or an unsigned parameter is something
    the caller controls, and trusting it is tenant spoofing. The source file is read and
    checked rather than the behaviour, because the failure mode is a *new* line of code
    added later, not a wrong result today.
    """
    import inspect
    import re

    from plateforme.tenancy import middleware as middleware_module

    source = inspect.getsource(middleware_module)
    offenders = re.findall(
        r"request\.(?:META|headers|GET|POST)[^\n]*", source, flags=re.IGNORECASE
    )
    assert offenders == [], (
        f"The middleware reads the request for tenant resolution: {offenders}. "
        "The client must come from the authenticated principal only (T-02-13)."
    )


# ------------------------------------------------------------------------------------
# Celery
# ------------------------------------------------------------------------------------


@pytest.mark.django_db(databases=TENANT_DBS)
def test_tenant04_celery_task_without_client_id_fails_closed():
    """A task invoked with no `client_id` refuses to run. So does one naming a non-ACTIVE client.

    Two assertions, because they guard different things:

    * No `client_id` kwarg at all -> `NoTenantBound`. A task that ran with no context
      would either raise deep inside a query or, worse, read the control plane.
    * A `client_id` whose `Client.status != ACTIVE` -> also refused. A half-provisioned,
      failed or suspended client must not be routable; that invariant is what makes
      TENANT-05 true (threat T-02-18).
    """
    from plateforme.tenancy.context import NoTenantBound, clear

    from tests.tenant_tasks import count_magasins

    clear()
    with pytest.raises(NoTenantBound):
        count_magasins()

    pending = _make_client("task-pending", "tenant_a")
    Client.objects.using("default").filter(pk=pending.pk).update(status=Client.FAILED)
    with pytest.raises(Client.DoesNotExist):
        count_magasins(client_id=pending.pk)

    active = _make_client("task-active", "tenant_a")
    assert count_magasins(client_id=active.pk) == 0


@pytest.mark.django_db(databases=TENANT_DBS)
def test_tenant04_celery_task_clears_context_even_when_the_task_raises():
    """The task's context scope unwinds on the exception path, without relying on Celery.

    Celery dispatches `task_postrun` from inside a `finally:` in its tracer, so it does
    fire when a task raises — but our own scope must not depend on that, because the
    prefork worker reuses processes and a future Celery change would be a silent leak.
    """
    from plateforme.tenancy.context import clear, is_bound

    from tests.tenant_tasks import always_fails

    client = _make_client("task-boom", "tenant_a")

    clear()
    with pytest.raises(RuntimeError):
        always_fails(client_id=client.pk)

    assert is_bound() is False, (
        "The context survived a task that raised. TenantTask must scope the call so it "
        "unwinds on every path, rather than relying on a Celery signal."
    )
