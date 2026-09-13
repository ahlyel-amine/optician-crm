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
