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

# TODO(02-03): ["plateforme.tenancy.router.TenantRouter"]
# Left empty on purpose until the router exists. Setting it now would make
# makemigrations fan out across every registered alias.
DATABASE_ROUTERS: list[str] = []

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

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
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_celery_beat",
    # Control plane — lives on `default` only, and `allow_migrate` pins it there.
    "plateforme.control_plane",
    # Business apps — their tables exist only in client databases, never in `default`.
    "domaine.magasins",
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
    # TODO(02-03): "plateforme.tenancy.middleware.TenantMiddleware" goes HERE — strictly
    # after AuthenticationMiddleware, because resolving the client depends on request.user.
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

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        # Set now, not later. Ordonnances are health data under law 09-08 and are in
        # scope for every request; retrofitting a scrubber after a leak is not a fix.
        send_default_pii=False,
        traces_sample_rate=0.0,
        # TODO(02-03): before_send scrubber + per-event client/magasin tags, set from the
        # tenancy context in the middleware.
    )
