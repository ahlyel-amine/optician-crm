> **⚠️ TWO CORRECTIONS — decided after this research was written.**
>
> 1. **§4's grant model is superseded.** `DroitAccorde(utilisateur, code)` carries no magasin
>    dimension, which reverses CLAUDE.md **#13**. Grants are stored per
>    **(gérant, magasin, permission)** — the owner may override permissions per magasin, so the
>    storage shape must support it from day one; the UI defaults to one uniform checklist and
>    surfaces override only on request. Retrofitting the magasin dimension is a data migration.
>    Use the shape in `03-UI-SPEC.md`, not the one below.
> 2. **The MAD separator is settled:** `1 800,00 MAD` — U+00A0 non-breaking space, decimal comma,
>    pinned explicitly on server and client (CLAUDE.md **#14**). Not ICU `fr-MA`'s full stop.
>
> Everything else here stands, including the session-authentication finding, which was verified and
> has already corrected CLAUDE.md.

# Phase 3: Comptes, Permissions & App Shell — Research

**Researched:** 2026-09-14
**Domain:** Django custom auth on a control-plane database, per-user field/row projection, DRF + OpenAPI contract, React/Vite SPA shell, fr-MA localisation
**Confidence:** HIGH on the Django/DRF/drf-spectacular internals (read from installed source and upstream master), HIGH on the locale finding (reproduced locally), MEDIUM on the SPA package choices (registry-verified versions, judgement calls on which to use)

---

## Summary

Phase 2 built a tenancy layer whose entire security argument is *"the tenant comes from an authenticated claim, resolved in middleware, and failing to resolve means refusing to run."* Phase 3 supplies the authenticated claim. Three facts, each verified from source in this session, collapse most of the apparent design space:

1. **`TenantMiddleware` resolves the client from `request.user` at middleware time.** Session authentication populates `request.user` in `AuthenticationMiddleware`, i.e. *before* `TenantMiddleware` runs. JWT authentication happens inside DRF, *after* all middleware. Choosing JWT therefore means moving the tenant lifecycle out of the middleware Phase 2 spent a plan getting right. Choosing session cookies changes **zero lines** of `plateforme/tenancy/middleware.py`.
2. **`ModelBackend.get_user()` calls `user_can_authenticate()`, which rejects `is_active=False`** (`django/contrib/auth/backends.py:235-240`, `:96-101`). Deactivating a gérant (PERM-02) or revoking a grant (PERM-03) takes effect on that user's *very next request*, with no revocation machinery, because the user row and the grant rows are read fresh from the control plane every request. A JWT bakes nothing useful in — verified: `JWTAuthentication.get_user` hits the database and checks `is_active` too — so the "stateless" argument for JWT is empty here while its revocation cost is real.
3. **`djangorestframework-simplejwt` does not support Django 6.1.** Released version 5.5.1 (2025-07-21) claims Django <= 5.2; upstream `master`'s tox matrix stops at `dj60`. CLAUDE.md pins Django 6.1.1. Adopting simplejwt means running unreleased code against an untested Django.

The architectural crux (PERM-06) is not "where does the filtering live" — it is "what stops three renderers from drifting apart by Phase 9." The answer is not a clever abstraction: it is an **enumerable registry** of `(model, field) -> permission code`, consumed by four things (DRF serializers, the CSV export, the document HTML context, *and the OpenAPI schema postprocessor*), plus a **parametrized conformance test that iterates the registry x the renderers**. Adding `prix_achat` to the registry in Phase 8 then automatically produces three assertions, one per renderer. That test — not the abstraction — is what makes PERM-06 true.

And one finding that directly answers "where should formatting live so server and client cannot disagree": **they already disagree, three ways.** Verified in this session — Django's `fr` locale groups thousands with U+00A0, browser/Node ICU `fr-FR` uses U+202F, and ICU **`fr-MA` uses a full stop**: `1.800,00 MAD` on screen versus `1 800,00 MAD` on the facture. Relying on either locale database is the bug.

**Primary recommendation:** Django session cookies on a same-origin Vite-proxied SPA; a custom `Utilisateur` in a new control-plane app `plateforme/comptes/` carrying a nullable `client` FK (so `resolve_client` is untouched); grants as rows in a purpose-built table keyed to a code catalogue that lives in Python; one `plateforme/projection/` package holding the registry plus four consumers; magasin scope enforced in `get_queryset()` **and** in every related-field queryset, never in `list()`; and an explicitly pinned money/date formatter on both sides driven by one shared fixture file.

---

## Project Constraints (from CLAUDE.md)

There is no `03-CONTEXT.md` — this phase has not been through `/gsd-discuss-phase`. CLAUDE.md's non-negotiables are therefore the binding constraints, and the ones that govern here are:

| # | Directive | Effect on this phase |
|---|---|---|
| **6** | Only the optician (owner) and gérants log in. Vendeurs are a field on a sale. **Permissions are granted per gérant individually, as data, not as role tiers.** | No `role` column anywhere. No tier bundles. PERM-03 is literally a checklist. |
| **8** | Tenant context fails closed, cleared (not `reset()`) in a `finally` | The `Acces` object must fail closed the same way: absent => empty permission set, not "allow". |
| **11** | **User accounts live in the control-plane database, with one shared login address.** Control plane holds identity, business membership and permission grants; the client database holds all business data. | `AUTH_USER_MODEL` on `default`. Grant tables on `default`. **Settled — do not reopen.** |
| **7** | Money is `Decimal`, never float | `COERCE_DECIMAL_TO_STRING` stays `True`; no client-side arithmetic on money. |
| **12** | Never set `ATOMIC_REQUESTS = True` | Login/logout views use explicit `atomic()` if they need it. |
| Testing | Test-first; tests named after their requirement; two tenants never one; do not test Django | Every test name below cites a requirement. |
| Stack | *"Auth: DRF with short-lived JWT (`djangorestframework-simplejwt`)"* | **Challenged below — see "Where CLAUDE.md is wrong", item 1.** CLAUDE.md itself says to raise rather than quietly reverse. |

---

## Phase Requirements

| ID | Requirement | Research support |
|---|---|---|
| PERM-01 | Owner signs in and stays signed in across sessions | §6 (session cookies, `SESSION_COOKIE_AGE`, `SESSION_EXPIRE_AT_BROWSER_CLOSE=False`), §8 (SPA bootstrap via `/api/auth/moi/`) |
| PERM-02 | Owner creates a gérant account and deactivates it later | §1 (`Utilisateur` shape, constraints), §6 (`is_active` enforced per request — source-verified), Attack surface A-03-05 (client_id forced server-side) |
| PERM-03 | Grant/revoke individual permissions, not role tiers | §4 (`Permission` catalogue in code, `DroitAccorde` rows as data) |
| PERM-04 | A gérant sees only granted magasins and data | §5 (queryset scoping in `get_queryset()`, related-field querysets, stale-grant intersection) |
| PERM-05 | Prix d'achat, margin, business-wide revenue hidden unless granted | §3 (field registry), §5 (aggregates are a *queryset* problem, not a field problem — see the roadmap correction) |
| PERM-06 | One projection layer for API, exports and printed documents | §3 — the crux. Registry + 4 consumers + parametrized conformance test |
| APP-01 | Web application runs in a browser with a French interface | §7 (server `fr-fr`, no `LocaleMiddleware`, DRF `fr` locale verified present), §8 (shell) |
| APP-03 | Amounts, dates, numbers formatted for Morocco (MAD, French conventions) | §7 — including the verified three-way separator disagreement |

---

## Where CLAUDE.md and the ROADMAP are wrong or naive

This is the highest-value section. Five corrections, in order of consequence.

### 1. The stack table's JWT choice is wrong for this product. Use Django session cookies.

CLAUDE.md: *"Auth | DRF with short-lived JWT (`djangorestframework-simplejwt`)"*. Four independent reasons to reverse it:

**(a) It breaks Phase 2's middleware.** `plateforme/tenancy/middleware.py:53-59` reads `request.user.client_id`. `django.contrib.auth.middleware.AuthenticationMiddleware` sets `request.user` from the session; DRF's authentication classes run inside `APIView.initial()`, long after every middleware has executed. Under JWT, `request.user` at `TenantMiddleware` time is `AnonymousUser` on **every** request, `resolve_client` returns `None`, nothing binds, and the first business query raises `NoTenantBound`. The fix would be to move binding into a DRF hook — abandoning the single-point-of-binding and the assert-unset-on-entry guard that plan 02-03 describes as *"the highest-risk bug in the system."* [VERIFIED: `plateforme/tenancy/middleware.py`, `rest_framework/authentication.py:112-133`, `django/contrib/auth/middleware.py`]

**(b) simplejwt does not support Django 6.1.** PyPI 5.5.1, released 2025-07-21, declares `Framework :: Django :: 4.2 ... 5.2`. Upstream `master`'s `tox.ini` envlist ends at `py314-dj{52,60}`. There is no 6.1 row anywhere. [VERIFIED: PyPI JSON API 2026-09-14; jazzband/djangorestframework-simplejwt `master/tox.ini`, `master/setup.py`]

**(c) The "stateless, no DB hit" benefit does not exist.** `JWTAuthentication.get_user()` does `self.user_model.objects.get(...)` and then `if api_settings.CHECK_USER_IS_ACTIVE and not user.is_active: raise`. It queries the database on every request exactly as sessions do. [VERIFIED: `master/rest_framework_simplejwt/authentication.py:127-147`]

**(d) PERM-02 and PERM-03 are revocation requirements, and tokens are the wrong shape for them.** With sessions, `logout()` flushes the session row, and `ModelBackend.get_user` refuses a deactivated user on the next request — *free*, source-verified. With JWT you must add `token_blacklist` (two more control-plane tables), rotate refresh tokens, and accept a window where a revoked gérant still works. And for a browser SPA the access token has to live somewhere: `localStorage` (readable by any XSS) or memory (lost on reload, so PERM-01 "stays signed in" forces a persisted refresh cookie — at which point you have reinvented sessions with extra parts and the same CSRF problem).

**The honest counter-argument, stated fully:** Phase 11 is Expo/React Native, where cookie handling is fiddlier than an `Authorization` header. This does **not** change the decision, because `DEFAULT_AUTHENTICATION_CLASSES` is a *list*. Adding a token class in Phase 11 is additive: no view, serializer, permission or projection code changes. The only thing that must be built now to keep that door open is that the tenant binding must not be *irreversibly* welded to middleware — and it is not, because `resolve_client(request)` is already a standalone function with the contract "server-verified identity in, `Client` out." Phase 11 can call it from a DRF hook for token requests without touching the session path.

**What this costs in doc edits (put these in the plan):** CLAUDE.md's stack row; `plateforme/tenancy/middleware.py`'s module docstring ("Phase 3 issues JWTs carrying a `client_id` claim"); `resolve_client`'s docstring ("Phase 3 replaces the `client_id` lookup below with a signed JWT claim"); the 02-03 decision line in `.planning/STATE.md`.

### 2. `config/urls.py`'s docstring states something false about tenant resolution, and it hides a real hole.

> *"`resolve_client` deliberately returns `None` for this path — the admin is fleet management"*

Resolution is **not path-based**. `resolve_client` returns `None` for admin URLs today only because the operator superuser happens to have no `client_id`. The moment Phase 3 introduces users *with* a `client_id`, any such user who is also `is_staff` gets their tenant bound on `/admin/`, and every registered `ModelAdmin` runs against their client database. Nothing in the codebase currently prevents `is_staff=True` on a client user. See Attack surface A-03-01 for the closure.

### 3. Roadmap criterion 3 is not satisfiable in Phase 3, and pretending otherwise will produce a fake test.

> *"prix d'achat, margin and business-wide revenue are absent unless explicitly granted"*

`prix_achat` and `marge` do not exist until **Phase 8** (ACHAT-04/07). Business-wide CA does not exist until **Phase 10** (DASH-01). Phase 3 cannot verify their absence without inventing them, and inventing them pre-empts Phase 8's schema — exactly the mistake `domaine/stock/models.py`'s docstring already warns against.

The correct Phase 3 scope, and it is still a full phase of work:
- declare the **whole ~20-code catalogue now**, including `article.voir_prix_achat`, `vente.voir_marge`, `dashboard.voir_ca_global`, even though the fields land later;
- build the registry and all **three renderers** plus the schema hook;
- write the conformance test **parametrized over the registry**, so it grows to three new assertions the day Phase 8 adds one line;
- prove it end-to-end against a **test-only fixture resource** in `tests/`, not a contrived production field.

REQUIREMENTS.md already re-verifies PERM-05 live at Phase 8 ("*a gérant without that permission sees neither in the UI, the API, an export, nor a printed document*"). Say so in the plan and in the phase gate, rather than writing a Phase 3 test that proves nothing.

### 4. Roadmap criterion 4 quietly demands an export and a printed document that are nobody's requirement.

*"A field hidden from a gérant is equally absent from the API response, an export and a printed document"* — but no PERM/APP requirement asks for an export or a print in Phase 3, and Phase 9 owns printed documents and WeasyPrint. Building a facture PDF now is scope creep; building nothing makes criterion 4 unverifiable and guarantees drift.

**The seam, not the document.** Ship `plateforme/projection/` with three thin adapters: `vers_json` (DRF), `vers_csv`, `vers_html` (Django template). Phase 3 renders **HTML**, not PDF — no WeasyPrint dependency, and the conformance test asserts on the HTML string. Phase 9 wraps the same HTML in `HTML(string=...).write_pdf()` with zero projection change. This is the smallest thing that makes criterion 4 real.

### 5. `USE_L10N` no longer exists, and `LocaleMiddleware` is the wrong tool here.

`USE_L10N` was deprecated in Django 4.0 and **removed**; it is absent from `django.conf.global_settings` in the installed 6.1.1. [VERIFIED: local probe] Adding it back does nothing. And `LocaleMiddleware` would make the UI language depend on a **client-supplied** `Accept-Language` header plus add `Vary: Accept-Language` to every response — a client-controlled variable in a product whose whole Phase 2 argument is that nothing security- or presentation-relevant comes from the client. This product is single-language. Do not add it. See §7.

---

## Standard Stack

All versions verified against the PyPI JSON API and the npm registry on **2026-09-14**.

### Backend — add to the existing pinned set

| Package | Version | Released | Purpose | Why standard / notes |
|---|---|---|---|---|
| `drf-spectacular` | **0.30.0** | 2026-07-06 | OpenAPI 3 schema -> TS client | Already named in CLAUDE.md. `requires_dist: Django>=2.2` with no upper bound; classifiers stop at Django 6.0, so **prove it in Wave 0** with `manage.py spectacular --fail-on-warn`. [VERIFIED: PyPI] |
| `argon2-cffi` | **25.1.0** | 2025-06-03 | Password hashing | Put `Argon2PasswordHasher` first in `PASSWORD_HASHERS`. Django ships the backend; this is the missing C library. Never hand-roll. [VERIFIED: PyPI] |
| `django-axes` | **8.3.1** | 2026-02-11 | Login lockout | **Optional.** One global login address for every optician is a broad brute-force target. DRF's `ScopedRateThrottle` covers per-IP; axes adds per-username lockout + an audit trail. Classifiers reach Django 6.0, not 6.1 — same Wave 0 proof required. If adopted, `axes` **must** be added to `CONTROL_PLANE_APPS` in the same commit (it has models). [VERIFIED: PyPI] |

**Do NOT add:** `djangorestframework-simplejwt` (see above), `django-guardian` (§4 — structurally impossible here), `django-cors-headers` (§8 — a same-origin dev proxy makes CORS unnecessary), `djangorestframework-camel-case` (last release 2023-02, and snake_case through the generated TS client is fine).

### Frontend — new `web/` workspace

| Package | Version | Released | Purpose | Notes |
|---|---|---|---|---|
| `vite` | **8.2.2** | 2026-08-20 | Dev server + build | `latest` is 8.3.0, four days old. Pin one minor back, consistent with this project's pinning discipline. [VERIFIED: npm] |
| `@vitejs/plugin-react` | **6.1.1** | 2026-08-28 | React fast-refresh | [VERIFIED: npm] |
| `react` / `react-dom` | **19.3.0** | 2026-09-09 | UI | [VERIFIED: npm] |
| `typescript` | **5.9.3** | 2025-09-30 | Types | **Not 7.0.2.** `typescript-eslint@8.70.0` (latest, 2026-09-07) declares `peerDependencies.typescript: ">=4.8.4 <6.1.0"` — it supports neither TS 6 nor TS 7. Pinning TS 7 means no lint. [VERIFIED: npm registry peer metadata] |
| `react-router-dom` | **7.18.3** | 2026-08-28 | Routing + auth guard | See §8 for the judgement against TanStack Router. [VERIFIED: npm] |
| `@tanstack/react-query` | **5.102.8** | 2026-08-27 | Server state, 401 handling, cache invalidation on grant change | [VERIFIED: npm] |
| `openapi-typescript` | **7.13.0** | 2026-02-11 | `schema.yml` -> `types.ts` (types only, no runtime) | Repo active (pushed 2026-09-11, 8.4k stars) despite the npm gap. [VERIFIED: npm + GitHub API] |
| `openapi-fetch` | **0.17.0** | 2026-02-11 | ~6 kB typed fetch wrapper | Passes `credentials` and headers straight through — the CSRF header and session cookie are two lines. [VERIFIED: npm] |
| `openapi-react-query` | **0.5.4** | 2026-02-11 | Binds the two above to react-query | Peers: `@tanstack/react-query ^5.80.0`, `openapi-fetch ^0.17.0` — both satisfied. [VERIFIED: npm] |
| `vitest` | **4.1.11** | 2026-08-18 | SPA unit tests (the shared format fixture) | `latest` is 5.0.0, eleven days old. Use the `V4` dist-tag. [VERIFIED: npm] |
| `typescript-eslint` | **8.70.0** | 2026-09-07 | Lint | [VERIFIED: npm] |

### Alternatives considered

| Instead of | Could use | Tradeoff |
|---|---|---|
| `openapi-typescript` + `openapi-fetch` | `@hey-api/openapi-ts` 0.99.0 | Generates a full runtime SDK. Pre-1.0 with a history of breaking renames; the generated runtime is a second thing that can drift from the schema. Rejected for a solo project. |
| same | `orval` 8.33.0 (2026-09-13) | Generates react-query hooks directly — genuinely less boilerplate. Rejected because it emits a large amount of code into the repo, and because types-only generation makes "did the contract change?" a one-line diff of `schema.yml`, which TESTING.md §2 explicitly asks for. |
| `react-router-dom` 7 | `@tanstack/react-router` 1.170.x | Better type-safe routes and search params. Rejected: it adds a **second** codegen step (route tree) on top of the OpenAPI one, and the auth guard this phase needs is a 20-line wrapper either way. Revisit at Phase 5 if dense table URLs get painful. |
| A purpose-built grant table | `django.contrib.auth.Permission` + `Group` | See §4 — no magasin dimension, model-CRUD shaped rather than business shaped, and `Group` *is* a role tier, which CLAUDE.md #6 forbids. |
| A purpose-built grant table | `django-guardian` 3.5.0 | **Structurally impossible**, see §4. |

**Installation:**
```bash
uv add drf-spectacular==0.30.0 argon2-cffi==25.1.0
# optional, after the Wave 0 Django-6.1 proof:
uv add django-axes==8.3.1

cd web && npm i react@19.3.0 react-dom@19.3.0 react-router-dom@7.18.3 \
  @tanstack/react-query@5.102.8 openapi-fetch@0.17.0 openapi-react-query@0.5.4
npm i -D vite@8.2.2 @vitejs/plugin-react@6.1.1 typescript@5.9.3 \
  openapi-typescript@7.13.0 vitest@4.1.11 typescript-eslint@8.70.0
```

---

## Architecture

### Recommended structure

```
plateforme/
├── comptes/                 # NEW — control-plane app, label "comptes"
│   ├── models.py            #   Utilisateur, DroitAccorde, AccesMagasin, JournalDroit
│   ├── permissions_catalogue.py  #   the ~20 codes, as TextChoices — CODE, not data
│   ├── acces.py             #   Acces dataclass + acces_pour() + Acces.ANONYME / .SCHEMA
│   ├── middleware.py        #   AccesMiddleware — sets request.acces lazily, after TenantMiddleware
│   ├── serializers.py       #   connexion / moi / gestion des gérants
│   ├── views.py             #   /api/auth/*, /api/comptes/*
│   └── admin.py             #   operator-only
├── projection/              # NEW — PERM-06 lives here and NOWHERE else
│   ├── registre.py          #   CHAMPS_PROTEGES: {"app.Model.field": code}
│   ├── serializers.py       #   SerializerProjete  (consumer 1: JSON API)
│   ├── export.py            #   exporter_csv      (consumer 2: export)
│   ├── documents.py         #   contexte_document / rendre_html (consumer 3: print)
│   ├── schema.py            #   postprocessing hook + GET_MOCK_REQUEST (consumer 4: OpenAPI)
│   ├── vues.py              #   VueProjetee, MagasinScopedViewSet, MagasinAutoriseField
│   └── checks.py            #   projection.E001 — every exposed model field is classified
├── tenancy/                 # UNCHANGED by this phase, except two docstrings
└── control_plane/
web/                         # NEW — Vite + React + TS
├── src/api/{schema.yml,types.gen.ts,client.ts}
├── src/auth/{AuthProvider.tsx,RequireAuth.tsx,Connexion.tsx}
├── src/format/{montant.ts,date.ts}
├── src/layout/{AppShell.tsx,NavLaterale.tsx}
└── tests/format.test.ts     # reads tests/fixtures/formats_mad.json
tests/fixtures/formats_mad.json   # ONE fixture, read by pytest AND vitest
```

`comptes` and `projection` **must** be added to `CONTROL_PLANE_APPS` in `plateforme/tenancy/router.py` in the **same commit** as `INSTALLED_APPS`, along with `drf_spectacular` and (if adopted) `axes` — `tenancy.E001` exempts only names starting with `django.`, so every one of them will fail `manage.py check` otherwise. `projection` owns no models but still needs the label. [VERIFIED: `plateforme/tenancy/checks.py:29-32`]

---

### §1 — Where the user model lives, and how it coexists with the router

**Decided by CLAUDE.md #11 and by 02-RESEARCH.md Open Question 1: control plane, on `default`.** This research confirms it rather than reopening it, and the confirming fact is concrete: `auth`, `contenttypes`, `admin` and `sessions` are already in `CONTROL_PLANE_APPS` and `allow_migrate` already pins them to `default` (`router.py:41-53, 129-131`). One `AUTH_USER_MODEL` per project; Django requires `auth`/`contenttypes`/`admin` co-located. There is no choice left to make.

**Does the user carry the client FK directly, or is membership a separate model? -> FK directly, nullable.**

```python
# plateforme/comptes/models.py
class Utilisateur(AbstractBaseUser):          # NOT PermissionsMixin — see below
    email        = models.EmailField(unique=True, verbose_name="adresse e-mail")
    nom_complet  = models.CharField(max_length=150)

    # THE tenant claim. TenantMiddleware.resolve_client already reads `user.client_id`
    # (middleware.py:59) — naming this field `client` means Phase 3 changes ZERO lines
    # of the tenancy layer. NULL means a platform operator, who belongs to no client.
    client       = models.ForeignKey("control_plane.Client", null=True, blank=True,
                                     on_delete=models.PROTECT, related_name="utilisateurs")
    est_proprietaire = models.BooleanField(default=False)

    is_active    = models.BooleanField(default=True)   # PERM-02 deactivation
    is_staff     = models.BooleanField(default=False)  # OPERATOR ONLY — see constraint
    is_superuser = models.BooleanField(default=False)
    doit_changer_mot_de_passe = models.BooleanField(default=False)
    derniere_connexion_ip = models.GenericIPAddressField(null=True, blank=True)
    cree_le      = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = ["nom_complet"]
    objects = UtilisateurManager()

    class Meta:
        constraints = [
            # A user belonging to a client can NEVER reach the operator admin.
            # A CHECK constraint, not clean(): queryset.update(is_staff=True) and a
            # shell session both bypass clean(). Same reasoning as
            # control_plane.Client.active_client_has_db_name.
            models.CheckConstraint(
                condition=models.Q(client__isnull=True)
                          | (models.Q(is_staff=False) & models.Q(is_superuser=False)),
                name="un_utilisateur_client_n_est_jamais_operateur",
                violation_error_message=(
                    "Un compte rattaché à un client ne peut pas être opérateur. "
                    "L'admin Django est la gestion de flotte, pas les données d'un opticien."
                ),
            ),
            models.CheckConstraint(
                condition=models.Q(client__isnull=False) | models.Q(est_proprietaire=False),
                name="un_proprietaire_appartient_a_un_client",
            ),
            models.UniqueConstraint(
                fields=["client"], condition=models.Q(est_proprietaire=True),
                name="un_seul_proprietaire_par_client",
            ),
        ]

    # AbstractBaseUser without PermissionsMixin — the admin needs these three.
    def has_perm(self, perm, obj=None):    return self.is_superuser
    def has_module_perms(self, app_label): return self.is_superuser
```

**Why FK, not a `Membership` table** — in order of weight:
1. `resolve_client` reads `user.client_id`. A `Membership` means the request must resolve *which* membership, which means either a client-supplied selector (exactly the tenant-spoofing threat T-02-13 that Phase 2 exists to prevent) or session state that can go stale. A column on a row cannot be spoofed.
2. The product has no multi-business user. A chain of shops is **one client with several magasins**, which is what `Magasin` is for. CLAUDE.md #11's "one shared login address" means one login *page*, not one shared account.
3. Cost, stated honestly: a person genuinely running two separate client businesses needs two accounts with two email addresses. If that day comes, the migration is contained — because **nothing outside `acces_pour()` ever reads `user.client` directly.** Everything reads the resolved `Acces` object (below), so swapping the storage is one function.

**Why no `PermissionsMixin`** — it would create `auth_user_groups` and `auth_user_user_permissions`, and it would put `user.has_perm("achats.view_article")` one keystroke away from `acces.peut("article.voir_prix_achat")`. Two permission systems in one codebase is how Phase 9 drifts. Omitting it means `Group` — a role tier — cannot be reached at all, which is CLAUDE.md #6 enforced by absence rather than by discipline. **Cost:** the operator admin becomes all-or-nothing (`is_superuser` or nothing). For a solo operator that is correct; revisit only if a support role is ever hired. [CITED: docs.djangoproject.com/en/6.1/topics/auth/customizing/ — `AbstractBaseUser` + admin requires `is_staff`, `has_perm`, `has_module_perms`]

**How login works before any tenant is bound.** It just works, and the router is the reason: `comptes` is in `CONTROL_PLANE_APPS`, so `TenantRouter._route` returns `"default"` at line 79-80 *before* it ever calls `current_alias()` (line 91). Authenticating an anonymous `POST /api/auth/connexion/` touches only `comptes` and `sessions` — both control-plane — so `NoTenantBound` is never raised. The context stays unbound for the whole login request, which is correct: a login has no client to belong to yet. On the *next* request the session cookie identifies the user, `AuthenticationMiddleware` loads them, `TenantMiddleware` reads `user.client_id`, and the tenant binds. **No chicken-and-egg exists.** This is the single strongest confirmation of the control-plane-user decision — and it is a property of the code that already exists, not of anything Phase 3 adds.

**The migration hazard — put this in Wave 0.** `AUTH_USER_MODEL` must be swapped before anything depends on `auth.User`, and `django.contrib.admin`'s migrations already carry `LogEntry.user -> settings.AUTH_USER_MODEL`. Because `plateforme/control_plane/migrations/0001-0003` do not reference `User`, the clean path is to **recreate the control-plane development database** in Wave 0. Blocking pre-check before the plan runs:
```sql
SELECT count(*) FROM control_plane_client WHERE status = 'active';
```
If that is non-zero on any real deployment, this becomes a data migration (the documented multi-step swap) and needs its own plan. Verify with the operator first.

---

### §2 — Tenant resolution from the authenticated user

**Nothing changes.** `resolve_client(request)` (`middleware.py:36-67`) already does exactly the right thing: reads `request.user`, refuses if unauthenticated, reads `user.client_id`, and filters on `status=ACTIVE`. Phase 3's only job is to make `request.user` be a real user.

Ordering, which matters and is already correct in `config/settings/base.py`:

```
SecurityMiddleware
SessionMiddleware              <- reads the session cookie
CommonMiddleware
CsrfViewMiddleware
AuthenticationMiddleware       <- sets request.user (lazy)
TenantMiddleware               <- forces the lazy load, binds the alias, clears in finally
AccesMiddleware                <- NEW. request.acces = SimpleLazyObject(...)  [tenant IS bound here]
MessageMiddleware
XFrameOptionsMiddleware
```

`AccesMiddleware` goes **after** `TenantMiddleware` because resolving which magasins a grant refers to requires a query against the *client* database (§5), which requires the alias to be bound. It sets a `SimpleLazyObject`, so endpoints that never touch `request.acces` pay nothing.

| Caller | `request.user` | Bound client | Correct? |
|---|---|---|---|
| Anonymous (login page, `/api/auth/csrf/`, health) | `AnonymousUser` | none | Yes — a business query on these paths *should* raise `NoTenantBound`. |
| Signed-in owner/gérant | `Utilisateur` with `client_id` | their client | Yes. |
| Operator in `/admin/` | superuser, `client_id is NULL` | none | Yes — `resolve_client` returns `None` at line 59-61. Admin is fleet management. |
| Client user reaching `/admin/` | — | **would bind** | **Closed by the CHECK constraint above**, not by the path. See A-03-01. |
| Celery | n/a | from `client_id` kwarg | Unchanged. A task that needs a *user's* view of data takes `acting_utilisateur_id` — see A-03-03. |

**Do not** add a subdomain, header or query-parameter tenant hint, even as a "secondary signal." The middleware docstring already forbids it and the reasoning is sound.

---

### §3 — The single projection layer (PERM-06). The crux.

#### The failure mode to design against

Three renderers that agree today drift apart because each one is written by a different task in a different phase, and nothing mechanically links them. A shared base class does not prevent this — Phase 9 writes a facture template with `{{ ligne.prix_achat }}` in it and Django renders an empty string with no error. **The link must be enumerable and the test must iterate it.**

#### The design: one registry, four consumers, one parametrized test

```python
# plateforme/projection/registre.py
"""The one source of truth for field-level visibility. PERM-06.

Keyed by MODEL field, not by serializer, so a protected field stays protected
wherever it is serialized — including when it is nested inside another resource's
serializer, which is the route by which this kind of thing normally leaks.
"""
from plateforme.comptes.permissions_catalogue import Permission

CHAMPS_PROTEGES: dict[str, str] = {
    # "app_label.ModelName.field_name": permission code
    # Phase 8 adds:
    #   "achats.Article.prix_achat":  Permission.ARTICLE_VOIR_PRIX_ACHAT,
    #   "ventes.LigneVente.marge":    Permission.VENTE_VOIR_MARGE,
    # Phase 10 adds:
    #   "dashboard.Synthese.ca_entreprise": Permission.DASHBOARD_VOIR_CA_GLOBAL,
}

#: Model fields deliberately visible to everyone. Every exposed model field must be in
#: exactly one of these two structures; `projection.E001` fails otherwise.
CHAMPS_PUBLICS: frozenset[str] = frozenset({...})

def champs_interdits(model, acces) -> frozenset[str]:
    """Fields of `model` this Acces may not see. Empty for a schema-generation Acces."""
```

**Consumer 1 — DRF serializers.**
```python
class SerializerProjete(serializers.ModelSerializer):
    def get_fields(self):
        fields = super().get_fields()
        # FAIL CLOSED: a request with no `acces` gets Acces.ANONYME, whose permission
        # set is empty, so every protected field is dropped. A missing attribute must
        # never mean "allow" — CLAUDE.md #8 applied to the permission layer.
        acces = getattr(self.context.get("request"), "acces", Acces.ANONYME)
        for nom in champs_interdits(self.Meta.model, acces):
            fields.pop(nom, None)
        return fields
```
Dropping from `get_fields()` also closes the **write** side for free: a dropped field never reaches `validated_data`, so a gérant POSTing `prix_achat` is silently ignored rather than honoured. Assert the value is *unchanged* — do not assert a 400, because DRF does not raise for unknown keys.

**Consumer 2 — the export.** The export must not read the queryset. It reuses the serializer:
```python
def exporter_csv(serializer_class, queryset, *, acces) -> str:
    ser = serializer_class(queryset, many=True, context={"request": _PorteurAcces(acces)})
    lignes = ser.data
    colonnes = list(ser.child.fields)     # ALREADY projected — this is the whole trick
    ...
```
Deriving the header from `ser.child.fields` rather than from a hand-written column list is what makes an omitted field produce *no column* instead of an *empty column*. `_PorteurAcces` is a five-line stand-in object carrying only `.acces` and `.user`; it exists so that a Celery task or a management command can drive the projection without an HTTP request.

**Consumer 3 — the printed document.**
```python
def contexte_document(serializer_class, instance, *, acces) -> dict:
    return serializer_class(instance, context={"request": _PorteurAcces(acces)}).data

def rendre_html(nom_template, contexte) -> str: ...
# Phase 9: HTML(string=rendre_html(...)).write_pdf()
```
**Template trap, state it in the plan:** a Django template resolving a missing dict key renders `string_if_invalid`, which defaults to `""` — so a hidden field looks fine and a *typo'd* field also looks fine. Do not fix this by setting `string_if_invalid` globally (the Django docs warn it breaks `{% if %}` on optional values). Fix it by having document templates iterate a **declared, projected column list** rather than naming fields inline, and by asserting in the conformance test that the protected *value* does not appear anywhere in the rendered HTML.

**Consumer 4 — the OpenAPI schema.** This is the part that is easy to miss and it is what keeps the generated TypeScript honest.

#### What breaks the OpenAPI contract when a field's presence varies by user — plainly

`drf-spectacular` builds each component by iterating `serializer.fields.values()` (`openapi.py:1083`). **Your `get_fields()` projection therefore changes the generated schema.** Two concrete consequences, both verified from source:

1. **`build_serializer_context(view)` calls `view.get_serializer_context()`, and `build_mock_request` copies `request.user` from the original request when one exists** (`plumbing.py:1283-1299`, `:1502-1506`). When the schema is *served* at `/api/schema/`, `original_request` is the real request — so **a gérant would download a different schema than the owner.** The committed `schema.yml` and the runtime schema silently diverge, and "one generated client" stops being true.
2. A field's membership of the component's `required` array is computed as `field.required or (readOnly and not COMPONENT_NO_READ_ONLY_REQUIRED)` (`openapi.py:1094-1099`). A read-only computed money field lands in `required`. The generated TypeScript then declares `prix_achat: string` — **a type that lies**, because at runtime a gérant's payload has no such key. `data.prix_achat.toString()` throws in production and the compiler said it was fine.

**The fix is that the registry drives the schema too**, which is also the cleanest proof that the abstraction is real rather than decorative:

```python
# plateforme/projection/schema.py
def requete_mock_schema(method, path, view, original_request, **kwargs):
    """SPECTACULAR_SETTINGS["GET_MOCK_REQUEST"].

    Pins the projection to Acces.SCHEMA regardless of who is asking, so the served
    schema is byte-identical to the committed schema.yml for every user. Without this,
    drf-spectacular copies request.user from the caller (plumbing.py:1288).
    """
    requete = build_mock_request(method, path, view, original_request, **kwargs)
    requete.acces = Acces.SCHEMA          # full catalogue, pour_le_schema=True
    return requete

def marquer_champs_proteges_optionnels(generator, request, public, result):
    """SPECTACULAR_SETTINGS["POSTPROCESSING_HOOKS"] += this.

    Every field named in CHAMPS_PROTEGES is removed from its component's `required`
    array, so the generated TS is `prix_achat?: string` and the compiler forces every
    call site to handle absence. One registry, one truth, four consumers.
    """
```
Keep `COMPONENT_NO_READ_ONLY_REQUIRED` at its default `False` — flipping it would make *every* read-only field optional, including `id`, which is a much worse lie. The hook is precise. [VERIFIED: `drf_spectacular/settings.py:38, 100-102, 137`]

#### The alternative, and why it loses

**Null-instead-of-omit** (always emit the key, `null` when not permitted) gives a simpler TS type `prix_achat: string | null` and avoids touching `required`. Rejected on three grounds: PERM-05 and roadmap criterion 4 both say **absent**; an always-present column in a CSV export is an empty column, which fails "absent from an export" in spirit and gives a gérant the field's existence and position; and a `null` money value invites `?? 0` at the call site, producing a *margin of zero* instead of a visibly missing one — a wrong number with no error, which this project's own `MagasinScopedModel` docstring already identifies as worse than a crash.

#### What actually prevents drift: the test, not the abstraction

```python
@pytest.mark.parametrize("cle,code", sorted(CHAMPS_PROTEGES.items()))
@pytest.mark.parametrize("rendu", ["api", "export", "document"])
def test_perm06_champ_protege_absent_de_lapi_de_lexport_et_du_document(cle, code, rendu):
    ...
```
Adding one line to `CHAMPS_PROTEGES` in Phase 8 produces three new assertions automatically. A renderer added in Phase 9 that does not read the registry fails the moment it is added to the `rendu` list — and the plan for Phase 9 must add it. Pair it with a classification guard in the `tenancy.E001` idiom this codebase already uses:

```python
# plateforme/projection/checks.py
@register()
def check_every_exposed_field_is_classified(app_configs, **kwargs):
    """projection.E001 — a model field exposed by any ModelSerializer must be in
    CHAMPS_PROTEGES or CHAMPS_PUBLICS. Unclassified means someone added a column and
    nobody decided who may see it."""
```
Implement this as a **test first** (import cycles make a startup check that imports every `serializers.py` fragile), and promote it to a system check only if it proves stable.

---

### §4 — Per-gérant permission grants

#### Rejecting the off-the-shelf options, concretely

| Option | Why it loses |
|---|---|
| `django.contrib.auth.Permission` + `Group` | `Group` **is** a role tier — CLAUDE.md #6 forbids it. `Permission` rows are `(content_type, codename)` shaped, i.e. model-CRUD, not business-shaped ("voir le prix d'achat" is not an operation on a model). There is no magasin dimension on `auth_user_user_permissions`. And adding a permission means creating a `Permission` row, which means a data migration. |
| `django-guardian` 3.5.0 | **Structurally impossible.** Guardian's `UserObjectPermission` has a FK to the user (control plane, `default`) and a generic FK to the target object. The objects being scoped are `Magasin` rows, which live in the **client database**. A Django FK cannot span aliases, and `TenantRouter.allow_relation` (`router.py:116-118`) explicitly returns `obj1._state.db == obj2._state.db`, so any such relation is refused. Not a preference — a wall. |
| `spatie`-style team mode | Already rejected in Phase 2 as inapplicable; it is a Laravel package. |
| A JSON/`ArrayField` of codes on `Utilisateur` | Would work for 20 codes. Rejected for: no unique constraint, no `accorde_par`/`accorde_le`, and no way for the admin or a future audit view to answer "who gave Karim the margin permission and when." The cost of a table over an array is three columns. |

#### The shape

```python
# plateforme/comptes/permissions_catalogue.py
class Permission(models.TextChoices):
    """~20 codes. CODE, not data — the catalogue must be enumerable at import time so
    the conformance test, the schema hook and the UI checklist can all iterate it.
    Grants are data; the catalogue is not. This is not a role tier (CLAUDE.md #6):
    a tier bundles codes, this is the list of codes that exist."""
    CLIENT_VOIR             = "client.voir",              "Consulter les clients"
    CLIENT_MODIFIER         = "client.modifier",          "Créer et modifier des clients"
    ORDONNANCE_VOIR         = "ordonnance.voir",          "Consulter les ordonnances"
    ORDONNANCE_SAISIR       = "ordonnance.saisir",        "Saisir une ordonnance"
    STOCK_VOIR              = "stock.voir",               "Consulter le stock"
    STOCK_AJUSTER           = "stock.ajuster",            "Ajuster le stock / inventaire"
    ARTICLE_VOIR_PRIX_ACHAT = "article.voir_prix_achat",  "Voir le prix d'achat"   # Phase 8
    VENTE_CREER             = "vente.creer",              "Enregistrer une vente"
    VENTE_REMISE            = "vente.remise",             "Accorder une remise"
    VENTE_VOIR_MARGE        = "vente.voir_marge",         "Voir la marge"          # Phase 8
    FACTURE_AVOIR           = "facture.avoir",            "Émettre un avoir"
    CAISSE_VOIR             = "caisse.voir",              "Consulter la caisse"
    CAISSE_SAISIR           = "caisse.saisir",            "Saisir en caisse"
    CAISSE_COMPTAGE         = "caisse.comptage",          "Faire le comptage"
    FOURNISSEUR_VOIR        = "fournisseur.voir",         "Consulter les fournisseurs"
    ACHAT_COMMANDER         = "achat.commander",          "Passer un bon de commande"
    ACHAT_VOIR_SOLDES       = "achat.voir_soldes",        "Voir les soldes fournisseurs"
    DASHBOARD_VOIR_CA_GLOBAL= "dashboard.voir_ca_global", "Voir le CA de toute l'entreprise"  # Phase 10
    RAPPEL_VOIR             = "rappel.voir",              "Consulter les rappels"
    COMPTE_GERER            = "compte.gerer",             "Gérer les comptes et les droits"

# plateforme/comptes/models.py
class DroitAccorde(models.Model):
    """PERM-03. One row = one permission, granted to one gérant, individually."""
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name="droits")
    code        = models.CharField(max_length=64, choices=Permission.choices)
    accorde_par = models.ForeignKey(Utilisateur, on_delete=models.PROTECT, related_name="+")
    accorde_le  = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["utilisateur", "code"],
                                               name="uniq_droit_par_utilisateur")]

class AccesMagasin(models.Model):
    """PERM-04. `magasin_code` is a VALUE, not a ForeignKey: Magasin lives in the client
    database and a FK cannot cross aliases (TenantRouter.allow_relation). Stored as the
    business code rather than the pk so it survives a restore-and-cut-over, and
    intersected with the live active magasins at resolution time so a stale grant grants
    nothing."""
    utilisateur   = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name="acces_magasins")
    magasin_code  = models.CharField(max_length=20)
    accorde_par   = models.ForeignKey(Utilisateur, on_delete=models.PROTECT, related_name="+")
    accorde_le    = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["utilisateur", "magasin_code"],
                                               name="uniq_acces_magasin_par_utilisateur")]

class JournalDroit(models.Model):
    """Append-only. Revocation deletes the grant row; this keeps the history.
    Five columns, and the owner will eventually ask 'who gave Karim the margins?'."""
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.PROTECT, related_name="journal")
    action      = models.CharField(max_length=8)   # "accorde" | "revoque"
    cible       = models.CharField(max_length=64)  # permission code or magasin code
    par         = models.ForeignKey(Utilisateur, on_delete=models.PROTECT, related_name="+")
    le          = models.DateTimeField(auto_now_add=True)
```

#### The resolved access object — the seam everything else reads

```python
# plateforme/comptes/acces.py
@dataclass(frozen=True, slots=True)
class Acces:
    utilisateur_id: int | None
    client_id: int | None
    est_proprietaire: bool
    permissions: frozenset[str]
    magasins_ids: frozenset[int]
    pour_le_schema: bool = False

    def peut(self, code: str) -> bool:
        return code in self.permissions        # ONE code path. See below.

Acces.ANONYME = Acces(None, None, False, frozenset(), frozenset())
Acces.SCHEMA  = Acces(None, None, False, frozenset(Permission.values), frozenset(),
                      pour_le_schema=True)

def acces_pour(utilisateur) -> Acces:
    """Resolve once per request. The owner's Acces is MATERIALISED with the full
    catalogue and the full active-magasin set — deliberately, so that `peut()` has no
    `if est_proprietaire` branch. A branch that skips the check for owners is a branch a
    bug can reach for a non-owner. One code path, always."""
```

Wire it lazily so unauthenticated and non-business endpoints pay nothing:
```python
# plateforme/comptes/middleware.py
request.acces = SimpleLazyObject(lambda: acces_pour(request.user))
```

**Everything else in the codebase reads `request.acces`, never `request.user.droits` and never `user.client_id`.** That is what makes the FK-versus-Membership decision in §1 reversible, and what lets a Celery task or a management command drive the projection with no HTTP request.

---

### §5 — Magasin scoping (PERM-04): where it is enforced

**Both layers, with different jobs — and the queryset is the load-bearing one.** The projection redacts *fields*; it cannot redact *rows*, and it cannot redact an *aggregate*. A gérant granted one magasin who can still see a `SUM(montant)` over all magasins has been told the business-wide revenue that PERM-05 forbids, even though every field was "hidden."

> **This is a real gap in how the roadmap frames PERM-05.** "Business-wide revenue" is not a field-visibility problem. You cannot redact a scalar you already computed — you have to not compute it. The aggregate must be taken **over the already-scoped queryset**, before any serializer sees it. Any dashboard endpoint that computes then redacts is wrong by construction.

**Where the filter lives:**

```python
# plateforme/projection/vues.py
class MagasinScopedViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self.request, "acces", Acces.ANONYME).pour_le_schema:
            return qs
        return qs.for_magasins(self.request.acces.magasins_ids)
```

- **In `get_queryset()`, never in `list()`.** `GenericAPIView.get_object()` calls `get_queryset()`, so filtering there covers the detail route `/ventes/42/` as well as the list. Filtering in `list()` leaves the detail route wide open — the classic IDOR in this shape of code.
- **Not in a default manager.** `domaine/magasins/models.py:80-85` already rejects an implicit magasin filter, with the right reason: cross-magasin reads are legitimate and constant (the owner's dashboard, réappro), and an implicit filter would return *a wrong number with no error*. Respect that decision; scope at the view, explicitly.
- **Related fields must be scoped too, and this is the one people forget.** A gérant POSTing `{"magasin": 7}` for a magasin they were not granted is an IDOR unless the field's queryset is scoped:
```python
class MagasinAutoriseField(serializers.PrimaryKeyRelatedField):
    """Never Magasin.objects.all(). DRF validates the pk against THIS queryset, so
    scoping it turns a cross-magasin write into a 400 instead of a 201."""
    def get_queryset(self):
        return Magasin.objects.filter(id__in=self.context["request"].acces.magasins_ids)
```
- **Enumeration guard**, same idiom as `tenancy.E001`: a test that walks every registered ViewSet whose model subclasses `MagasinScopedModel` and asserts it inherits `MagasinScopedViewSet`. Forgetting the mixin in Phase 7 then fails CI rather than shipping.

**Interaction with the tenant router.** Two layers, never conflated: the router binds *which database* (a client boundary, fails closed, enforced below the application by `REVOKE CONNECT`); the magasin filter selects *which rows within it* (a column, enforced only in Python). The magasin filter must never be relied on for tenant isolation, and the router must never be relied on for magasin scope. A test for each, and the fixtures give two tenants **and** two magasins per tenant.

**Stale grants.** `acces_pour` intersects granted `magasin_code`s with `Magasin.objects.filter(actif=True)`. A grant naming a magasin that was deactivated (they are never deleted — `Magasin` docstring) resolves to nothing, so a stale row grants nothing. Test it.

---

### §6 — Authentication for the SPA

**Recommendation: Django session cookies, same-origin, with DRF `SessionAuthentication`.** The case is made in "Where CLAUDE.md is wrong" item 1; here is the configuration.

```python
# config/settings/base.py
AUTH_USER_MODEL = "comptes.Utilisateur"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",   # argon2-cffi
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",   # keeps existing hashes readable
]

# PERM-01 — "stays signed in across sessions".
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30        # 30 days, explicit (default is 14)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False       # default, but state it: this IS the requirement
SESSION_SAVE_EVERY_REQUEST = False            # see note
SESSION_ENGINE = "django.contrib.sessions.backends.db"
# SESSION_COOKIE_SECURE / HTTPONLY / SAMESITE="Lax" and the CSRF pair are already set.

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    # Browsable API is a debugging tool, not a product surface — see A-03-06.
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "COERCE_DECIMAL_TO_STRING": True,          # DRF's default; pinned because flipping it
                                               # turns every money value into a JS float
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"connexion": "10/min"},
}
```

**`SESSION_SAVE_EVERY_REQUEST = False`, deliberately.** Sliding expiry would write one `UPDATE django_session` per request to the **control-plane** database — a single hot table shared by every optician. PERM-01 asks for "still signed in when they return," not for a rolling window, and a fixed 30 days delivers that with one write at login. If users later complain about being logged out, the upgrade is `cached_db` with the Redis that Celery already uses — *not* plain `cache`, because a Redis restart would log the entire fleet out, and Redis must not be in the authentication path.

**Add `clearsessions` to Celery Beat.** Without it `django_session` grows forever on the shared control-plane database. This is routinely forgotten; make it a task line in the plan.

**CSRF.** DRF views are `csrf_exempt` at the middleware level; `SessionAuthentication.authenticate()` calls `self.enforce_csrf(request)` itself, per request, for authenticated users only (`rest_framework/authentication.py:117-133`, verified in the installed 3.18.1). So CSRF *is* enforced on the API, by the authentication class. The SPA needs:
- `GET /api/auth/csrf/` decorated `@ensure_csrf_cookie` before the first POST;
- the header `X-CSRFToken` (`CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"`, verified from `global_settings`) read from the `csrftoken` cookie, which is intentionally **not** HttpOnly (`CSRF_COOKIE_HTTPONLY = False` is the default and is correct — the double-submit pattern requires JS to read it);
- `credentials: "include"` on every call (a same-origin `openapi-fetch` default of `same-origin` is also fine).

`SameSite=Lax` (already set) is correct — `Strict` would break returning to the app from an external link, and same-origin makes Lax sufficient.

**Endpoints:**

| Route | Auth | Does |
|---|---|---|
| `GET /api/auth/csrf/` | anon | `@ensure_csrf_cookie`, empty 204 |
| `POST /api/auth/connexion/` | anon, throttled `connexion` | `authenticate()` -> `login(request, user)` -> returns the `moi` payload. Rotates the session key (Django's `login()` does this — session fixation handled). |
| `POST /api/auth/deconnexion/` | session | `logout(request)` — flushes the session row. **Real revocation, immediately.** |
| `GET /api/auth/moi/` | session | `{utilisateur, client:{raison_sociale,...}, permissions:[...], magasins:[...]}` — the SPA's entire bootstrap. |
| `POST /api/auth/mot-de-passe/` | session | self-change; clears `doit_changer_mot_de_passe` |
| `POST/PATCH/DELETE /api/comptes/...` | session + `compte.gerer` | PERM-02, PERM-03 |

**Password reset is an unresolved dependency, and it is a real gap.** The stack table names no transactional email provider, so `PasswordResetView` cannot work. Phase 3 must therefore ship the no-email path: the **owner sets a gérant's initial password and can reset it**, with `doit_changer_mot_de_passe=True` forcing a change at first login; an **owner** who forgets theirs is reset by the operator through the admin. That is defensible for shops of this size and removes a procurement dependency from the critical path. Flag the email provider as a Phase 1/Phase 12 procurement item (self-serve signup in Phase 12 will need it anyway).

---

### §7 — French locale and MAD formatting (APP-01, APP-03)

#### The finding: "French conventions" has three different answers, verified

| Source | 1234567.89 renders as | Group separator |
|---|---|---|
| Django `fr` locale (`django/conf/locale/fr/formats.py:26`) | `1 234 567,89` | **U+00A0** no-break space |
| Browser / Node ICU `fr-FR` | `1 234 567,89` | **U+202F** narrow no-break space |
| Browser / Node ICU **`fr-MA`** | `1.234.567,89` | **U+002E full stop** |

[VERIFIED: `Intl.NumberFormat` run on Node v22.21.1 with full ICU, codepoints dumped; and the installed Django 6.1.1 locale file]

So an SPA using `fr-MA` shows `1.800,00 MAD` while the facture PDF rendered by the same system shows `1 800,00 MAD`. Same amount, same product, two different numbers on screen and on paper — and no test would catch it, because each side is internally consistent. **Reaching for a locale database is the bug.**

#### The recommendation

**Pin the format explicitly on both sides and drive both from one fixture file.**

```jsonc
// tests/fixtures/formats_mad.json  — read by pytest AND by vitest
{
  "separateur_decimal": ",",
  "separateur_milliers": " ",     // U+00A0. See the choice note below.
  "decimales": 2,
  "suffixe": " MAD",
  "cas": [
    ["0.05",       "0,05 MAD"],
    ["1800.00",    "1 800,00 MAD"],
    ["1234567.89", "1 234 567,89 MAD"],
    ["-12.30",     "-12,30 MAD"]
  ]
}
```

Server (`plateforme/projection/formats.py`) and client (`web/src/format/montant.ts`) each implement ~15 lines against this file. Two implementations are **unavoidable** — one renders a PDF in Python, the other renders the DOM in a browser — so the achievable goal is not "one formatter" but "one specification with two tested implementations." Say that plainly in the plan rather than promising a single formatter you cannot deliver.

**Separator choice, and it is a decision for the user, not for research.** I recommend **U+00A0 + French conventions** over ICU `fr-MA`'s full stop, for two reasons: a `.` thousands separator on a fiscal document is confusable with a decimal point by anyone reading it in an English or Arabic-numeral context, and it disagrees with what Django, WeasyPrint and every French-language accounting habit produce. U+00A0 rather than U+202F because Django already emits it, it is far more widely supported in PDF fonts (a narrow no-break space is a real missing-glyph risk in WeasyPrint at Phase 9), and it survives a CSV round-trip into Excel. **[ASSUMED — confirm with the optician or the comptable; see Assumptions A1.]**

**Do not implement this with `django.utils.formats` / `floatformat`.** Grouping there is off unless you set `USE_THOUSAND_SEPARATOR = True` (default `False`, verified), and it would give U+00A0 by accident rather than by decision — the next Django locale-data update could change it under you. An explicit ~15-line function is both shorter and pinned.

**Do not use `Intl.NumberFormat(..., {style:"currency", currency:"MAD"})` on the client either** — its output depends on the browser's ICU version, which you do not control. Use `Intl.NumberFormat` with explicit `useGrouping` and fixed digits only if you then normalise the separators against the fixture; a hand-written formatter is simpler and testable.

#### Decimal across the JSON boundary

`COERCE_DECIMAL_TO_STRING` defaults to `True` (verified: `rest_framework/settings.py:119`), so `DecimalField` serialises to `"1800.00"` — a **string**, and `JSON.parse` leaves it a string. That is correct and it is the only thing standing between CLAUDE.md #7 and a binary float. Pin it explicitly in `REST_FRAMEWORK` with a comment, and assert it:
`test_app03_un_montant_traverse_le_json_en_chaine_pas_en_flottant`.

On the TypeScript side the generated type is `string`. Rules:
1. **Parse to `Number` for display only.** A MAD amount under ~9e13 centimes is exact as a double once scaled; display is safe.
2. **Never do arithmetic on money in the SPA.** The enforcement is not a lint rule — it is an API design rule: **every total the UI shows must be a server-provided field** (`total_ht`, `total_tva`, `total_ttc`, `reste_a_payer`, `solde_caisse`). If the client never needs to add two amounts, it never can. Make this a stated convention in the plan and a review item; a serializer that omits a total the UI needs is the bug to catch.

#### Server-side French

- `LANGUAGE_CODE = "fr-fr"` and `USE_I18N = True` are **already set** in `config/settings/base.py`. With nothing activated, `get_language()` returns `settings.LANGUAGE_CODE`, so `gettext` resolves French on every thread. **No `LocaleMiddleware`** — see the correction above.
- **DRF ships French translations**: `rest_framework/locale/fr/LC_MESSAGES/django.mo` exists in the installed 3.18.1 (verified). So `"Ce champ est obligatoire."` comes out of the box; `test_app01_les_erreurs_de_lapi_sont_en_francais` asserts it rather than asserting Django works.
- Model `verbose_name`s and `TextChoices` labels in this codebase are already French (`ClientStatus`, `SensEcriture`). Keep that; it is what makes `drf-spectacular` emit French enum descriptions into the schema, and thence into the SPA.
- Dates: `SHORT_DATE_FORMAT = "d/m/Y"` from Django's `fr` locale; `Intl.DateTimeFormat("fr-FR")` gives `14/09/2026`. These two **agree** — verified — so dates are the easy half. Pin `fr-FR` (not `fr-MA`, which also gives `14/09/2026` but is one ICU update away from not).
- `TIME_ZONE = "UTC"` is load-bearing for PgBouncer and must not be changed to `Africa/Casablanca`. **Convert for display, in the formatter, not in settings.** Morocco is UTC+1 year-round except a Ramadan shift to UTC+0 — a real source of off-by-one-day bugs on a "CA du jour" figure at Phase 10. Note it now; do not solve it now.

---

### §8 — The app shell

**Same-origin from day one. This is the decision that removes the most work.**

```ts
// web/vite.config.ts
server: { proxy: { "/api": "http://127.0.0.1:8010", "/static": "http://127.0.0.1:8010" } }
```
With the dev server proxying `/api`, the browser only ever sees one origin. Consequences: no CORS in dev, no `django-cors-headers`, no `CORS_ALLOW_CREDENTIALS`, no preflight, and the session cookie and CSRF token behave exactly as they will in production (where the built SPA is served from the same origin, `/api/` routed to gunicorn). Every one of the classic "cookie works locally but not in prod" failures is designed out.

**What the shell is, minimally, in Phase 3:**

| Piece | Content |
|---|---|
| Build | Vite + `@vitejs/plugin-react` + TS 5.9.3, strict mode on |
| API client | `npm run api:types` -> `openapi-typescript src/api/schema.yml -o src/api/types.gen.ts`. `schema.yml` is **committed** and regenerated by `manage.py spectacular --file web/src/api/schema.yml --fail-on-warn`; CI fails on a diff. That is TESTING.md's "the OpenAPI schema does not change silently." |
| Fetch | `openapi-fetch` `createClient<paths>({ baseUrl: "/api", credentials: "include" })` + a middleware injecting `X-CSRFToken` and mapping 401 -> sign-out |
| Server state | `@tanstack/react-query` + `openapi-react-query`; a global 401 handler clearing the auth context |
| Auth | `AuthProvider` bootstrapping from `GET /api/auth/moi/`; `<RequireAuth>` route wrapper; `<RequirePermission code="...">` for nav items and route elements |
| Routing | `react-router-dom` 7, one protected layout route + `/connexion` |
| Layout | Header with the raison sociale and the magasin selector (restricted to `acces.magasins`), a side nav whose items are filtered by `acces.permissions`, a content outlet, a French error boundary |
| Formatting | `src/format/montant.ts` and `date.ts`, tested by vitest against the shared fixture |
| Accounts UI | The permission **checklist** — a flat list of the ~20 codes with a switch each, grouped by area, with **no tier presets**. PERM-03 is a checkbox list; resist the urge to add "Gérant standard" buttons. |

**The UI permission filter is convenience, never enforcement.** Hiding a nav item is UX; the server-side queryset filter and the projection are the control. Say this in the plan so that no task is written as "hide X in the UI" and treated as done.

**Deliberately deferred:**

| Deferred | To | Why |
|---|---|---|
| `react-i18next` / any i18n framework | Never, unless Arabic UI is requested | One language. Plain French strings. Note the cost honestly: retrofitting i18n across ~60 components later is a week. BRAND-04 is Arabic *content* in printed documents, not an Arabic *interface*. |
| A component library | Phase 4, when the first real forms land | Pick one then (dense tables and keyboard flows are the real criteria, per STACK.md's RNW rejection). Do **not** hand-roll one. |
| `react-hook-form` / form validation | Phase 4 | Phase 3 has one form (login). |
| Theming / branding tokens | Phase 9 (BRAND-01) | But **use CSS custom properties for colours now**, so Phase 9 sets variables instead of rewriting styles. One-line cost, large saving. |
| Data tables, virtualisation | Phase 5 | |
| Charts | Phase 10 | |
| E2E / Playwright | Phase 11 per TESTING.md §2 | |
| Anything offline | Never (CLAUDE.md #1) | |

---

## Attack Surface — how each guarantee could be walked around

Phase 2 shipped a cross-tenant hole because three research passes reasoned only at the Python layer. Here is the equivalent exercise for Phase 3 — and it opens with the most important admission.

> **There is no layer below the application for per-gérant permissions, and pretending otherwise would be the same mistake in a new costume.** Tenant isolation has `REVOKE CONNECT ... FROM PUBLIC` beneath it. Field and magasin permissions have nothing: every user of one client shares the single PostgreSQL role `optique_uNNNNNN`, so the database cannot distinguish the owner from a gérant. The whole guarantee is Python.
>
> **Could we add one?** Per-gérant PostgreSQL roles with column-level `GRANT`s would be real defence in depth — and it is **rejected on measured grounds**: PgBouncer pools are keyed by `(user, database)`, so N gérants per client multiplies the pool count by N, directly attacking the connection budget that TENANT-08 measured at 300 aliases / 4 connections. It would trade a proven property for an unproven one.
>
> **Therefore the compensating control is enumeration, not depth:** the registry is enumerable, the conformance test iterates it, the classification check refuses unclassified fields, and grant changes are journalled. That is the honest security story and it should be written that way in the phase summary.

| # | Route around the guarantee | What closes it |
|---|---|---|
| **A-03-01** | **Django admin.** An owner or gérant given `is_staff` reaches `/admin/`, where `TenantMiddleware` binds *their* client (resolution is by `client_id`, not by path — `config/urls.py`'s docstring is wrong about this) and every registered `ModelAdmin` runs unprojected. The control-plane `ClientAdmin` also exposes every optician's `db_name`, `db_host` and `db_password_encrypted`. | (1) The `CHECK` constraint in §1 makes `is_staff`/`is_superuser` impossible on a user with a `client` — enforced in the database, so `queryset.update()` and a shell cannot bypass it. (2) A custom `AdminSite.has_permission` requiring `is_superuser and user.client_id is None`. (3) **Never register a business model in the admin** — assert it: `test_perm06_aucun_modele_metier_n_est_enregistre_dans_ladmin` iterating `admin.site._registry`. (4) Fix the `urls.py` docstring. |
| **A-03-02** | **Management command.** `dumpdata`, or any future export command, runs with no user and therefore no projection. | `dumpdata` on a business app already raises `NoTenantBound` (no context bound outside middleware) — that half is free. The rule to add: **any command that produces a client-facing artefact takes `--utilisateur` and builds its output through `contexte_document`/`exporter_csv` with a real `Acces`.** Operator-level unprojected access is accepted by design, but it must be *named* as operator access. |
| **A-03-03** | **Celery task.** A task rendering a PDF or an export receives `client_id` and does not know *who* asked, so it renders the owner's view and emails it to a gérant. | The document/export task signature is `(*, client_id, acting_utilisateur_id, ...)`; the task recomputes `acces_pour(...)` inside the bound tenant context. Never pass an `Acces` or a model instance (already forbidden by `TenantTask`'s docstring). Test: `test_perm06_toute_tache_de_rendu_exige_acting_utilisateur_id` — iterate the task registry, assert the signature. |
| **A-03-04** | **Raw / `.values()` / `.annotate()`.** `Response(qs.values("prix_achat"))` or `qs.annotate(marge=F("pv")-F("pa"))` never touches a serializer, so the projection is simply absent. **This is the structural weakness of a serializer-based projection and it must be stated, not hidden.** | (1) A source-level test that no view module returns a `ValuesQuerySet` — the same idiom as `test_tenant06_management_command_delegates_to_provision_client`. (2) Derived protected values live behind a queryset method that takes the access object: `VenteQuerySet.avec_marge(acces)` returns the annotation only when `acces.peut(VENTE_VOIR_MARGE)`. (3) Code review rule: an `annotate()` that produces money is a registry question. |
| **A-03-05** | **Mass assignment on account creation.** An owner POSTing `{"client": 7, "est_proprietaire": true, "is_staff": true}` to `/api/comptes/`. | `client`, `est_proprietaire`, `is_staff`, `is_superuser` and `derniere_connexion_ip` are **never** serializer inputs; `client` is forced from `request.acces.client_id` in `perform_create`. Plus the DB constraint (A-03-01) as the backstop. Test: `test_perm02_un_proprietaire_ne_cree_un_compte_que_dans_son_propre_client`. |
| **A-03-06** | **The browsable API.** DRF's HTML renderer draws forms from `get_fields()` — which is projected, so it is less bad than it looks — but it also renders related-object `__str__` in `<select>` dropdowns, enumerating rows the caller may not be allowed to see. | `DEFAULT_RENDERER_CLASSES = ["...JSONRenderer"]` in base settings; add `BrowsableAPIRenderer` in `local.py` only. Test: `test_perm06_le_renderer_html_est_absent_hors_developpement`. |
| **A-03-07** | **Ordering / filter / search parameters as an oracle.** `?ordering=prix_achat` leaks the total ordering of a hidden field; `?prix_achat__gt=1500` recovers an exact value by binary search in ~20 requests. **The field is never in a response and is fully disclosed anyway.** | `OrderingFilter.ordering_fields` and `filterset_fields` must be **explicit allowlists derived from the projection** — a `ProjectedOrderingFilter.get_valid_fields()` that subtracts `champs_interdits`. An unpermitted value must return **400**, not be silently ignored (silent ignore is also an oracle: the result order changes). Test: `test_perm06_un_champ_protege_ne_peut_ni_trier_ni_filtrer`. |
| **A-03-08** | **Nested serializers.** `ArticleSerializer` is safe on its own, but Phase 6 nests it inside `LigneVenteSerializer` using a plain `ModelSerializer` and `prix_achat` reappears. | The registry is keyed by **`app.Model.field`**, not by serializer class, so `SerializerProjete` protects it wherever it appears — *provided the nested serializer also inherits `SerializerProjete`*. The `projection.E001` classification test is what enforces that: it walks `ModelSerializer.__subclasses__()` and fails on any that exposes a registry-protected field without the mixin. |
| **A-03-09** | **`/api/schema/` as a per-user document.** `build_mock_request` copies `request.user`, so the served schema would vary by caller (verified, `plumbing.py:1288`). | The `GET_MOCK_REQUEST` override pinning `Acces.SCHEMA` (§3). Test: `test_perm06_le_schema_est_identique_pour_le_proprietaire_et_le_gerant`. |
| **A-03-10** | **`.using(alias)` and object-level bypass**, inherited from Phase 2 (Pitfall 9). Unchanged here, but now a *gérant* is a potential actor, not only code. | Unchanged: business tables do not exist on `default`, so a bypass gets `relation does not exist`. Nothing to add; do not weaken it. |
| **A-03-11** | **Credential stuffing against one global login address.** Every optician in the fleet shares `/api/auth/connexion/`. | `ScopedRateThrottle` at `10/min` per IP on the login scope; optionally `django-axes` for per-username lockout. Argon2 hashing. `login()` cycles the session key, so session fixation is handled by Django. Test: `test_perm01_la_connexion_est_limitee_en_debit`. |
| **A-03-12** | **Session rows on a shared table.** `django_session` lives on the control plane and is shared fleet-wide; an unbounded table is a DoS-by-growth and a forensic liability. | `clearsessions` on Celery Beat. Sessions hold only a user pk and a hash — no client data — so there is no cross-tenant content there, but say so explicitly rather than assuming. |
| **A-03-13** | **Error messages.** A `ValidationError` echoing a unique-constraint value, or a DRF 400 whose *keys* reveal that a protected field exists. | Because the field is dropped from `get_fields()`, it cannot appear in a validation error for that serializer. `NoTenantBound` must never reach a response body as-is — already a Phase 2 rule (ASVS V7); extend it to `Acces` resolution failures. |

---

## Don't Hand-Roll

| Problem | Don't build | Use | Why |
|---|---|---|---|
| Password hashing | Anything | `Argon2PasswordHasher` + `argon2-cffi` | Django ships the backend. Parameters, salting and upgrade-on-login are solved. |
| Session lifecycle, fixation, expiry | A token table | `django.contrib.sessions` + `login()`/`logout()` | `login()` cycles the key; `logout()` flushes. Both source-verified behaviours you would otherwise re-derive. |
| Per-request deactivation check | An `is_active` middleware | `ModelBackend.get_user` | Already does it (`backends.py:235-240`). Adding a second check is dead code that will drift. |
| CSRF double-submit | A custom header scheme | `CsrfViewMiddleware` + `SessionAuthentication.enforce_csrf` | Constant-time comparison, cookie masking, `Origin` checks, trusted-origin handling. |
| OpenAPI -> TypeScript | A hand-written `api.ts` | `drf-spectacular` + `openapi-typescript` | A hand-written client is a second contract that silently drifts — precisely the PERM-06 failure mode, applied to types. |
| Money formatting | `toLocaleString()` alone | A pinned formatter + shared fixture | The locale databases disagree three ways (§7). This is verified, not hypothetical. |
| Decimal transport | `float(montant)` anywhere | `COERCE_DECIMAL_TO_STRING = True` | CLAUDE.md #7. It is already the default; the work is pinning and testing it. |
| Object-level permissions | `django-guardian` | A grant table (§4) | Guardian cannot work here — its FKs would have to cross the control-plane/tenant boundary. |
| Role tiers | A `role` column, "presets" | Rows in `DroitAccorde` | CLAUDE.md #6 and the only differentiator FEATURES.md found here. A preset is a tier with a friendly name. |

---

## Common Pitfalls

**P1 — A new app forgets `CONTROL_PLANE_APPS` and `manage.py check` fails at the worst moment.** `comptes`, `projection`, `drf_spectacular` and (if used) `axes` all need classifying; `tenancy.E001` exempts only `django.*` names (`checks.py:29-32`). Add each to `router.py` in the **same commit** as `INSTALLED_APPS`.

**P2 — The projection fails open.** `getattr(request, "acces", None)` followed by `if acces is None: return fields` leaks every protected field on any path where the middleware did not run. Default to `Acces.ANONYME` (empty permission set), never to `None`, and never to "allow."

**P3 — `if est_proprietaire: return fields` as a shortcut.** A second code path that a bug can reach for a non-owner. Materialise the owner's full permission and magasin sets in `acces_pour()` so `peut()` and the queryset filter have exactly one branch each. Assert the absence of the shortcut with a source-level test.

**P4 — Filtering magasins in `list()` instead of `get_queryset()`.** The detail route stays open. `get_object()` goes through `get_queryset()`; `list()` does not cover it.

**P5 — `PrimaryKeyRelatedField(queryset=Magasin.objects.all())`.** A cross-magasin write, accepted with a 201. Scope every related-field queryset.

**P6 — Redacting an aggregate after computing it.** You cannot unsee a scalar. Aggregate over the scoped queryset.

**P7 — Swapping `AUTH_USER_MODEL` after `auth`/`admin` migrations exist.** Recreate the control-plane development database in Wave 0, and run the blocking `SELECT count(*) FROM control_plane_client WHERE status='active'` pre-check first.

**P8 — `drf-spectacular` serving a per-user schema.** Verified behaviour (`plumbing.py:1288`). Pin `GET_MOCK_REQUEST`.

**P9 — A protected field marked `required` in the schema.** The generated TS claims a key that will not be there. The postprocessing hook fixes it; `COMPONENT_NO_READ_ONLY_REQUIRED = True` is the wrong blunt instrument (it would make `id` optional too).

**P10 — A Django template silently rendering a hidden field as empty.** `string_if_invalid` defaults to `""`. Iterate a projected column list in document templates; assert the *value* is absent from the HTML.

**P11 — `USE_L10N`.** Removed from Django. Setting it does nothing. Do not let a plan task add it.

**P12 — `LocaleMiddleware`.** Makes the UI language a client-controlled input and adds `Vary: Accept-Language`. Not needed for a single-language product.

**P13 — `SESSION_SAVE_EVERY_REQUEST = True`.** One write per request to a fleet-shared control-plane table.

**P14 — Forgetting `clearsessions`.** `django_session` grows without bound.

**P15 — `.reset(token)` creeping back in.** `AccesMiddleware` will be tempted to use a contextvar for `request.acces`. **Do not** — put it on the request object, where the request's own lifetime bounds it. If a contextvar is ever genuinely needed, it obeys the same `set(_UNSET)`-in-`finally` rule as `plateforme/tenancy/context.py`, and the ban on the token-based undo under `plateforme/tenancy/` should be extended to `plateforme/comptes/`.

**P16 — Testing with one magasin.** The same class of blind spot as testing with one tenant: a scoping bug that always returns the same magasin passes every test. The fixtures must supply **two magasins per tenant**, as they already supply two tenants.

---

## Code Examples

### The four-consumer wiring (the whole of PERM-06 in one view)

```python
# config/settings/base.py
SPECTACULAR_SETTINGS = {
    "TITLE": "API Optique",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Pin the projection during schema generation so the served document is identical
    # for every user and matches the committed schema.yml.
    # (drf_spectacular/plumbing.py:1288 copies request.user from the caller otherwise.)
    "GET_MOCK_REQUEST": "plateforme.projection.schema.requete_mock_schema",
    # The registry also drives `required`, so the generated TS is `prix_achat?: string`.
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "plateforme.projection.schema.marquer_champs_proteges_optionnels",
    ],
}
```

### The conformance test — the thing that actually makes PERM-06 true

```python
# tests/test_projection.py
@pytest.mark.parametrize("rendu", ["api", "export", "document"])
@pytest.mark.parametrize("cle,code", sorted(CHAMPS_PROTEGES.items()) or [("<fixture>", None)])
def test_perm06_champ_protege_absent_de_lapi_de_lexport_et_du_document(rendu, cle, code, ...):
    """PERM-06. One table-driven test over the registry x the renderers, exactly as
    TESTING.md section 5 requires. Adding one registry line in Phase 8 adds three
    assertions here automatically; a renderer added in Phase 9 that does not read the
    registry fails the moment it joins the `rendu` list.

    While CHAMPS_PROTEGES is empty (Phase 3 — prix_achat arrives in Phase 8), the
    vehicle is a test-only resource declared in tests/, so the machinery is proven
    end-to-end without pre-empting Phase 8's schema.
    """
```

### Fail-closed access resolution

```python
# plateforme/comptes/acces.py
def acces_pour(utilisateur) -> Acces:
    if utilisateur is None or not getattr(utilisateur, "is_authenticated", False):
        return Acces.ANONYME
    if utilisateur.client_id is None:
        return Acces.ANONYME          # an operator has no business access, by design

    if utilisateur.est_proprietaire:
        codes = frozenset(Permission.values)          # MATERIALISED, not special-cased
    else:
        codes = frozenset(utilisateur.droits.values_list("code", flat=True))

    # Magasin codes are values, not FKs. Intersect with the LIVE active magasins in the
    # client database, so a grant naming a deactivated magasin grants nothing.
    if utilisateur.est_proprietaire:
        magasins = Magasin.objects.filter(actif=True)
    else:
        accordes = utilisateur.acces_magasins.values_list("magasin_code", flat=True)
        magasins = Magasin.objects.filter(actif=True, code__in=list(accordes))

    return Acces(
        utilisateur_id=utilisateur.pk,
        client_id=utilisateur.client_id,
        est_proprietaire=utilisateur.est_proprietaire,
        permissions=codes,
        magasins_ids=frozenset(magasins.values_list("id", flat=True)),
    )
```

---

## Pre-flight State Check (run before planning tasks)

Not a rename phase, but two pieces of runtime state decide the shape of Wave 0.

| Item | Question | Action |
|---|---|---|
| Control-plane database | `SELECT count(*) FROM control_plane_client WHERE status='active'` — are there real clients? | 0 => recreate the control-plane DB in Wave 0 and swap `AUTH_USER_MODEL` cleanly. >0 => this becomes a data migration needing its own plan. **Blocking.** |
| Existing dev superuser | Any `auth_user` rows created during Phase 2 development? | They are destroyed by the swap. Re-create the operator with `createsuperuser` after. |
| `.env` / secrets | Does anything reference `SIMPLE_JWT_*`? | Grep before writing settings; none expected. |
| Concurrent work | `config/settings/base.py` gained `PGBOUNCER_HOST`/`PGBOUNCER_PORT`, and `tests/test_pgbouncer_auth.py` appeared, *during* this research session | Phase 2's verification pass (plan 02-08, PgBouncer `auth_query`) landed while this was being written. Rebase before planning; the Phase 3 settings edits touch the same file. |
| `.planning/STATE.md` | Front-matter now reads 7/7 plans, Phase 2 complete and verified (107 tests passing); the **body** still says "Plan: 3 of 7 complete ... next is 02-04" and "Progress 43%" | The header and body disagree. Fix the body during Phase 3's Wave 0 so the planner is not misled. |
| `.planning/STATE.md` decision log | The 02-03 entry still reads *"Phase 3 swaps the lookup for a signed JWT client_id claim"* | Supersede it with the session-cookie decision (correction 1) in the same commit that edits CLAUDE.md's stack row. |
| New settings surface | Plan 02-08 added `PGBOUNCER_HOST`/`PGBOUNCER_PORT` and a SQL init script | Confirms pitfall P1's shape: Phase 3's `comptes`, `projection`, `drf_spectacular` and `axes` each need a `CONTROL_PLANE_APPS` entry, or `manage.py check` fails on the next run. |

---

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | The MAD format should follow **French** conventions (U+00A0 group separator) rather than ICU `fr-MA`'s full stop | §7 | Every amount on screen and on every facture is formatted in a way Moroccan opticians find odd. Cheap to change *before* the fixture is written; expensive after Phase 9's PDFs exist. **Ask the optician.** |
| A2 | Exactly one owner per client business (`UniqueConstraint` on `client` where `est_proprietaire`) | §1 | A business with two equal partners cannot be modelled. Ask; relaxing the constraint later is a one-line migration, tightening it is not. |
| A3 | No user belongs to two client businesses | §1 | Would force a `Membership` table. The `Acces` seam contains the blast radius, but it is a migration. |
| A4 | Password reset without email (owner resets gérants, operator resets owners) is acceptable for v1 | §6 | If unacceptable, Phase 3 gains a transactional-email procurement dependency that is currently nobody's task. |
| A5 | ~20 permission codes as listed is roughly the right catalogue | §4 | Codes are cheap to add; a *missing dimension* (e.g. per-magasin permissions rather than per-magasin access) is not. Review the list with a real optician. |
| A6 | `drf-spectacular` 0.30.0 works on Django 6.1.1 | Stack | Classifiers stop at 6.0. Prove it in Wave 0 with `manage.py spectacular --fail-on-warn` before anything depends on it. |
| A7 | `django-axes` 8.3.1 works on Django 6.1.1 | Stack | Same; it is optional, so dropping it costs only per-username lockout. |
| A8 | Phase 3 ships an HTML document renderer, not a PDF one | Correction 4 | If a stakeholder expects a printable facture in Phase 3, scope grows into Phase 9. |
| A9 | Serving the built SPA same-origin in production is acceptable (no separate CDN origin) | §8 | A separate origin re-introduces CORS and `SameSite=None`, which would materially weaken the session argument. Confirm with the Phase 1 hosting decision. |

---

## Open Questions

1. **Is there any deployed client data?** — determines whether the `AUTH_USER_MODEL` swap is a database recreation or a migration plan. *Blocking Wave 0.* Answer with the SQL above.
2. **MAD separator convention (A1).** Needs a Moroccan optician or the comptable, not more searching. Pair it with the four Phase 6 facturation questions already queued for Phase 1.
3. **Does the export need Excel, or is CSV enough?** If Excel, `openpyxl` 3.1.5 (2024-06) is the answer and the projection is unchanged. If CSV, note that French/Moroccan Excel expects `;` separators and a UTF-8 BOM — otherwise the optician opens the export and sees one column. Recommend CSV with `;` + BOM for v1.
4. **Transactional email provider.** Absent from the stack. Not blocking Phase 3 if A4 holds, but Phase 12's self-serve signup cannot work without it. Raise with Phase 1 procurement.
5. **Do gérants need per-magasin *permissions*, or only per-magasin *access*?** The design grants a flat permission set plus a magasin set. "Karim may take payments in Maârif but only view stock in Anfa" would need `DroitAccorde.magasin_code`. Adding the column later is a migration plus a change to `Acces`; the `peut()` signature would gain a magasin argument, touching every call site. **Worth five minutes with a real optician before the plan is written** — it is the one decision here that is genuinely expensive to reverse.

---

## Environment Availability

Probed 2026-09-14 on the development machine.

| Dependency | Required by | Available | Version | Fallback |
|---|---|---|---|---|
| Node | SPA build, `openapi-typescript`, vitest | yes | v22.21.1, full ICU | — |
| npm | SPA packages | yes | 11.7.0 | — |
| Python 3.13 (venv) | Backend | yes | `.venv/bin/python3.13`, Django 6.1.1 installed | — |
| `uv` | Dependency management | yes | 0.8.19 | — |
| DRF French locale | APP-01 | yes | `rest_framework/locale/fr/LC_MESSAGES/django.mo` present in 3.18.1 | — |
| Django `fr` locale formats | APP-03 | yes | `django/conf/locale/fr/formats.py` | — |
| Docker + Compose (PostgreSQL 18, PgBouncer, Redis) | Test suite | yes (per the 02-RESEARCH probe) | 28.3.3 | — |
| `drf-spectacular` | PERM-06 schema hook | **no** — not installed | — | none — must install and prove on Django 6.1 in Wave 0 |
| `argon2-cffi` | Password hashing | **no** — not installed | — | PBKDF2 (Django default) works; Argon2 is a strict improvement |
| Transactional email | Password reset | **no** | — | Owner/operator-initiated resets (A4) |

**Missing with no fallback:** none. **Missing with fallback:** email (fallback A4), Argon2 (fallback PBKDF2).

**Note for the planner:** Node 22 ships full ICU, so `Intl` is reliable in CI — but the *browser's* ICU is not yours to pin, which is the second reason §7 recommends a hand-written formatter over `Intl` currency formatting.

---

## Validation Architecture

### Test framework

| Property | Value |
|---|---|
| Backend framework | `pytest` 9.1.1 + `pytest-django` 4.14.0 (existing) |
| Frontend framework | `vitest` 4.1.11 — **Wave 0 gap**, does not exist yet |
| Config | `pyproject.toml [tool.pytest.ini_options]` (existing); `web/vitest.config.ts` (new) |
| Quick run | `uv run pytest -x -q -m "not slow"` and `npm --prefix web test -- --run` |
| Full suite | `uv run pytest --create-db` + `npm --prefix web test -- --run` + the schema diff gate |
| New marker | none needed; the projection tests are ordinary integration tests |

### Success criteria -> named, requirement-citing tests

**Criterion 1 — "An optician opens the web application, sees a French interface, signs in, and is still signed in in a new session"**

| Test | Cites | Command |
|---|---|---|
| `test_app01_les_erreurs_de_lapi_sont_en_francais` | APP-01 | `pytest tests/test_locale.py -x` |
| `test_perm01_la_connexion_etablit_une_session_et_lie_le_client` — POST credentials, assert 200, assert the next request binds `tenant_<pk>` and reads client data | PERM-01 | `pytest tests/test_comptes_auth.py -x` |
| `test_perm01_le_cookie_de_session_survit_a_la_fermeture_du_navigateur` — assert `Max-Age` present, `SESSION_EXPIRE_AT_BROWSER_CLOSE is False`, age >= 30 days. *This is the literal reading of "across sessions."* | PERM-01 | idem |
| `test_perm01_la_deconnexion_invalide_la_session_immediatement` | PERM-01 | idem |
| `test_perm01_la_connexion_est_limitee_en_debit` — 11 attempts -> 429 | PERM-01 / A-03-11 | idem |
| `test_perm01_une_requete_api_sans_jeton_csrf_est_refusee` | PERM-01 | idem |

**Criterion 2 — "The owner creates a gérant, grants and revokes individual permissions without picking a role tier, and deactivates the account later"**

| Test | Cites |
|---|---|
| `test_perm02_un_proprietaire_ne_cree_un_compte_que_dans_son_propre_client` — `client` forced server-side; a payload naming another client is ignored | PERM-02 / A-03-05 |
| `test_perm02_un_compte_desactive_est_refuse_des_la_requete_suivante` — no logout, no token expiry; asserts the `ModelBackend.get_user` behaviour *through the API*, not by testing Django | PERM-02 |
| `test_perm02_un_utilisateur_client_ne_peut_jamais_etre_operateur` — via `queryset.update(is_staff=True)`, proving it is a DB constraint and not `clean()` | PERM-02 / A-03-01 |
| `test_perm03_un_droit_est_une_ligne_pas_un_palier` — grant one code, assert no other code becomes true; assert no model in `comptes` has a `role`/`tier`/`niveau` field | PERM-03 |
| `test_perm03_la_revocation_prend_effet_sans_reconnexion` — **the test that would fail under JWT** | PERM-03 |
| `test_perm03_un_proprietaire_ne_peut_pas_accorder_a_un_utilisateur_dun_autre_client` | PERM-03 |
| `test_perm03_le_journal_enregistre_qui_a_accorde_quoi_et_quand` | PERM-03 |

**Criterion 3 — "A gérant sees only the magasins and data the owner granted; prix d'achat, margin and business-wide revenue are absent unless granted"**

| Test | Cites |
|---|---|
| `test_perm04_un_gerant_ne_voit_que_les_magasins_accordes_en_liste_et_en_detail` — **both routes**, two magasins per tenant | PERM-04 / P4 |
| `test_perm04_un_gerant_ne_peut_pas_ecrire_dans_un_magasin_non_accorde` — POST -> 400 | PERM-04 / A-03-05 |
| `test_perm04_un_droit_obsolete_sur_un_magasin_inactif_n_accorde_rien` | PERM-04 |
| `test_perm04_lacces_du_proprietaire_est_lensemble_complet_et_non_un_filtre_saute` — assert the materialised set, plus a source-level assertion that `peut()` has no `est_proprietaire` branch | PERM-04 / P3 |
| `test_perm05_un_agregat_est_calcule_sur_le_queryset_deja_filtre` — a gérant's CA equals the sum over their magasins only | PERM-05 |
| `test_perm05_le_catalogue_declare_prix_achat_marge_et_ca_global` — the codes exist in Phase 3 even though the fields arrive in Phases 8 and 10 | PERM-05 |
| *(live verification of PERM-05 belongs to Phase 8 — see correction 3)* | |

**Criterion 4 — "A field hidden from a gérant is equally absent from the API response, an export and a printed document"**

| Test | Cites |
|---|---|
| `test_perm06_champ_protege_absent_de_lapi_de_lexport_et_du_document` — **parametrized over `CHAMPS_PROTEGES` x {api, export, document}**; asserts key-absence for JSON, column-absence for CSV, value-absence for HTML | PERM-06 |
| `test_perm06_tout_champ_de_modele_expose_est_classe` — every `ModelSerializer` field is in `CHAMPS_PROTEGES` or `CHAMPS_PUBLICS` | PERM-06 / A-03-08 |
| `test_perm06_le_schema_est_identique_pour_le_proprietaire_et_le_gerant` | PERM-06 / A-03-09 |
| `test_perm06_un_champ_protege_est_optionnel_dans_le_schema` — absent from the component's `required` array | PERM-06 / P9 |
| `test_perm06_le_schema_committe_correspond_au_schema_genere` — `spectacular --fail-on-warn` + a diff gate in CI. *TESTING.md section 2's "API contract" level.* | PERM-06 |
| `test_perm06_un_champ_protege_ne_peut_ni_trier_ni_filtrer` — `?ordering=` -> 400 | PERM-06 / A-03-07 |
| `test_perm06_un_champ_protege_ne_peut_pas_etre_ecrit_par_un_gerant` — assert the value is *unchanged*, not that a 400 occurs | PERM-06 |
| `test_perm06_aucune_vue_ne_renvoie_un_values_queryset` — source-level | PERM-06 / A-03-04 |
| `test_perm06_aucun_modele_metier_n_est_enregistre_dans_ladmin` | PERM-06 / A-03-01 |
| `test_perm06_le_renderer_html_est_absent_hors_developpement` | PERM-06 / A-03-06 |
| `test_perm06_toute_tache_de_rendu_exige_acting_utilisateur_id` | PERM-06 / A-03-03 |
| `test_perm06_lacces_absent_vaut_aucun_droit` — a serializer with no `request` in context drops every protected field (fail-closed) | PERM-06 / P2 |

**Criterion 5 — "Amounts, dates and numbers render in MAD and French conventions everywhere"**

| Test | Cites |
|---|---|
| `test_app03_un_montant_traverse_le_json_en_chaine_pas_en_flottant` — asserts `isinstance(..., str)` **and** `COERCE_DECIMAL_TO_STRING is True` | APP-03 / CLAUDE.md #7 |
| `test_app03_le_formatage_serveur_respecte_la_fixture_partagee` (pytest) | APP-03 |
| `format.test.ts` -> `le formatage client respecte la fixture partagée` (vitest, **same JSON file**) | APP-03 |
| `test_app03_la_date_courte_est_au_format_jj_mm_aaaa` | APP-03 |
| `test_app03_aucun_montant_n_est_un_flottant_dans_une_reponse` — walk a response payload, assert no `float` | APP-03 |

### Sampling rate
- **Per task commit:** `uv run pytest -x -q -m "not slow"` + `npm --prefix web test -- --run` (target under 30 s combined).
- **Per wave merge:** full `uv run pytest --create-db`, plus `manage.py spectacular --file web/src/api/schema.yml --fail-on-warn` and a clean-tree check on the regenerated `schema.yml`.
- **Phase gate:** full suite green, `manage.py check` clean (`tenancy.E001` and `projection.E001`), `migrate_all --check` exit 0, schema diff clean, and `npm --prefix web run build` succeeds.

### Wave 0 gaps
- [ ] Control-plane database recreated and `AUTH_USER_MODEL = "comptes.Utilisateur"` set, after the blocking pre-flight SQL check
- [ ] `comptes`, `projection`, `drf_spectacular` (+ `axes`) added to `CONTROL_PLANE_APPS` **in the same commit** as `INSTALLED_APPS`
- [ ] `uv add drf-spectacular==0.30.0 argon2-cffi==25.1.0`, then prove `manage.py spectacular --fail-on-warn` on Django 6.1.1
- [ ] `tests/factories.py` — `UtilisateurFactory`, `ProprietaireFactory`, `GerantFactory`, `DroitFactory`; `conftest.py` gains **two magasins per tenant**
- [ ] `tests/fixtures/formats_mad.json` — the shared format fixture, written before either formatter
- [ ] `tests/test_comptes_auth.py`, `tests/test_comptes_droits.py`, `tests/test_projection.py`, `tests/test_magasin_acces.py`, `tests/test_locale.py`, `tests/test_schema_contrat.py`
- [ ] `web/` scaffold: `package.json`, `vite.config.ts` (with the `/api` proxy), `tsconfig.json`, `vitest.config.ts`, `web/tests/format.test.ts`
- [ ] CI step: regenerate `schema.yml` and fail on a dirty tree

---

## Security Domain

### Applicable ASVS categories

| Category | Applies | Control in this phase |
|---|---|---|
| V1 Architecture | **yes** | The trust boundary is documented explicitly, **including the admission that per-gérant permissions have no enforcement layer below Python** and why per-gérant PostgreSQL roles were rejected (PgBouncer pool keying vs TENANT-08). |
| V2 Authentication | **yes — core** | Argon2; session cookies over TLS; `login()` cycles the session key (fixation); `is_active` checked per request by `ModelBackend.get_user`; throttled login; optional `django-axes` lockout. Password reset is operator/owner-initiated (no email dependency). |
| V3 Session Management | **yes — core** | `Secure`, `HttpOnly`, `SameSite=Lax`, explicit 30-day age, `logout()` flushes, `clearsessions` scheduled, `django_session` on the control plane carries no client data. |
| V4 Access Control | **yes — core** | Vertical: the grant catalogue + `Acces.peut()`. Horizontal *within* a tenant: magasin queryset scoping in `get_queryset()` and in every related-field queryset. Horizontal *across* tenants: unchanged Phase 2 router. Fail-closed defaults. |
| V5 Input Validation | **yes** | `client`, `est_proprietaire`, `is_staff`, `is_superuser` never accepted from a payload; `ordering`/`filter` parameters are allowlists derived from the projection; DB `CHECK` constraints as the backstop to serializer validation. |
| V6 Cryptography | **yes** | Argon2 via `argon2-cffi`. Session keys from Django's `get_random_string`. Nothing hand-rolled. |
| V7 Error Handling & Logging | **yes** | `JournalDroit` for grant changes. `NoTenantBound` and `Acces` resolution failures never leak identifiers into a response. Sentry `before_send` scrubbing already in place. |
| V8 Data Protection | **yes** | Field-level projection is the control. The health-data boundary is unchanged: ordonnances remain in the client database; the control plane gains only identity and grants (CLAUDE.md #11). |
| V9 Communications | yes | Unchanged from Phase 2; `SESSION_COOKIE_SECURE` makes TLS mandatory in production. |
| V13 API | **yes** | JSON renderer only in production; the OpenAPI document is deterministic and committed; the browsable API is a development-only surface. |
| V14 Configuration | **yes** | `DEBUG=False`, `ATOMIC_REQUESTS` still absent, `COERCE_DECIMAL_TO_STRING=True`, renderer list, throttle rates — each asserted by a test so drift turns the suite red. |

### Threat patterns for this stack

| Pattern | STRIDE | Mitigation |
|---|---|---|
| Privilege escalation via `is_staff` on a client user -> operator admin | Elevation | DB `CHECK` constraint + superuser-only `AdminSite.has_permission` (A-03-01) |
| Mass assignment of `client` / `est_proprietaire` at account creation | Elevation | Fields excluded from serializer input; forced from `request.acces` (A-03-05) |
| IDOR on a magasin-scoped detail route | Info disclosure | Filter in `get_queryset()`, never `list()` (P4) |
| Cross-magasin write via a related-field pk | Tampering | `MagasinAutoriseField` scoped queryset (A-03-05) |
| Hidden-field oracle via `ordering` / filter parameters | Info disclosure | Projection-derived allowlists, 400 on a disallowed value (A-03-07) |
| Protected field re-exposed through a nested serializer | Info disclosure | Registry keyed by `app.Model.field` + `projection.E001` classification test (A-03-08) |
| Unprojected output from a Celery task or management command | Info disclosure | `acting_utilisateur_id` required; projection-driven rendering (A-03-02/03) |
| Unprojected output from `.values()` / `.annotate()` | Info disclosure | Source-level test; permission-aware queryset methods (A-03-04) |
| Per-user OpenAPI document | Info disclosure / integrity | `GET_MOCK_REQUEST` pinned to `Acces.SCHEMA` (A-03-09) |
| Credential stuffing on one global login address | Spoofing | Throttle + Argon2 + optional lockout (A-03-11) |
| CSRF on a cookie-authenticated API | Spoofing | `SessionAuthentication.enforce_csrf` + `SameSite=Lax` + same-origin |
| Session fixation | Spoofing | `django.contrib.auth.login()` cycles the session key |
| Unbounded `django_session` growth on a shared table | DoS | `clearsessions` on Beat (A-03-12) |

---

## Sources

### Primary (HIGH confidence — read directly this session)
- **Installed Django 6.1.1** (`.venv/lib/python3.13/site-packages/django/`): `contrib/auth/backends.py:96-101, 235-247` (`user_can_authenticate`, `ModelBackend.get_user`), `contrib/auth/__init__.py:278-308` (`get_user`, session hash verification), `conf/global_settings.py` (`USE_L10N` **absent**; `USE_THOUSAND_SEPARATOR=False`; `CSRF_HEADER_NAME`; `SESSION_*` defaults), `conf/locale/fr/formats.py:25-27` (`THOUSAND_SEPARATOR = "\xa0"`)
- **Installed DRF 3.18.1**: `authentication.py:112-140` (`SessionAuthentication.enforce_csrf`), `settings.py:119` (`COERCE_DECIMAL_TO_STRING: True`), `locale/fr/LC_MESSAGES/django.mo` present
- **drf-spectacular `master`** (tfranzel/drf-spectacular): `openapi.py:1075-1114` (`_map_serializer`, the `required` computation), `plumbing.py:1283-1299` (`build_mock_request` copies `request.user`), `:1502-1506` (`build_serializer_context`), `settings.py:36-38, 54-61, 97-102, 137, 237-245`
- **djangorestframework-simplejwt `master`**: `rest_framework_simplejwt/authentication.py:127-147` (DB hit + `is_active`), `tox.ini` (envlist ends at `dj60`), `setup.py` (classifiers end at Django 6.0)
- **Local Node v22.21.1, full ICU**: `Intl.NumberFormat` output and codepoints for `fr-MA` / `fr-FR` / `fr` — the three-way separator finding
- **This repository**: `plateforme/tenancy/{context,router,middleware,checks,tasks,provisioner}.py`, `plateforme/control_plane/models.py`, `domaine/{magasins,stock,caisse}/models.py`, `config/settings/{base,test}.py`, `config/urls.py`, `pyproject.toml`, the commit history
- **PyPI JSON API, 2026-09-14** — every backend version and release date above
- **npm registry, 2026-09-14** — every frontend version, release date, and the `typescript-eslint` peer range

### Secondary (MEDIUM confidence)
- `docs.djangoproject.com/en/6.1/topics/db/multi-db/` — auth/contenttypes/admin co-location (quoted via 02-RESEARCH.md Open Question 1)
- `docs.djangoproject.com/en/6.1/topics/auth/customizing/` — `AbstractBaseUser` without `PermissionsMixin`; the admin's `is_staff`/`has_perm`/`has_module_perms` requirements
- `.planning/phases/02-tenancy-foundation-control-plane/02-RESEARCH.md` — Open Questions 1 and 4, threat catalogue T-02-*, validation architecture idioms
- `.planning/research/FEATURES.md:107` — *"a checklist of ~20 permissions beats an RBAC engine"*

### Tertiary (LOW confidence — flagged, not relied on)
- `drf-spectacular` 0.30.0 and `django-axes` 8.3.1 on Django **6.1** — no classifier, no upper pin. Assumptions A6/A7; must be proven in Wave 0.
- The exact ~20 permission codes — a design proposal, not research. Assumption A5.
- The choice of `react-router-dom` over `@tanstack/react-router` — a judgement about build-step count on a solo project, not a measured comparison.

---

## Metadata

| Area | Confidence | Reason |
|---|---|---|
| Session vs JWT | **HIGH** | Four independent verified facts: middleware ordering (repo source), `ModelBackend.get_user` (Django source), simplejwt's DB hit (upstream source), simplejwt's Django 6.1 gap (PyPI + tox.ini) |
| User model shape | **HIGH** on the control-plane placement (already locked + confirmed), **MEDIUM** on FK-vs-Membership (a judgement; mitigated by the `Acces` seam) |
| Projection layer | **HIGH** on the drf-spectacular mechanics (read from master), **MEDIUM** on the registry design (a recommendation) |
| Grant model | **HIGH** on rejecting guardian (`allow_relation` makes it impossible), **MEDIUM** on the exact table shape |
| Magasin scoping | **HIGH** — follows from existing code and DRF's documented `get_object`/`get_queryset` relationship |
| Locale / MAD | **HIGH** — reproduced locally, codepoints dumped. The *choice* of separator is A1, unverified |
| SPA stack | **MEDIUM-HIGH** — versions registry-verified; the TypeScript 7 exclusion is hard-verified via peer metadata; router and generator choices are judgement |
| Attack surface | **MEDIUM-HIGH** — each route is concrete and each closure is implementable, but unlike Phase 2 there is **no layer below the application**, and that is stated rather than papered over |

**Research date:** 2026-09-14
**Valid until:** 2026-10-14 for versions (Vite, React, vitest and TanStack all moved within the last month — re-check at install). The Django/DRF/drf-spectacular internals are valid for the 6.1 / 3.18 / 0.30 lines; **re-verify `ModelBackend.get_user`, `SessionAuthentication.enforce_csrf` and `build_mock_request` when any of the three is upgraded.**
