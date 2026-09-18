"""Test settings.

Declares `tenant_a` and `tenant_b` as ordinary static aliases. Production registers
tenant connections at runtime, but the test suite does not have to imitate that, and
making it imitate that costs a great deal for no benefit.

Two static entries in DATABASES buy creation, migration, teardown, per-test transaction
rollback and pytest-xdist worker suffixing for free.

**Nothing here overrides pytest-django's database-setup fixture, and nothing ever
should.** It looks like the obvious hook and it silently breaks pytest-xdist:
`django_db_modify_db_settings_xdist_suffix` runs *before* `django_db_modify_db_settings`,
so aliases added inside such an override never receive the `_gw0` worker suffix, and
parallel workers then collide on the same test databases. See `.planning/TESTING.md`
section 3 and 02-RESEARCH.md Pitfall 8. The grep in this plan's acceptance criteria
enforces the absence of that fixture name anywhere under `config/` and `tests/`.

Two tenants, never one: with a single tenant, a router bug that always returns the same
alias passes every isolation test.
"""

import copy
import tempfile

from .base import *  # noqa: F403
from .base import DATABASES, PG_ADMIN_HOST, PG_ADMIN_PORT


def _tenant(name: str) -> dict:
    # copy.deepcopy, never {**DATABASES["default"]}: OPTIONS and TEST are nested dicts
    # that a shallow copy would share by reference across all three aliases, so mutating
    # one alias's OPTIONS would silently mutate the others'.
    cfg = copy.deepcopy(DATABASES["default"])
    cfg.update(
        NAME=name,
        CONN_MAX_AGE=0,
        DISABLE_SERVER_SIDE_CURSORS=True,
    )
    cfg["TEST"] = {**cfg.get("TEST", {}), "NAME": f"test_{name}"}
    return cfg


DATABASES["tenant_a"] = _tenant("optique_test_a")
DATABASES["tenant_b"] = _tenant("optique_test_b")

# Tests create and drop databases, which cannot happen through transaction-mode pooling,
# so the test aliases talk directly to PostgreSQL.
for _alias in ("default", "tenant_a", "tenant_b"):
    DATABASES[_alias]["HOST"] = PG_ADMIN_HOST
    DATABASES[_alias]["PORT"] = str(PG_ADMIN_PORT)

# Ou les photos d'ordonnance de la suite atterrissent : un repertoire temporaire de
# session, **jamais** l'arbre du depot. Une photo d'ordonnance commise serait une fuite
# de donnee de sante dans l'historique git, et l'historique git n'est pas revocable.
#
# `mkdtemp` et non un chemin fixe sous /tmp : chaque worker xdist importe ces reglages,
# donc chacun obtient sa propre racine et deux workers ne peuvent pas se lire.
ORDONNANCE_MEDIA_ROOT = tempfile.mkdtemp(prefix="optique-test-media-")

# The context guard raises instead of merely logging. A leak must fail the test, loudly.
TENANCY_STRICT = True

# Databases the provisioning tests create are named `test_client_c000001`, not
# `optique_c000001`. Two reasons, both safety:
#
# 1. A test control plane starts its primary keys at 1, exactly as a development one does.
#    With a shared prefix, `provision_client` in a test would derive `optique_c000001`,
#    *adopt* the developer's real first client database (the existence guard makes that
#    silent), and then drop it in teardown. Data loss with no error.
# 2. `test_client_%` is already one of conftest.py's STALE_TEST_DB_PATTERNS, so a run
#    killed with SIGKILL is cleaned up by the next session rather than leaving behind
#    something that looks like a production client database.
TENANT_DB_NAME_PREFIX = "test_client_c"
TENANT_DB_USER_PREFIX = "test_client_u"

# The rate-limit counter lives in the cache, so the cache is pinned here rather than
# inherited. Two reasons, and the second is the one that bites:
#
# 1. a suite that shared a Redis with a developer's running application would count their
#    login attempts against its own limit, and vice versa;
# 2. `base.py` declares no CACHES today, so the suite falls back to Django's in-process
#    LocMemCache by accident. The day someone adds a Redis there for a legitimate reason,
#    the throttling tests would start leaking counters between runs and between xdist
#    workers — and they would fail *intermittently*, which is the worst way to learn it.
#
# `conftest.py`'s autouse `cache_vide` fixture clears this between tests; a per-test
# LOCATION would not, because DRF's throttle holds `caches["default"]` at import.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "suite-de-tests",
    }
}
