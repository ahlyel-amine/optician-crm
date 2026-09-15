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
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"


# --------------------------------------------------------------------------------------
# Celery
# --------------------------------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://127.0.0.1:6379/1")
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"


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
