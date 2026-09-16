"""Root URLconf.

Only the operator admin so far. Business routes are mounted by Phases 3 onward, behind
the API.

**What keeps the admin operator-only is not this URL.** An earlier version of this
docstring claimed that `resolve_client` yields no client for this path by design. That was
never true and is now actively misleading: resolution is a function of the authenticated
principal's `client_id`, not of the path, and from Phase 3 on there are real users
carrying one — so a client's account reaching `/admin/` would bind its tenant perfectly
well. Mounting the admin elsewhere, or not mounting it, would change nothing.

What actually keeps it shut is two layers, neither of them a route:

1. `comptes.Utilisateur`'s CHECK constraint `un_utilisateur_client_n_est_jamais_operateur`
   — PostgreSQL refuses to store a client-bound account with `is_staff` or `is_superuser`;
2. `AdminOperateurSite.has_permission` — requires `is_active`, `is_superuser` **and**
   `client_id is None`.

The tenant context does stay unbound for an operator's admin request, because an operator
belongs to no client. A business query reached from an admin page therefore still raises,
which is the fail-closed router doing its job — and it is why no business model is ever
registered in the admin (PERM-06).
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # PERM-01. Same-origin with the SPA, which is what makes session cookies work with
    # no CORS configuration on either side: `web/` proxies `/api` to this application.
    path("api/auth/", include("plateforme.comptes.urls")),
]
