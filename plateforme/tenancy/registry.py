"""Runtime registration of a client's database connection.

# ==========================================================================================
# NEVER register tenant aliases outside a request, a task or an explicit command.
# NEVER pre-register in AppConfig.ready().
#
# `makemigrations` does:
#     aliases_to_check = connections if settings.DATABASE_ROUTERS else [DEFAULT_DB_ALIAS]
#     for alias in sorted(aliases_to_check):
#         connection = connections[alias]
#         ... loader.check_consistent_history(connection)   # opens a REAL connection
#
# This project sets DATABASE_ROUTERS, so `makemigrations` iterates every alias registered
# in that process and connects to each one. A developer who adds a `ready()` that
# pre-registers all clients would silently make `manage.py makemigrations` open a
# connection to every production database (Pitfall 4, threat T-02-22). Registration is
# lazy and request-driven precisely so that this never happens by accident.
# ==========================================================================================

Two findings shape the code below, and both contradict what every pre-2022 source says:

1. **The two `ConnectionHandler` helpers every pre-2022 runtime-registration snippet
   calls — the one that applied `DATABASES` defaults to a single alias, and its
   test-settings counterpart — do not exist.** Both were removed in Django 4.1, confirmed
   across nine tagged versions, when defaults moved into
   `ConnectionHandler.configure_settings()`, which runs once, lazily. (Their names are
   spelled out in `tests/test_tenancy_registry.py`, so a search for them lands on the
   test that proves the replacement works rather than on code that calls them.)
   A dict added to `connections.settings` afterwards gets no defaults and
   `DatabaseWrapper` raises a `KeyError` naming a `DATABASES` key from somewhere
   unrelated. The fix is `copy.deepcopy(settings.DATABASES["default"])`: that entry has
   already been through `configure_settings()`, so it carries every key the wrapper
   requires — including keys a future Django adds.

2. **To evict an alias, drop the wrapper, not the settings entry.** See `evict_alias`.

`connections.settings` **is** `settings.DATABASES` — the same object, because
`configure_settings()` mutates and returns what it was handed. Registering an alias
therefore also makes it visible in `settings.DATABASES`, which is why the TENANT-08
settings tests that iterate `settings.DATABASES` automatically cover runtime aliases too.

**No LRU eviction, deliberately.** At 300 aliases the cost is one `make_view_atomic` loop
and two `close_old_connections` loops per request — tens of microseconds — and a few tens
of MB for threads that actually touched every tenant. `evict_alias` exists as the correct
primitive; nothing calls it on a schedule. An LRU would add a failure mode for no
measured benefit.
"""

from __future__ import annotations

import copy
import threading

from django.conf import settings
from django.db import connections

TENANT_ALIAS_PREFIX = "tenant_"

# Not GIL paranoia — a bare `dict.__setitem__` is atomic today. The check-then-act below
# is racy regardless, and free-threaded CPython removes the GIL guarantee entirely. It
# costs nothing.
_REGISTER_LOCK = threading.Lock()


def alias_for(client_id: int) -> str:
    """The connection alias for a client primary key.

    Keep the prefix: `TenantRouter.allow_migrate` decides whether a business app may
    migrate to an alias by asking `is_tenant_alias(db)`, which keys off exactly this.
    """
    return f"{TENANT_ALIAS_PREFIX}{client_id}"


def register_client_database(
    *, alias: str, name: str, host: str, port: int | str, user: str, password: str
) -> str:
    """Register (or refresh) a client's connection settings. Idempotent; returns the alias.

    Safe to call on every request: when an alias is already registered with the same
    NAME and HOST the existing config object is kept untouched, so a wrapper already
    holding that `settings_dict` does not go stale.

    Opens no connection. `DatabaseWrapper` construction is lazy, which is what makes
    per-request registration cheap.
    """
    existing = connections.settings.get(alias)
    if existing is not None and existing["NAME"] == name and existing["HOST"] == host:
        return alias

    cfg = copy.deepcopy(settings.DATABASES["default"])
    cfg.update(
        NAME=name,
        HOST=host,
        PORT=str(port),
        USER=user,
        PASSWORD=password,
        # PgBouncer owns pooling. A non-zero value makes every worker thread hold a
        # client connection per alias it has ever touched (TENANT-08).
        CONN_MAX_AGE=0,
        # Explicitly False on a runtime alias — CLAUDE.md #12 forbids writing this key in
        # a settings *module*, where a later reader might "fix" the False to True. Here
        # it is a defensive pin on a dict built at runtime: make_view_atomic() iterates
        # every alias in connections.settings, so one truthy entry costs one transaction
        # per request per registered client.
        ATOMIC_REQUESTS=False,
        # Server-side cursors are local to a connection and stay open at the end of a
        # transaction under autocommit — exactly what transaction pooling recycles.
        DISABLE_SERVER_SIDE_CURSORS=True,
    )
    # `_connection_pools` is a class-level dict keyed by alias, so an inherited `pool`
    # option is one psycopg_pool per tenant per process (Pitfall 6).
    cfg["OPTIONS"] = {k: v for k, v in cfg["OPTIONS"].items() if k != "pool"}
    # A runtime alias is never a test alias and never mirrors another database.
    cfg["TEST"] = {**cfg.get("TEST", {}), "NAME": None, "MIRROR": None}

    with _REGISTER_LOCK:
        connections.settings[alias] = cfg
    return alias


def evict_alias(alias: str) -> None:
    """Close and drop this thread's wrapper for `alias`, leaving the settings entry.

    `connections[alias].close()` then `del connections[alias]`.
    `BaseConnectionHandler.__delitem__` does `delattr(self._connections, key)` — it drops
    only the thread-local `DatabaseWrapper`, which is exactly the eviction primitive
    wanted.

    # NEVER: del connections.settings[alias]
    #
    # `close_old_connections` is wired to both `request_started` and `request_finished`
    # and iterates `connections.all(initialized_only=True)`, which iterates
    # `iter(self.settings)`. Removing the settings entry makes a still-open wrapper
    # invisible to that loop, so its socket is never closed again and PostgreSQL
    # eventually answers `FATAL: too many connections` (threat T-02-21).
    """
    connections[alias].close()
    del connections[alias]
