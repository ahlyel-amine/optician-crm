---
phase: 03-comptes-permissions-app-shell
plan: 01
subsystem: comptes-socle
tags: [comptes, auth-user-model, argon2, admin, claude-md-12, revoke-connect, PERM-02, PERM-06, APP-03]
requires:
  - 02-01 (settings package, pinned stack, Compose topology)
  - 02-02 (control_plane.Client — the FK target)
  - 02-03 (router, tenancy.E001 check, TenantMiddleware)
provides:
  - comptes.Utilisateur as AUTH_USER_MODEL, on the control-plane database
  - three database-level guarantees about who may be an operator
  - an AdminSite reachable only by an operator carrying no client
  - REVOKE CONNECT on optique_control (CLAUDE.md #12, fourth instance)
  - tests/fixtures/formats_mad.json — the one money/date spec pytest and vitest both read
  - plateforme/projection/ — labelled shell for the PERM-06 registry
affects:
  - 03-02 (owner creates gérants — consumes Utilisateur and UtilisateurManager)
  - 03-03 (app shell / login — consumes session auth on this user model)
  - 03-04 (permission grants — FK to Utilisateur)
  - 03-05+ (projection registry — fills plateforme/projection/)
  - 03-10, 03-11 (server and client formatters — both read formats_mad.json)
tech-stack:
  added: [drf-spectacular==0.30.0, argon2-cffi==25.1.0]
  patterns:
    - guarantees as CheckConstraint, proven by going round the model with queryset.update()
    - the absence of a Django subsystem as the guarantee, asserted by a test
    - a custom AdminSite installed through AdminConfig.default_site, not mounted alongside
    - every new database gets its REVOKE and a wrong-principal test in the same change
key-files:
  created:
    - plateforme/comptes/models.py
    - plateforme/comptes/managers.py
    - plateforme/comptes/sites.py
    - plateforme/comptes/admin.py
    - plateforme/comptes/migrations/0001_initial.py
    - plateforme/projection/__init__.py
    - plateforme/projection/apps.py
    - tests/fixtures/formats_mad.json
    - tests/test_comptes_socle.py
  modified:
    - config/settings/base.py
    - config/urls.py
    - plateforme/tenancy/router.py
    - plateforme/tenancy/middleware.py
    - docker/postgres/init/00-databases.sql
    - tests/test_tenancy_context.py
    - pyproject.toml
    - uv.lock
decisions:
  - AUTH_USER_MODEL swapped by recreating the development control-plane database, not by a data migration — pre-flight found 0 clients
  - the FK is named `client` so the Phase 2 tenancy layer changes zero lines
  - no permissions mixin — Group is a role tier (CLAUDE.md #6), and its absence is the guarantee
  - the AdminSite class lives in sites.py, not admin.py, to avoid a silent LazyObject re-entrancy that drops registrations
  - AdminOperateurConfig lives in sites.py too, because Django scans apps.py with inspect.getmembers and cannot tell an imported AppConfig from a defined one
metrics:
  tasks: 3
  commits: 3
  tests-added: 7
  suite: 114 passed (107 before)
  completed: 2026-09-14
---

# Phase 3 Plan 01: Comptes — Socle Summary

`comptes.Utilisateur` is now `AUTH_USER_MODEL`, living in the control-plane database with
three database-enforced guarantees about who may reach the fleet admin; the admin itself
is gated on being an operator with no client; and `optique_control` finally refuses
`CONNECT` to `PUBLIC` — a live hole, confirmed open before the fix and closed by a test
that connects as the wrong principal.

## The pre-flight, and why it mattered

```
TOTAL: 0   ACTIVE: 0   ROWS: []
```

Run before anything else, and re-run inside the drop script immediately before the
`DROP DATABASE`. Non-zero would have stopped the plan: `django.contrib.admin`'s migrations
already reference `AUTH_USER_MODEL`, so swapping it over existing `auth`/`admin`
migrations is a multi-step data migration needing its own plan (`03-RESEARCH.md` P7). At
zero it is a database recreation, which is what happened.

**The database name was never typed.** The drop script derived it from
`settings.DATABASES["default"]["NAME"]` and refused to run on anything else.

## What is guaranteed, and by which layer

| Guarantee | Enforced by | Test |
|---|---|---|
| A client-bound account is never `is_staff` / `is_superuser` | `CheckConstraint un_utilisateur_client_n_est_jamais_operateur` | `test_perm02_un_utilisateur_client_ne_peut_jamais_etre_operateur` |
| The same, second layer | `AdminOperateurSite.has_permission` | `test_perm02_seul_un_operateur_sans_client_atteint_ladmin` |
| An owner belongs to a client | `CheckConstraint un_proprietaire_appartient_a_un_client` | `test_perm02_un_proprietaire_appartient_a_un_client` |
| One owner per client | partial `UniqueConstraint un_seul_proprietaire_par_client` | `test_perm02_un_seul_proprietaire_par_client` |
| No second permission system | absence of the permissions mixin | `test_perm02_utilisateur_n_expose_aucun_systeme_de_droits_django` |
| No business model in the admin | nothing from `domaine.` imported | `test_perm06_aucun_modele_metier_n_est_enregistre_dans_ladmin` |
| A client role cannot open the control plane | `REVOKE CONNECT ... FROM PUBLIC` | `test_perm02_un_role_client_ne_peut_pas_ouvrir_la_base_du_plan_de_controle` |

Two of these are worth singling out.

**The operator test goes round the model on purpose.**
`Utilisateur.objects.filter(pk=...).update(is_staff=True)` calls neither `save()`, nor
`full_clean()`, nor a signal. If that path succeeded, the only thing between an optician's
account and fleet management would be convention. It raises `IntegrityError`, for both
flags, tested separately — a model constraining only one would leave the other as a route.

**The registry test has a positive control.** A test that only asserts *absence* of
business models passes against an empty registry — for instance if `autodiscover()` never
ran. It now also asserts that `comptes.Utilisateur` and `control_plane.Client` *are*
registered, which is what makes the negative assertion mean something.

## CLAUDE.md #12, fourth instance — confirmed open, then closed

Measured before the fix, on the shared development cluster:

```
test_client_u028990 détient CONNECT sur optique_control   → assert True is False
```

`00-databases.sql` created `optique_control` and never took `CONNECT` away from `PUBLIC`,
which PostgreSQL grants on every new database. Any role on the cluster — including every
provisioned `optique_u######` client role — could open it with `psql`. From this phase on
that database holds the password hashes and every permission grant of the **whole fleet**,
so the exposure was fleet-wide and reachable from a single optician's credential.

After the fix the ACL reads `=T/optique_app` for `PUBLIC` — `T` for TEMP, no `c`:

```
 optique_control | optique_app | ... | =T/optique_app
                                     | optique_app=CTc/optique_app
```

This is the same shape as the three holes already found in this project (client databases,
the `postgres` maintenance database, the `SECURITY DEFINER` verifier function). All four
were invisible to review because the guarantee each broke is written in Python, one layer
above.

## Three docstrings that were lying

- `config/urls.py` claimed tenant resolution yields nothing for the admin path by design.
  It never did: resolution is a function of the principal's `client_id`, not of the path,
  and this phase creates users carrying one. What shuts the admin is the CHECK constraint
  and `has_permission` — never the URL.
- `plateforme/tenancy/middleware.py` (module docstring and `resolve_client`) announced
  that Phase 3 would issue bearer tokens carrying a `client_id` claim. Phase 3
  authenticates by session, precisely because DRF authenticates inside `APIView.initial()`
  — after every middleware — so a token would leave `request.user` anonymous at binding
  time and every business query would raise `NoTenantBound`. **No behavioural line of that
  file changed.**
- `tests/test_tenancy_context.py` carried the same stale claim on its `_Principal` stand-in.

## Two things an operator must know

1. **The Phase 2 operator superuser was destroyed** with the database and recreated as
   `operateur@optique.local` (development password `admin_dev_only`, `client=None`).
   Verified live: its hash starts with `argon2`, so the hasher order is in effect and not
   merely configured.
2. **`docker/postgres/init/00-databases.sql` must be re-run by hand on any development
   cluster that was already initialised.** Docker executes
   `/docker-entrypoint-initdb.d` only on an empty volume, so the `REVOKE` would otherwise
   never reach an existing machine. It was applied to this one; the command is now written
   at the top of the file itself:

   ```
   docker compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d postgres \
       -f /docker-entrypoint-initdb.d/00-databases.sql
   ```

   The script is idempotent, so re-running it is always safe. Note the slow test targets
   the *development* database deliberately: `test_optique_control` is built by the test
   runner from a template that has never seen this file.

## Deviations from Plan

### 1. [Rule 3 — Blocking] The AdminSite class cannot live in `admin.py`

- **Found during:** Task 3, while wiring `default_site`.
- **Issue:** `django.contrib.admin.site` is a `LazyObject` whose `_setup()` imports the
  class named by `default_site`. Had that class lived in `plateforme/comptes/admin.py`
  beside an `@admin.register(...)` call, the decorator's access to `admin.site` would
  re-enter `_setup()` while `_wrapped` was still empty: a second site instance would
  receive the registration, and the outer `_setup()` would then overwrite it with a third.
  `Utilisateur` would vanish from the admin **with no error**.
- **Fix:** the site class (and the config that installs it) live in
  `plateforme/comptes/sites.py`, which registers nothing. `admin.py` holds only the
  registration and is picked up by `autodiscover()` normally.
- **Cost:** one file beyond the plan's `<files>` list. The plan's intent — "define an
  AdminSite in comptes and install it as `admin.site`" — is met.
- **Commit:** `1f7e74d`

### 2. [Rule 3 — Blocking] `AdminOperateurConfig` cannot live in `apps.py` either

- **Found during:** Task 3. `manage.py check` failed with
  *"Application labels aren't unique, duplicates: admin"*.
- **Issue:** Django builds an app's configuration by running
  `inspect.getmembers(module, inspect.isclass)` over `<app>/apps.py` and keeping every
  `AppConfig` subclass it finds — it does not distinguish a class *defined* there from one
  merely *imported*. The `from django.contrib.admin.apps import AdminConfig` needed to
  subclass it therefore registered a second config with label `admin`.
- **Fix:** `AdminOperateurConfig` moved to `sites.py`; `apps.py` carries a comment stating
  the rule so the import is not reintroduced.
- **Commit:** `1f7e74d`

### 3. [Rule 1 — Bug] The slow test read the wrong database name

- **Found during:** Task 3 RED. The test asserted on
  `settings.DATABASES["default"]["NAME"]`, which pytest-django rewrites to
  `test_optique_control` before the first test runs — so it failed for the wrong reason.
- **Fix:** the name is read from `CONTROL_PLANE_DB_NAME` in the environment, the same
  source `config/settings/base.py` reads, with a guard refusing any name starting with
  `test_`. The test then went RED for the right reason (`CONNECT` genuinely granted) and
  GREEN after the `REVOKE`.
- **Commit:** `1f7e74d`

### 4. [Rule 1 — Bug] A stale JWT claim outside the plan's file list

- `tests/test_tenancy_context.py:132` carried the same false Phase-3 docstring the plan
  sends us to fix in `middleware.py`. The plan's success criterion is repo-wide ("no
  docstring in the repository still announces JWTs for phase 3"), so it was corrected too.
- **Commit:** `1f7e74d`

### 5. The format fixture had to be written with a heredoc-free path

The `Write` tool normalises ` ` escape sequences into literal U+00A0 bytes, which is
exactly what the plan forbids — the escapes are deliberate, because a literal
non-breaking space is invisible in review and an editor may silently turn it into an
ordinary one. The file was written and then converted back with
`perl -CSD -i -pe 's/\x{00a0}/\\u00a0/g'`. Verified: 8 escape sequences present, 0 raw
U+00A0 bytes, 0 U+202F, 0 occurrences of `fr-MA`.

## Acceptance criteria, as run

### Task 1

| Criterion | Result |
|---|---|
| `uv run python manage.py check` | exit 0, "no issues (0 silenced)" |
| `grep -c 'drf-spectacular==0.30.0' pyproject.toml` | 1 |
| `grep -c 'argon2-cffi==25.1.0' pyproject.toml` | 1 |
| `grep -ci simplejwt pyproject.toml` | 0 |
| `grep -cE '"comptes"\|"projection"\|"drf_spectacular"' plateforme/tenancy/router.py` | 3 |
| `test -f tests/fixtures/formats_mad.json` | exit 0 |
| JSON loads, `separateur_milliers` is U+00A0, `["1800.00", "1 800,00 MAD"]` present | exit 0 |
| `grep -c 'fr-MA' tests/fixtures/formats_mad.json` | 0 |

`drf_spectacular` imports and checks clean on Django 6.1.1 — research assumption A6
closed, its classifiers stopping at 6.0 notwithstanding.

### Task 2

| Criterion | Result |
|---|---|
| `grep -c 'AUTH_USER_MODEL = "comptes.Utilisateur"' config/settings/base.py` | 1 |
| `grep -c Argon2PasswordHasher config/settings/base.py` | 1 |
| `grep -c PermissionsMixin plateforme/comptes/models.py` | 0 |
| `grep -c un_utilisateur_client_n_est_jamais_operateur plateforme/comptes/models.py` | 1 |
| `test -f plateforme/comptes/migrations/0001_initial.py` | exit 0 |
| `uv run pytest tests/test_comptes_socle.py -x -q -k perm02` | 4 passed |
| `uv run python manage.py makemigrations --check --dry-run` | exit 0, "No changes detected" |

### Task 3

| Criterion | Result |
|---|---|
| `grep -c 'REVOKE CONNECT ON DATABASE optique_control FROM PUBLIC' docker/postgres/init/00-databases.sql` | 1 |
| `grep -cE 'GRANT +CONNECT ON DATABASE optique_control TO optique_app' …` | 1 |
| `grep -ci jwt plateforme/tenancy/middleware.py` | 0 |
| `grep -ci 'deliberately returns' config/urls.py` | 0 |
| `pytest -q -k "ladmin or operateur"` | 3 passed |
| `pytest -q -k plan_de_controle -m slow` | 1 passed |
| `psql -c "\l optique_control"` shows no `c` for PUBLIC | `=T/optique_app` — TEMP only |

## RED → GREEN

| Test | RED reason | GREEN |
|---|---|---|
| 4 × PERM-02 socle | `ModuleNotFoundError: plateforme.comptes.models` | after the model, migration and database recreation |
| `..._aucun_modele_metier…` | `Utilisateur` not registered (positive control) | after `admin.py` + `default_site` |
| `..._seul_un_operateur_sans_client…` | a `client_id`-carrying superuser reached the admin | after `has_permission` |
| `..._un_role_client_ne_peut_pas_ouvrir…` | `test_client_u028990 détient CONNECT sur optique_control` | after the `REVOKE`, applied to the live cluster |

## Suite

**114 passed** (`-m "not pending"`, Compose up), against **107** at the start of the plan.
Seven added, none removed, none skipped. The quick loop
(`-m "not slow and not pending"`) is 84 passed in 2.6 s.

## Known Stubs

`plateforme/projection/` is an intentional labelled shell — no models, no registry yet.
The plan creates it in this wave only so that `INSTALLED_APPS` and `CONTROL_PLANE_APPS`
move together (pitfall P1) and no later plan has to touch the router to add itself. The
registry, its four consumers and the parametrized conformance test are plan 03-05's
deliverable. Nothing renders through it yet, so nothing is stubbed *out* of a user-facing
path.

## Notes for later plans

- `tests/fixtures/formats_mad.json` is written but **not yet read by anything**. 03-10
  (server formatter) and 03-11 (vitest) are its consumers. Its `999.995 → 1 000,00 MAD`
  case pins `ROUND_HALF_UP` on a `Decimal`, and the date case pins the UTC → UTC+1
  conversion. `TIME_ZONE = "UTC"` stays as it is — it is load-bearing for PgBouncer and
  must not become `Africa/Casablanca` (`03-UI-SPEC.md` 8.2).
- `03-UI-SPEC.md` 8.1 flags the U+00A0 group separator as research assumption **A1**,
  needing a Moroccan optician or the comptable. It is cheap to change now and expensive
  once Phase 9's PDFs exist. Ask alongside the four Phase 6 facturation questions.
- The permission grant model (03-04) must follow CLAUDE.md #13 —
  `(utilisateur, magasin, permission)` — not `03-RESEARCH.md` §4's shape. The research's
  own correction banner says so.
- `auth_group` and `auth_permission` tables still exist on `default`: `django.contrib.auth`
  remains installed for the machinery `admin` needs. `Utilisateur` has no relation to
  either, which is what the mixin-absence test pins.

## Self-Check: PASSED

All nine created files verified present on disk. All three commits verified in
`git log`: `326e25a`, `b7667da`, `1f7e74d`. Working tree clean before the docs commit.
