---
phase: 2
slug: tenancy-foundation-control-plane
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-09-12
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `02-RESEARCH.md` § Validation Architecture. Project-wide conventions: `.planning/TESTING.md`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-django (pin exact versions at Wave 0) |
| **Config file** | none yet — Wave 0 creates `pyproject.toml [tool.pytest.ini_options]` with `DJANGO_SETTINGS_MODULE = "config.settings.test"` |
| **Quick run command** | `uv run pytest -x -q -m "not slow"` |
| **Full suite command** | `uv run pytest --create-db` |
| **Estimated runtime** | quick ~30 s · full several minutes (real `CREATE DATABASE` and `pg_dump`) |

Marks: `slow` (real DDL / dump / restore, runs against Compose), `tenancy` (needs both tenant aliases).

---

## Sampling Rate

- **After every task commit:** `uv run pytest -x -q -m "not slow"`
- **After every plan wave:** `uv run pytest --create-db`
- **Before `/gsd-verify-work`:** full suite green **and** `manage.py migrate_all --check` exits 0
- **Max feedback latency:** 30 seconds

---

## Per-Requirement Verification Map

Task IDs are filled in by the planner; every task must cite one of these tests.

| Requirement | Named test | Type | Automated |
|---|---|---|---|
| TENANT-01 | `test_tenant01_provision_client_creates_database_at_migration_head` | integration | yes (`slow`) |
| TENANT-02 | `test_tenant02_control_plane_records_db_name_host_and_schema_version` | integration | yes |
| TENANT-03 | `test_tenant03_migration_fanout_reports_which_clients_are_behind` · `test_tenant03_one_client_failing_does_not_stop_the_others` | integration | yes (`slow`) |
| TENANT-04 | `test_tenant04_router_raises_when_no_client_bound` · `test_tenant04_router_never_returns_none` · `test_tenant04_business_models_never_migrate_to_default` · `test_tenant04_context_does_not_leak_between_requests_on_one_thread` · `test_tenant04_tenant_a_cannot_read_tenant_b_data` · `test_tenant04_celery_task_without_client_id_fails_closed` · `test_tenant04_every_installed_app_is_classified` | unit + integration | yes |
| TENANT-05 | `test_tenant05_failed_provisioning_leaves_no_active_client` · `test_tenant05_rerun_after_kill_converges_to_active` · `test_tenant05_rerun_creates_no_second_database` | integration | yes (`slow`) |
| TENANT-06 | `test_tenant06_management_command_delegates_to_provision_client` | unit | yes |
| TENANT-07 | `test_tenant07_provisioning_seeds_requested_magasins` · `test_tenant07_stock_and_caisse_are_scoped_per_magasin` | integration | yes |
| TENANT-08 | `test_tenant08_conn_max_age_is_zero_on_every_alias` · `test_tenant08_no_alias_has_atomic_requests` · `test_tenant08_server_side_cursors_are_disabled` · plus a `slow` load check asserting `pg_stat_activity` does not scale with alias count | settings + load | yes (load check `slow`) |
| TENANT-09 | `test_tenant09_single_client_restore_produces_identical_data` · `test_tenant09_backup_runs_for_every_active_client` | integration | yes (`slow`) |

**The bypass-proof backstop:** `test_tenant04_business_models_never_migrate_to_default` queries `information_schema.tables` on `default` and asserts zero business tables. It holds even if the router is circumvented, which no router-level assertion can claim.

---

## Wave 0 Requirements

Greenfield repository — nothing exists. Wave 0 creates, in order:

- [ ] `pyproject.toml` — `[tool.pytest.ini_options]`, `DJANGO_SETTINGS_MODULE`, `slow` and `tenancy` markers
- [ ] `config/settings/{base,local,test,production}.py` — **with static `tenant_a` / `tenant_b` aliases in `test.py`** (never override `django_db_setup`; it breaks xdist)
- [ ] `docker-compose.yml` — Postgres (`timezone=UTC`, `log_statement=all`), PgBouncer, Redis. **Host port must not be 8000 — it is already occupied on this machine.**
- [ ] `conftest.py` — `db_all`, `tenant_a`, `tenant_b`, and a session-start reaper for stale test databases
- [ ] `tests/test_tenancy_router.py`, `test_tenancy_context.py`, `test_provisioning.py`, `test_migrate_all.py`, `test_backup_restore.py`, `test_magasin_scoping.py`
- [ ] `tests/factories.py` — `ClientFactory`, `MagasinFactory`
- [ ] Dev dependencies: pytest, pytest-django, pytest-xdist, factory_boy, freezegun

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| The managed provider's app role can `CREATE DATABASE` | TENANT-01 | Procurement fact, not code. If the provider is API-only, provisioning changes shape. | Ask the provider directly. Mitigated in code by putting `create_database` / `drop_database` behind a two-method `DatabaseProvisioner` interface from day one. |

Everything else has automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
