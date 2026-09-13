"""Which client's database this piece of work belongs to. The whole security model.

`contextvars`, not `threading.local`: a `ContextVar` works across `asyncio` tasks and
`sync_to_async` boundaries, and it is what asgiref itself uses.

**The token-based undo method is banned in this module, and in this package** — a grep
for it across `plateforme/tenancy/` must return nothing. Handed a token, a `ContextVar`
restores the *previous* value; it does not clear. Reproduced on CPython::

    cv.set("LEAKED")
    tok = cv.set("current")
    cv  # ... undo that set with tok
    cv.get()   ->  "LEAKED",  not unset

Worker threads and prefork worker processes are reused, so a `finally: reset(token)` on a
thread that already carried a leak from an earlier request faithfully re-installs that
leak. Clearing is therefore `_current.set(_UNSET)`, paired with an assert-unset-on-entry
guard in the middleware so a leak is loud rather than silent. This corrects
`CLAUDE.md` non-negotiable #8's wording, not its intent.

**One distinction not to unify.** `tenant_context` *does* restore the previous value on
exit, and that is right: a nested scope is a lexical construct whose caller genuinely had
a valid alias bound. Request and task teardown is the opposite situation — the thread is
about to be handed to a stranger — so it clears. Two different operations that happen to
look similar; keep them apart.
"""

from __future__ import annotations

import contextvars


class NoTenantBound(RuntimeError):
    """Database access was attempted with no client bound. Refused, not defaulted."""


class TenantContextLeak(RuntimeError):
    """A worker thread or process arrived already carrying a previous client's context."""


class CrossTenantAccess(RuntimeError):
    """An object loaded under one client was used while a different client was bound."""


# A unique sentinel rather than None: None is a value a caller could plausibly bind by
# accident, and "explicitly bound to nothing" must be indistinguishable from unbound.
_UNSET = object()

_current: contextvars.ContextVar = contextvars.ContextVar("tenant_alias", default=_UNSET)


def current_alias() -> str:
    """The bound alias, or raise `NoTenantBound`.

    Raising, rather than returning `None`, is the whole point. Django's
    `ConnectionRouter._router_func` falls through to `DEFAULT_DB_ALIAS` when every router
    declines, so a router that returns `None` reads the control-plane database with
    another client's query. An exception raised inside `db_for_read` / `db_for_write`
    propagates untouched — `_router_func` swallows only `AttributeError`, and only for a
    missing method.
    """
    alias = _current.get()
    if alias is _UNSET or alias is None:
        raise NoTenantBound(
            "No client is bound to this context — database access refused. "
            "Requests bind through TenantMiddleware, tasks through TenantTask, and "
            "commands and tests through the tenant_context scope."
        )
    return alias


def is_bound() -> bool:
    """True when a client is bound. Used by the middleware's entry guard."""
    return _current.get() is not _UNSET


def bind(alias: str) -> None:
    """Bind a client alias to the current context."""
    _current.set(alias)


def clear() -> None:
    """Unbind. **Never** `reset(token)` — see this module's docstring."""
    _current.set(_UNSET)


class tenant_context:
    """Explicit tenant scope for management commands, Celery tasks and tests.

    Restores the enclosing scope's value on exit, so nesting works. A scope entered from
    unbound therefore exits to unbound, which is what makes it safe as the outermost
    construct in a task.
    """

    __slots__ = ("alias", "prev")

    def __init__(self, alias: str):
        self.alias = alias

    def __enter__(self) -> str:
        self.prev = _current.get()
        _current.set(self.alias)
        return self.alias

    def __exit__(self, *exc_info) -> bool:
        # Restore, not clear: nested scopes DO want the previous value back. Request and
        # task teardown calls clear() instead.
        _current.set(self.prev)
        return False
