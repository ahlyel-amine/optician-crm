"""TENANT-04 / TENANT-08 — the runtime connection registry.

Production registers a client's connection lazily, per request or per task. Doing that
correctly on a modern Django is not what the blog posts say, and these tests pin the
difference.

`connections.ensure_defaults()` and `connections.prepare_test_settings()` **do not
exist** — they were removed in Django 4.1, confirmed across nine tagged versions, and
every pre-2022 runtime-registration snippet still calls them. Defaults are now applied
once, lazily, inside `ConnectionHandler.configure_settings()`, so a dict added to
`connections.settings` afterwards receives no defaults at all and `DatabaseWrapper`
raises a `KeyError` naming a `DATABASES` key from somewhere unrelated.

The fix is to deep-copy the `default` entry, which has already been through
`configure_settings()` and therefore carries every key the wrapper needs — and which
stays correct when a future Django adds another key.

None of these tests touch a database.
"""

import contextlib

import pytest
from django.conf import settings
from django.db import connections

ALIAS = "tenant_7"


@pytest.fixture(autouse=True)
def _no_alias_leaks_between_tests():
    """Undo any alias a test registered, so one test cannot contaminate the next.

    Order matters and mirrors `evict_alias`: close the wrapper, drop the thread-local
    wrapper, and only then drop the settings entry. Removing the settings entry while a
    wrapper is still open is the socket leak these tests exist to prevent — safe here
    only because the wrapper is already gone.
    """
    before = set(connections.settings)
    yield
    for alias in set(connections.settings) - before:
        try:
            connections[alias].close()
        except Exception:  # noqa: BLE001 — cleanup must not mask the test's own failure
            pass
        if hasattr(connections._connections, alias):
            del connections[alias]
        connections.settings.pop(alias, None)


@contextlib.contextmanager
def _default_nested(*, options=None, test=None):
    """Temporarily swap `default`'s OPTIONS / TEST, restoring them **in place**.

    In place matters. `connections.settings` *is* `settings.DATABASES`, and the already
    constructed `default` wrapper holds that inner dict as its `settings_dict`. Rebinding
    `settings.DATABASES["default"]` to a fresh dict therefore restores what the *settings*
    see while leaving the live wrapper holding the mutated one — which surfaced as
    pytest-django failing to tear down the test databases, because psycopg was handed a
    fabricated connection option. Restore the individual keys, not the entry.
    """
    entry = settings.DATABASES["default"]
    saved = {key: entry[key] for key in ("OPTIONS", "TEST") if key in entry}
    if options is not None:
        entry["OPTIONS"] = options
    if test is not None:
        entry["TEST"] = test
    try:
        yield entry
    finally:
        for key, value in saved.items():
            entry[key] = value


def _register(**overrides):
    from plateforme.tenancy.registry import register_client_database

    params = {
        "alias": ALIAS,
        "name": "optique_c000007",
        "host": "pgbouncer.internal",
        "port": 6432,
        "user": "optique_u000007",
        "password": "s3cret-s3cret",
    }
    params.update(overrides)
    return register_client_database(**params)


def test_tenant04_alias_for_keeps_the_tenant_prefix():
    """`alias_for(pk)` is `tenant_<pk>`, and the prefix is load-bearing.

    `allow_migrate` decides whether a business app may migrate to an alias by asking
    `is_tenant_alias(db)`, which keys off exactly this prefix. Renaming the scheme
    without updating both would let business tables migrate somewhere they must not.
    """
    from plateforme.tenancy.registry import alias_for

    assert alias_for(7) == "tenant_7"


def test_tenant04_register_client_database_builds_a_complete_alias_config():
    """The registered config carries **every** key `default` carries. Set equality, not a sample.

    This is the assertion that catches the `ensure_defaults` removal. A config built by
    hand from a remembered list of keys passes a spot-check on `NAME` and `HOST` and then
    raises `KeyError: 'CONN_HEALTH_CHECKS'` from inside `DatabaseWrapper.__init__` — a
    key that did not exist before Django 4.1 and that nobody's hand-written list has.
    """
    _register()

    expected = set(settings.DATABASES["default"])
    actual = set(connections.settings[ALIAS])
    assert actual == expected, (
        f"Registered alias is missing {expected - actual} and has extra {actual - expected}. "
        "Build the config with copy.deepcopy(settings.DATABASES['default']) — it has "
        "already been through ConnectionHandler.configure_settings() and therefore "
        "carries every key DatabaseWrapper requires, including keys added by a future "
        "Django release."
    )

    # Constructing the wrapper must not raise, and must not open a socket.
    wrapper = connections[ALIAS]
    assert wrapper.settings_dict["NAME"] == "optique_c000007"
    assert wrapper.connection is None, (
        "Constructing a DatabaseWrapper opened a connection. Registration happens on "
        "every request; it must stay lazy."
    )


def test_tenant04_registered_alias_does_not_share_nested_dicts_with_default():
    """`copy.deepcopy`, not `{**default}`. Nothing nested may be shared by reference.

    A shallow copy hands every registered tenant the *same* nested objects as `default`,
    so mutating one alias's config silently rewrites `default`'s and all three hundred
    others'.

    The assertion deliberately reaches **two levels deep**, and that matters: a shallow
    copy today happens to look correct at depth one, because `register_client_database`
    reassigns `OPTIONS` and `TEST` to freshly-built dicts on its way past. So a test that
    only checks `cfg["OPTIONS"] is not default["OPTIONS"]` passes against `{**default}`
    — verified by mutating the implementation. Depth two is where the difference is real,
    and depth two is exactly where a future Django key or a project-specific nested
    option will live.

    The final behavioural assertion is the one that cannot be gamed: mutate the registered
    config and prove `default` did not move.
    """
    with _default_nested(
        options={"connect_timeout": 5, "nested_option": {"shared": "no"}},
        test={"NAME": None, "nested_test_option": {"shared": "no"}},
    ):
        _register()
        cfg = connections.settings[ALIAS]
        default = settings.DATABASES["default"]

        for key in ("OPTIONS", "TEST"):
            assert cfg[key] is not default[key], (
                f"{key} is the same object on the registered alias and on default."
            )

        assert cfg["OPTIONS"]["nested_option"] is not default["OPTIONS"]["nested_option"], (
            "OPTIONS['nested_option'] is shared by reference with default. The config was "
            "built with a shallow copy; use copy.deepcopy."
        )
        assert (
            cfg["TEST"]["nested_test_option"] is not default["TEST"]["nested_test_option"]
        ), "TEST['nested_test_option'] is shared by reference with default."

        # Behavioural form: mutating the tenant's config must not move default's.
        cfg["OPTIONS"]["nested_option"]["shared"] = "MUTATED"
        assert default["OPTIONS"]["nested_option"]["shared"] == "no", (
            "Mutating the registered alias's nested OPTIONS changed default's too. "
            "Every alias registered from that point on would inherit the mutation."
        )


def test_tenant08_registered_alias_strips_the_pool_option_and_pins_conn_max_age():
    """TENANT-08 applies to runtime aliases too, and `pool` must never be inherited.

    `DatabaseWrapper._connection_pools` is a **class-level** dict keyed by alias, so an
    inherited `OPTIONS["pool"]` means one `psycopg_pool` per tenant per process. That is
    precisely the Prisma failure mode already in CLAUDE.md's Rejected table: memory and
    connection count both scale with client count instead of with traffic.

    Also asserts the other three TENANT-08 invariants on the built config, because a
    runtime alias that quietly differs from `default` is the drift the settings tests
    cannot see.
    """
    with _default_nested(options={"pool": True, "connect_timeout": 5}):
        _register()
        cfg = connections.settings[ALIAS]

        assert "pool" not in cfg["OPTIONS"], (
            "The registered alias inherited OPTIONS['pool'] from default. "
            "_connection_pools is class-level and keyed by alias — that is one "
            "psycopg_pool per tenant per process (TENANT-08, Pitfall 6)."
        )
        assert cfg["OPTIONS"]["connect_timeout"] == 5, (
            "Stripping `pool` must not throw away the rest of OPTIONS."
        )
        assert cfg["CONN_MAX_AGE"] == 0, "PgBouncer owns pooling, not Django."
        assert cfg["DISABLE_SERVER_SIDE_CURSORS"] is True
        assert bool(cfg.get("ATOMIC_REQUESTS", False)) is False, (
            "ATOMIC_REQUESTS is truthy on a runtime alias. make_view_atomic() iterates "
            "every alias in connections.settings — with 300 clients registered that is "
            "300 transactions per request (CLAUDE.md #12)."
        )


def test_tenant04_eviction_drops_the_wrapper_not_the_settings_entry():
    """`evict_alias` closes the wrapper and drops it — and leaves `connections.settings` alone.

    `del connections.settings[alias]` looks like the way to unregister an alias and it
    orphans an open socket permanently. `close_old_connections`, wired to both
    `request_started` and `request_finished`, iterates
    `connections.all(initialized_only=True)`, which iterates `iter(self.settings)`. Remove
    the settings entry and the still-open `DatabaseWrapper` in the thread-local becomes
    invisible to that loop — the connection is never closed again, and PostgreSQL
    eventually answers `FATAL: too many connections` (threat T-02-21).

    `BaseConnectionHandler.__delitem__` does `delattr(self._connections, key)`, which
    drops only the thread-local wrapper. That is exactly the primitive wanted.
    """
    from plateforme.tenancy.registry import evict_alias

    _register()
    connections[ALIAS]  # force the thread-local wrapper into existence
    # `hasattr(connections._connections, alias)` is exactly what Django's own
    # `__getitem__` / `__delitem__` / `connections.all(initialized_only=True)` use.
    assert hasattr(connections._connections, ALIAS)

    evict_alias(ALIAS)

    assert ALIAS in connections.settings, (
        "evict_alias removed the settings entry. That orphans the open socket, because "
        "close_old_connections iterates connections.settings to find wrappers to close."
    )
    assert not hasattr(connections._connections, ALIAS), (
        "evict_alias left the thread-local wrapper in place, so nothing was evicted."
    )


def test_tenant04_register_is_idempotent():
    """Registering the same alias twice does not rebuild the config. It runs on every request.

    Identity, not equality: a rebuilt config would be a new object, and any wrapper
    already holding the old `settings_dict` would keep using stale values.
    """
    _register()
    first = connections.settings[ALIAS]

    _register()
    assert connections.settings[ALIAS] is first, (
        "register_client_database rebuilt an identical config. It is called on every "
        "request; the check-then-act must short-circuit when NAME and HOST already match."
    )

    # A genuine change (the client moved to another PostgreSQL instance) must take effect.
    _register(host="other-pgbouncer.internal")
    assert connections.settings[ALIAS]["HOST"] == "other-pgbouncer.internal"
