"""Base settings, shared by local, test and production.

Two things here are load-bearing rather than conventional, and both are asserted by
`tests/test_connection_budget.py`:

1. Web and Celery traffic goes through **PgBouncer**. DDL, migrations and dumps go
   **direct to PostgreSQL** via the PG_ADMIN_* settings. Two connection paths, stated
   explicitly, because CREATE DATABASE cannot run inside a transaction block and
   transaction-mode pooling is the wrong place for schema work.
2. The connection budget (TENANT-08) must scale with concurrency, not with client count.
"""

from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-development-key-override-in-env")
DEBUG = False
ALLOWED_HOSTS: list[str] = []


# --------------------------------------------------------------------------------------
# Databases
# --------------------------------------------------------------------------------------
# The application talks to PgBouncer in transaction pooling mode. Nothing session-scoped
# may be set at connect time, because a server connection carrying it is handed straight
# to the next client (threat T-02-02).
#
# The per-request-transaction setting forbidden by CLAUDE.md non-negotiable #12 is
# deliberately absent from this file, and from every settings module. Writing it even as
# False invites a later "why is this False?" edit; BaseHandler.make_view_atomic() iterates
# *every* alias in connections.settings, so enabling it costs one transaction per
# registered client per request.

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("CONTROL_PLANE_DB_NAME", default="optique_control"),
        "USER": env("CONTROL_PLANE_DB_USER", default="optique_app"),
        "PASSWORD": env("CONTROL_PLANE_DB_PASSWORD", default=""),
        "HOST": env("PGBOUNCER_HOST", default="127.0.0.1"),
        "PORT": env("PGBOUNCER_PORT", default="6432"),
        # PgBouncer owns pooling. A non-zero value makes every worker thread hold a
        # client connection per alias it has ever touched (TENANT-08).
        "CONN_MAX_AGE": 0,
        # Server-side cursors are local to a connection and survive the end of a
        # transaction under autocommit — exactly what transaction pooling recycles.
        "DISABLE_SERVER_SIDE_CURSORS": True,
        # Intentionally empty. Do not add a connection-pool key: DatabaseWrapper's
        # _connection_pools is a class-level dict keyed by alias, i.e. one psycopg_pool
        # per tenant per process — the failure mode already rejected in CLAUDE.md.
        # Do not add prepare_threshold either: Django's psycopg3 backend already sets it
        # to None to keep connection poolers working.
        "OPTIONS": {},
    }
}

# Fail-closed routing (TENANT-04). From here on, `makemigrations` iterates every alias
# registered in the process and opens a connection to each — which is exactly why
# registration is lazy and request-driven, and why nothing registers an alias in an
# AppConfig.ready(). See plateforme/tenancy/registry.py.
DATABASE_ROUTERS = ["plateforme.tenancy.router.TenantRouter"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# The pooled traffic path, named symbolically so it survives the test settings pointing
# `DATABASES` straight at PostgreSQL. `DATABASES["default"]["HOST"]` is *not* a reliable
# way to find PgBouncer: config/settings/test.py overrides it to PG_ADMIN_HOST so that the
# suite can run DDL. A test that wants to prove the *pooled* path works therefore has to
# name the pooler explicitly — see tests/test_pgbouncer_auth.py.
PGBOUNCER_HOST = env("PGBOUNCER_HOST", default="127.0.0.1")
PGBOUNCER_PORT = env.int("PGBOUNCER_PORT", default=6432)

# Direct-to-PostgreSQL path, bypassing PgBouncer: provisioning, migrate_all, pg_dump,
# pg_restore, reap_orphan_databases. Deliberately a different port from PGBOUNCER_PORT.
PG_ADMIN_HOST = env("PG_ADMIN_HOST", default="127.0.0.1")
PG_ADMIN_PORT = env.int("PG_ADMIN_PORT", default=5432)
PG_ADMIN_USER = env("PG_ADMIN_USER", default="postgres")
PG_ADMIN_PASSWORD = env("PG_ADMIN_PASSWORD", default="")

# Tenant database creation. PostgreSQL 18's ICU provider carries its own locale data, so
# this works on the stock postgres image, which generates only en_US.utf8. A non-default
# locale also requires TEMPLATE template0.
TENANT_DB_LOCALE_PROVIDER = env("TENANT_DB_LOCALE_PROVIDER", default="icu")
TENANT_DB_ICU_LOCALE = env("TENANT_DB_ICU_LOCALE", default="fr-FR")

# Which implementation creates and drops client databases. `02-RESEARCH.md` Open Question
# 2 — does the managed provider's application role have CREATEDB, or must databases be
# created through the provider's API? — is a Phase 1 procurement fact and is still open.
# This setting is the seam: an API-based provisioner is a second class named here, not a
# change to the provisioning state machine.
DATABASE_PROVISIONER = env(
    "DATABASE_PROVISIONER", default="plateforme.tenancy.provisioner.SqlProvisioner"
)

# A client's database and role names are `<prefix><pk:06d>` — derived from the primary
# key, never from operator input (threat T-02-23). The prefixes are settings for exactly
# one reason, and it is a safety reason rather than a flexibility one: the test suite runs
# against the same PostgreSQL instance as development, and a test control plane starts its
# primary keys at 1 too. Sharing `optique_c` would make a test run adopt — and then drop —
# a developer's real `optique_c000001`. `config/settings/test.py` overrides both to
# `test_client_*`, which is also the prefix conftest.py's session-start reaper collects.
TENANT_DB_NAME_PREFIX = env("TENANT_DB_NAME_PREFIX", default="optique_c")
TENANT_DB_USER_PREFIX = env("TENANT_DB_USER_PREFIX", default="optique_u")


# --------------------------------------------------------------------------------------
# Backup and restore (TENANT-09)
# --------------------------------------------------------------------------------------
# The PostgreSQL client binaries. A mismatched pg_dump refuses to dump a newer server, so
# the major version must match the server's — the app image ships postgresql-client-18 and
# `docker compose exec` reports 18.6 on both sides. Overridable because a developer's
# machine may keep them off PATH (Homebrew's libpq is keg-only).
PG_DUMP_BIN = env("PG_DUMP_BIN", default="pg_dump")
PG_RESTORE_BIN = env("PG_RESTORE_BIN", default="pg_restore")

# `pg_dump --compress`. zstd:9 is the project default and is **verified supported** by the
# Debian postgresql-client-18 build the app image ships:
#   pg_dump --format=custom --compress=zstd:9   -> exit 0, pg_restore --list parses it
# It is a setting because compression methods are compiled in, not universal: Homebrew's
# keg-only libpq is built without zstd and answers
#   "invalid compression specification: this build does not support compression with ZSTD"
# A developer on such a host sets gzip:9. The value must be one a *restoring* build also
# supports, so it is deployment-wide rather than per-invocation.
BACKUP_COMPRESSION = env("BACKUP_COMPRESSION", default="zstd:9")

# Where dump artifacts go. The same reasoning as DATABASE_PROVISIONER: the object-storage
# provider is a Phase 1 procurement decision, and an interface now makes an S3-compatible
# implementation a small change later.
#
# Production storage must be **EU-resident and encrypted at rest** — a dump of a client
# database is a complete copy of that optician's ordonnances, which are health data under
# law 09-08 (threat T-02-45). That is gated on the Phase 1 LEGAL-02 hosting-jurisdiction
# decision, which is why the default here is deliberately a local path rather than a
# plausible-looking bucket someone might ship.
BACKUP_STORAGE = env(
    "BACKUP_STORAGE", default="plateforme.control_plane.storage.LocalFilesystemStorage"
)
BACKUP_LOCAL_ROOT = env("BACKUP_LOCAL_ROOT", default=str(BASE_DIR / "backups"))

# `02-RESEARCH.md` assumption **A5**, and it is a legal question rather than a technical
# one: art. 211 CGI's ten years is a **records** obligation, not a backup-rotation
# obligation. Conflating the two makes storage cost explode and over-collects personal
# data. This is the defensible default the research proposes; the Phase 1 lawyer confirms
# or replaces it. **Pruning is deliberately not implemented until they do** — a rotation
# task written against a guessed policy is worse than none, because it deletes.
BACKUP_RETENTION = {"daily": 30, "monthly": 12, "annual": 10}

# Fernet key encrypting each Client row's database password. Consumed by plan 02-02.
TENANCY_FERNET_KEY = env("TENANCY_FERNET_KEY", default="")

# Raise instead of merely logging when the tenant context guard trips. Overridden to True
# in the test settings; plan 02-03 consumes it.
TENANCY_STRICT = env.bool("TENANCY_STRICT", default=False)


# --------------------------------------------------------------------------------------
# Time
# --------------------------------------------------------------------------------------
USE_TZ = True
# Must match the PostgreSQL server's `timezone` setting (Compose sets `-c timezone=UTC`).
# _configure_timezone issues `SET TIMEZONE` only when the server's reported TimeZone
# differs from this value. Under transaction pooling that SET lands on a server
# connection which then returns to the pool still carrying it (threat T-02-02). Matching
# the two means Django issues zero session SQL at connect.
TIME_ZONE = "UTC"
USE_I18N = True
LANGUAGE_CODE = "fr-fr"
# Sans activation explicite, `get_language()` rend `LANGUAGE_CODE` sur chaque thread, donc
# `gettext` resout le francais partout et les messages de validation de DRF sortent en
# francais : la bibliotheque livre son catalogue `fr`. C'est tout ce qu'il faut (APP-01),
# et trois choses sont ABSENTES d'ici expres. Chacune a un test nomme dans
# `tests/test_locale.py`, qui redeviendrait rouge si on les ajoutait.
#
# 1. **Aucun middleware de negociation de langue.** Il ferait dependre la langue de
#    l'en-tete `Accept-Language`, c'est-a-dire du poste de l'utilisateur — dans un produit
#    dont tout l'argument de la phase 2 est que rien de significatif ne vient du client
#    (menace T-03-71) — et ajouterait `Vary: Accept-Language` a chaque reponse. Le produit
#    est monolingue et le restera : BRAND-04 est du *contenu* arabe dans des documents
#    imprimes, pas une *interface* arabe.
#
# 2. **Aucun reglage de localisation des nombres.** Celui auquel on pense a ete RETIRE de
#    Django ; l'ecrire aujourd'hui, dans un sens ou dans l'autre, ne fait litteralement
#    rien. Le risque n'est pas qu'il casse quelque chose, c'est qu'une revue le lise et en
#    conclue que le formatage des montants est gere ici. Il ne l'est pas : il est
#    entierement dans `plateforme/projection/formats.py`, epingle a la main, parce que les
#    trois bases de locale plausibles rendent trois separateurs de milliers differents
#    (CLAUDE.md #14). Et `TIME_ZONE` reste `UTC` : la conversion vers Africa/Casablanca se
#    fait dans ce meme formateur, jamais ici.
#
# 3. **La regle d'API que rien d'automatique ne peut verifier :** chaque total que
#    l'interface affiche est un total fourni par le serveur — `total_ht`, `total_tva`,
#    `total_ttc`, `reste_a_payer`, `solde_caisse`. La SPA ne doit jamais additionner deux
#    montants, et si elle n'en a jamais besoin, elle ne le peut jamais. Le bug a attraper
#    en revue n'est donc pas une addition cote client : c'est un serialiseur qui **omet**
#    un total dont l'interface a besoin.


# --------------------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------------------
INSTALLED_APPS = [
    # `django.contrib.admin` itself, through a config that swaps in the operator
    # AdminSite. The admin exposes db_name, db_host and the fleet's whole migration and
    # backup history, so reaching it has to require being a platform operator — not
    # merely being a superuser (threats T-03-01, T-03-02). Replacing the app entry rather
    # than mounting a second site is what keeps the existing @admin.register decorators
    # in control_plane/admin.py landing on the guarded site.
    "plateforme.comptes.sites.AdminOperateurConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    # OpenAPI 3 schema, from which the TypeScript client is generated (PERM-06, APP-01).
    # Owns no models, but `checks.py` exempts only `django.*`, so it is classified in
    # CONTROL_PLANE_APPS like every other third-party app here.
    "drf_spectacular",
    "django_celery_beat",
    # Tenancy infrastructure. Owns no models; its ready() registers the tenancy.E001
    # system check and touches no database.
    "plateforme.tenancy",
    # Control plane — lives on `default` only, and `allow_migrate` pins it there.
    "plateforme.control_plane",
    # Identity for the whole fleet: AUTH_USER_MODEL lives here (CLAUDE.md #11). Control
    # plane, because Django needs auth/contenttypes/admin co-located in one database and
    # because a login exists before any client database does.
    "plateforme.comptes",
    # The single projection layer (PERM-06). No models — a registry and its consumers.
    "plateforme.projection",
    # Business apps — their tables exist only in client databases, never in `default`.
    # Every one of these must also be in BUSINESS_APPS in plateforme/tenancy/router.py,
    # in the same commit. An unclassified app makes `manage.py check` fail with
    # tenancy.E001 rather than silently landing its tables on `default` (Pitfall 12).
    "domaine.magasins",
    "domaine.stock",
    "domaine.caisse",
    # Plan 02-03 adds a system check that fails startup if an installed app is
    # classified as neither control-plane nor business, because an unclassified app
    # defaults to the control-plane database — a cross-client leak.
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Strictly AFTER AuthenticationMiddleware: the client is resolved from the
    # authenticated principal, never from anything the caller can set (threat T-02-13).
    # And before any view, so that a business query outside this middleware's scope
    # raises NoTenantBound rather than reading the control-plane database.
    "plateforme.tenancy.middleware.TenantMiddleware",
    # Strictement APRES TenantMiddleware : resoudre a quels magasins un octroi se refere
    # demande une requete dans la base DU CLIENT (Magasin.objects.filter(actif=True, ...)),
    # donc l'alias doit deja etre lie. Place plus haut, ce middleware ne se plaindrait de
    # rien a l'installation — l'objet est paresseux — et echouerait a la premiere vue qui
    # touche request.acces, en production.
    "plateforme.comptes.middleware.AccesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Note on what is deliberately ABSENT from TEMPLATES["OPTIONS"]: `string_if_invalid`.
# A missing template key renders "" by default, so a field the projection removed and a
# field somebody misspelled look identical — which is threat T-03-35. The fix is NOT to
# set this option globally: Django's own docs warn that any non-empty value breaks
# `{% if %}` on optional variables. Document templates iterate a declared, already
# projected column list instead, and two tests hold that (see
# plateforme/projection/documents.py).


# --------------------------------------------------------------------------------------
# API — DRF and the OpenAPI schema (PERM-06, consumer 4)
# --------------------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Sessions, not JWT (PERM-01). `TenantMiddleware` reads `request.user` at middleware
    # time; DRF authenticates inside `APIView.initial()`, *after* every middleware — so
    # under a token nothing binds and the first business query of every request raises
    # `NoTenantBound`. Verified against the installed DRF 3.18.1.
    #
    # This is a **list**, and that is the whole answer to "but Phase 11 is Expo, where
    # cookies are painful": adding a token class there is additive and touches no view,
    # no serializer, no permission and no projection. What must stay true today is that
    # the tenant binding is not welded to the middleware — and it is not:
    # `resolve_client(request)` is a standalone function whose contract is
    # "server-verified identity in, `Client` out".
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Closed by default. A Phase 6 endpoint that forgets its permission class is refused
    # rather than public, and "forgetting" is the failure mode a closed default deletes.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    # JSON only, on purpose (threat A-03-06). DRF's browsable HTML renderer draws its
    # forms from `get_fields()`, which IS projected — but it also renders related
    # objects' `__str__` inside `<select>` dropdowns, and a dropdown enumerates rows: a
    # gérant with one magasin would read the client names of the others. It is added in
    # `local.py` and nowhere else, and a test asserts its class name appears in exactly
    # one settings module — which is why that name is not written here.
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    # DRF's own default (`rest_framework/settings.py:119`), pinned **because** it is a
    # default: a default is not reread in review and is reversed in one line, usually to
    # silence a chart component that wanted numbers. The chart component is wrong. This
    # setting is the only thing between CLAUDE.md #7 and a binary float — a `DecimalField`
    # rendered as a JSON number becomes an IEEE-754 double in the browser, and the missing
    # centime surfaces months later in a reconciliation with no trace of its cause.
    "COERCE_DECIMAL_TO_STRING": True,
    # One login address serves the whole fleet (CLAUDE.md #11), so it is a single point at
    # which to try passwords against any account of any business (A-03-11, threat T-03-47).
    # Argon2 makes each attempt expensive, which is itself a second reason to cap the rate:
    # uncapped, the expensive attempt becomes a denial of service against our own CPU.
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"connexion": "10/min"},
    # **Zero, deliberately.** `SimpleRateThrottle.get_ident` reads `X-Forwarded-For` when
    # this is `None` (the default, verified in the installed DRF 3.18.1), so an attacker
    # who rotates that header gets a fresh counter per attempt and the throttle stops
    # throttling — while staying perfectly green in any test that does not send the header.
    # The hosting jurisdiction is an open Phase 1 decision, so the number of trusted
    # proxies is not known; zero falls back to `REMOTE_ADDR`, which behind a reverse proxy
    # makes the limit *global* rather than bypassable. Too strict is the right side to err
    # on. Revisit this the day a proxy reaches production, with that proxy in hand.
    "NUM_PROXIES": 0,
    # Two corrections, both about what a response body is allowed to say: 401 must mean
    # "not authenticated" (DRF downgrades it to 403 whenever the authentication class
    # supplies no `WWW-Authenticate` header, which `SessionAuthentication` does not), and
    # `NoTenantBound` must never reach a body. See the handler's docstring.
    "EXCEPTION_HANDLER": "plateforme.comptes.views.gestionnaire_dexceptions",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "API Optique",
    "VERSION": "1.0.0",
    # The schema endpoint does not describe itself. It is infrastructure, not API surface.
    "SERVE_INCLUDE_SCHEMA": False,
    # Pin the projection during schema generation, so the served document is identical
    # for every caller and matches the committed schema.yml.
    # `generators.py:231` assigns `view.request = GET_MOCK_REQUEST(...)`, and the stock
    # `build_mock_request` copies `request.user` from the caller
    # (`plumbing.py:1283-1299`) — which would make `/api/schema/` a per-user document and
    # let a gérant enumerate the protected fields by diffing it (threat T-03-32).
    "GET_MOCK_REQUEST": "plateforme.projection.schema.requete_mock_schema",
    # The registry also drives `required`, so the generated TypeScript is
    # `prix_achat?: string` rather than a type that lies. `openapi.py:1094-1099` computes
    # membership as `field.required or readOnly`, so a read-only money field lands in
    # `required` and the compiler then promises a key that a gérant's payload will not
    # carry (threat T-03-33).
    # Order matters: the enum hook runs first, ours last, on the finished document.
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "plateforme.projection.schema.marquer_champs_proteges_optionnels",
    ],
    # Note what is absent here, and keep it absent: the global switch that drops *every*
    # read-only field from `required`. Flipping it would make `id` optional on every
    # resource in the product — a much broader lie than the one being fixed. The hook
    # above is surgical; that switch is not. A test asserts the name appears in no
    # settings module, because a setting nobody writes down is a setting nobody flips.
}


# --------------------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------------------
# The user table lives in the control-plane database (CLAUDE.md #11): identity, business
# membership and permission grants are fleet-wide, while every client database holds only
# that optician's business data.
#
# The model carries a nullable `client` FK, which is the whole of the tenant claim —
# `TenantMiddleware.resolve_client` already reads `user.client_id`, so this phase changes
# zero lines of the Phase 2 tenancy layer.
#
# Swapping this value is only cheap before anything depends on `auth.User`, which is why
# it happens in the first plan of the phase and why it was preceded by a blocking count of
# existing clients. `django.contrib.admin`'s migrations reference AUTH_USER_MODEL, so the
# development control-plane database was recreated rather than migrated.
AUTH_USER_MODEL = "comptes.Utilisateur"

# Argon2 first. Django ships the hasher; `argon2-cffi` is the C library it needs. The
# order is the whole setting: the first entry hashes new passwords, and the rest exist so
# that an existing hash can still be verified and transparently upgraded on login. PBKDF2
# stays behind it for exactly that reason.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]


# --------------------------------------------------------------------------------------
# Sessions and cookies
# --------------------------------------------------------------------------------------
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
# `Lax`, not `Strict`: `Strict` would break returning to the app from an external link,
# and the SPA is same-origin, which makes `Lax` sufficient.
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
# `CSRF_COOKIE_HTTPONLY` is deliberately left at Django's `False`. The double-submit
# pattern requires the SPA's JavaScript to read the cookie and echo it in `X-CSRFToken`;
# making it HttpOnly would break CSRF protection rather than strengthen it.

# Thirty days, explicit, because Django's default is fourteen. **`SESSION_EXPIRE_AT_BROWSER_CLOSE`
# is literally the PERM-01 requirement** ("stays signed in across sessions"), so it is
# written and asserted rather than inherited.
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
# Deliberately False (threat T-03-53). Sliding expiry writes one `UPDATE django_session`
# per request to the **control-plane** database — a single hot table shared by every
# optician in the fleet. PERM-01 asks for "still signed in when they return", not for a
# rolling window, and a fixed thirty days delivers that with one write at login.
#
# If opticians later complain about being logged out, the upgrade is `cached_db` on the
# Redis that Celery already uses — and **not** plain `cache`: a Redis restart would log
# the entire fleet out, and Redis must not sit on the authentication path.
SESSION_SAVE_EVERY_REQUEST = False
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# Password strength is checked where a password is *chosen* — the self-service change
# endpoint and, from plan 03-09, the owner setting a gérant's initial one. Validators are
# only run by `validate_password()`; they are not invoked by `set_password`, so declaring
# them changes nothing about existing hashes or fixtures.
#
# Ten rather than Django's eight: one login address serves the whole fleet, so the
# per-account cost of a weak password is borne by a shared brute-force surface.
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {"user_attributes": ("email", "nom_complet")},
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --------------------------------------------------------------------------------------
# Celery
# --------------------------------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://127.0.0.1:6379/1")
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Beat entries. `DatabaseScheduler.setup_schedule()` calls
# `update_from_dict(self.app.conf.beat_schedule)` (verified in the installed
# django-celery-beat 2.9.0), so entries declared here are synced into the operator-visible
# `PeriodicTask` table on beat start rather than competing with it.
#
# Tasks are named by string, not imported: a settings module that imports an app module
# runs it before the app registry is ready, and the failure mode is an import error a long
# way from its cause.
CELERY_BEAT_SCHEDULE = {
    # Without this, `django_session` grows forever on the shared control-plane database
    # (threat T-03-52, A-03-12): denial of service by growth, and a forensic liability.
    # The rows themselves carry only a user primary key and a hash — no cross-client
    # content — but that is worth stating rather than assuming, because the retention
    # decision depends on it (art. 211 CGI covers *records*, not sessions).
    "purger-les-sessions-expirees": {
        "task": "control_plane.clear_expired_sessions",
        # 03:17 UTC — off the hour, so it does not pile onto every other cron in the
        # fleet, and outside Moroccan shop hours (UTC+1).
        "schedule": crontab(hour="3", minute="17"),
    },
}


# --------------------------------------------------------------------------------------
# Sentry
# --------------------------------------------------------------------------------------
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk

    from plateforme.tenancy.telemetry import before_send

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        # Set now, not later. Ordonnances are health data under law 09-08 and are in
        # scope for every request; retrofitting a scrubber after a leak is not a fix.
        send_default_pii=False,
        traces_sample_rate=0.0,
        # The fine control, on top of send_default_pii: redacts clinical and personal
        # values from request bodies, breadcrumbs and captured stack-frame locals.
        # TenantMiddleware adds the `client` tag — keep the tag, scrub the body
        # (threat T-02-17).
        before_send=before_send,
    )
