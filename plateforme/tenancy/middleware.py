"""`TenantMiddleware` — the request half of the tenant context lifecycle.

Three rules, each of which is a line of code and a security property:

1. **Resolve the client from the authenticated principal, never from the request.** A
   tenant identity the caller can set — a header, a subdomain, a query parameter — is
   tenant spoofing (threat T-02-13). The source is the principal's control-plane
   `client_id` and nothing else. A subdomain may later become a *secondary* signal
   validated **against** it, never instead of it.

2. **Clear in a `finally`, on every path.** `clear()` after `get_response(request)`
   passes every happy-path test and leaks on every 500.

3. **Assert unset on entry.** Worker threads are reused. If this thread arrives already
   bound, something failed to clear, and the correct response is a CRITICAL log and —
   under `TENANCY_STRICT` — a refusal. This is not defensive clutter: it is the
   difference between a loud failure and a silent cross-client read (threat T-02-15).

This middleware **must** sit after `AuthenticationMiddleware`, because resolving the
client depends on the authenticated principal, and before any view.

**Phase 3 authenticates with session cookies.** An earlier version of this docstring
announced a signed bearer token carrying a `client_id` claim. That plan was reversed
before any of it was built, and the reason is this very file: `AuthenticationMiddleware`
populates `request.user` from the session *before* this middleware runs, whereas DRF's
authentication classes run inside `APIView.initial()`, *after* every middleware. With a
token authenticated by DRF, `request.user` here would be `AnonymousUser` on every request,
nothing would bind, and the first business query of every request would raise
`NoTenantBound`. Sessions cost this layer zero lines.
"""

from __future__ import annotations

import logging

import sentry_sdk
from django.conf import settings

from plateforme.tenancy.context import TenantContextLeak, bind, clear, is_bound
from plateforme.tenancy.registry import alias_for, register_client_database

logger = logging.getLogger("plateforme.tenancy")


def resolve_client(request):
    """The ACTIVE control-plane `Client` this request belongs to, or `None`.

    Returns `None` for unauthenticated endpoints, health checks and the operator admin.
    Leaving the context unbound there is correct: any business query on those paths
    *should* raise, because it has no client to belong to.

    Only ACTIVE clients resolve. A PENDING, CREATING_DB, MIGRATING, SEEDING, FAILED or
    SUSPENDED client is invisible to the router — provisioning is a state machine rather
    than a transaction, so a non-ACTIVE client may have a database that is incomplete.
    That invariant is what makes TENANT-05 true.

    Phase 3 changes nothing here. It was once expected to replace the lookup below with a
    claim carried in a bearer token; it does not, for the reason given in the module
    docstring. `comptes.Utilisateur.client` is named `client` precisely so that
    `user.client_id` keeps meaning what this function already assumes. The contract is
    unchanged and always was: an authenticated, server-verified identity in, a `Client`
    row out.
    """
    from plateforme.control_plane.models import Client

    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None

    # The client id comes from the authenticated principal. It is deliberately NOT read
    # from anything the caller controls (T-02-13).
    client_id = getattr(user, "client_id", None)
    if client_id is None:
        return None

    return (
        Client.objects.using("default")
        .filter(pk=client_id, status=Client.ACTIVE)
        .first()
    )


class TenantMiddleware:
    """MUST sit after AuthenticationMiddleware and before any view."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_bound():
            # A previous request on this worker thread failed to clear. Loud, not silent:
            # this is the highest-risk bug in the system.
            logger.critical(
                "tenant context leaked onto worker thread",
                extra={"path": getattr(request, "path", "?")},
            )
            clear()
            if settings.TENANCY_STRICT:
                raise TenantContextLeak(
                    "A tenant context survived a previous request on this worker "
                    "thread. Refusing to serve, because the alternative is serving one "
                    "optician's data to another."
                )

        try:
            client = resolve_client(request)
            if client is not None:
                register_client_database(**client.connection_params())
                bind(alias_for(client.pk))
                # The tag is wanted; the event body is scrubbed by
                # plateforme.tenancy.telemetry.before_send. Health data under law 09-08
                # must not ride along in the body (threat T-02-17).
                sentry_sdk.set_tag("client", client.code)
            return self.get_response(request)
        finally:
            clear()
