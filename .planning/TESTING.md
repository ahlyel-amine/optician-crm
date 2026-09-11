# Testing Strategy

How this project tests, and what it deliberately does not test. Written before any code exists, so
Phase 2 starts test-first rather than retrofitting a suite later.

Stack assumption: **pytest + pytest-django**, `factory_boy` for data, `freezegun` for time.

---

## 1. What TDD means here

Test-first, but aimed at **invariants rather than coverage**. This product's failure modes are not
"the button doesn't work" — they are a facture number with a gap in it, one optician seeing another's
data, and a caisse balance that quietly disagrees with the drawer. Those are the things to write
tests for before the code.

Three rules:

1. **Every non-negotiable in `CLAUDE.md` has a named test.** If a decision matters enough to be
   non-negotiable, it matters enough that reversing it should turn the suite red.
2. **Do not test Django.** No tests that a `CharField` saves a string, that a migration applies, or
   that DRF serialises. Test *our* rules.
3. **A test name cites its requirement.** `test_fact03_numbers_have_no_gaps_under_concurrency`.
   That gives requirement → test traceability for free, and the verifier can check a phase's
   requirements actually have tests rather than trusting a summary.

**A requirement is done when its test exists, passes, and names it.**

---

## 2. Test levels

| Level | Database | What belongs here |
|---|---|---|
| **Unit** | none | Money arithmetic, TVA per rate, remise, totals, ordonnance validation (axe 0–180, cylinder transposition, mono vs bino EP), the AMO 23-month relance date maths, facture number formatting |
| **Integration** | one tenant | Ledgers and derived balances, document lifecycle, provisioning, querysets, serializer projections |
| **Tenancy** | two tenants | Routing, fail-closed, context isolation, migration fan-out — see §3 |
| **Concurrency** | real transactions | Facture numbering, stock decrement — see §4 |
| **API contract** | one tenant | Permission-filtered output, and that the OpenAPI schema the TypeScript client is generated from does not change silently |
| **E2E** | — | Not before Phase 11. A browser suite now would cost more than it catches. |

Most tests should be unit or integration. The tenancy and concurrency tests are few, slow, and the
most valuable in the repository.

---

## 3. The multi-tenant fixture — the part that needs designing

Standard Django testing assumes every database alias is in `DATABASES` at startup. Ours are
registered **at runtime**, so `pytest-django`'s normal setup knows nothing about them. This has to be
solved deliberately, once, in `conftest.py`.

**Provide two tenants, not one.** A single test tenant cannot prove isolation — with one tenant, a
router bug that always returns the same alias passes every test. Every isolation test needs a second
client whose data must *not* appear.

```
@pytest.fixture(scope="session")
def tenant_a(django_db_setup, django_db_blocker): ...   # provisioned, migrated, seeded
@pytest.fixture(scope="session")
def tenant_b(django_db_setup, django_db_blocker): ...   # the control
```

Session-scoped because provisioning a database per test is unaffordably slow; wrap per-test writes in
transactions and roll back. Where a test genuinely needs a fresh database (provisioning failure paths,
migration fan-out), let it pay the cost explicitly and mark it `slow`.

**Teardown must actually drop the test databases.** A crashed run that leaves `test_client_*`
databases behind will make the next run's provisioning test fail for the wrong reason.

---

## 4. Traps specific to this project

**`TestCase` makes the concurrency test lie.** Django's `TestCase` wraps each test in a transaction,
so `select_for_update()` never contends and a numbering test passes against broken code. The gapless
tests must use `TransactionTestCase` / `pytest.mark.django_db(transaction=True)` with real threads or
processes. A green suite that proves nothing is worse than no suite.

**The context-leak test must simulate thread reuse.** Worker threads are recycled between requests,
and a missed `current_alias.reset()` leaks the previous client. Testing two requests sequentially in
one thread is the *only* way this bug shows up — a fresh thread per test hides it permanently.

**Assert on `Decimal`, never float.** `assert total == 1800.0` passes while the code is wrong.
Compare `Decimal("1800.00")` and assert the exponent where rounding matters.

**Freeze time for anything with a date rule.** The AMO relance fires at 23 months, chèque échéances
fall due, and the facture exercice rolls at year end. Un-frozen, these pass today and fail in January.

**Test against the real pooling topology.** PgBouncer in transaction mode can break prepared
statements in ways that only appear under a pool. Compose must match production, or the tenancy suite
is testing a configuration you will never ship.

---

## 5. The invariant catalogue

The TDD backlog. Each of these is written *before* its implementation.

### Tenancy (Phase 2)
- `test_tenant04_router_raises_when_no_client_bound` — never returns `None`, never falls back to `default`
- `test_tenant04_business_models_never_migrate_to_default`
- `test_tenant04_context_does_not_leak_between_requests_on_one_thread`
- `test_tenant04_tenant_a_cannot_read_tenant_b_data`
- `test_tenant05_failed_provisioning_leaves_no_active_client`
- `test_tenant03_migration_fanout_reports_which_clients_are_behind`
- `test_tenant09_single_client_restore_produces_identical_data`

### Permissions (Phase 3)
- `test_perm05_gerant_without_grant_sees_no_prix_achat` — asserted against API, export **and** print in one table-driven test, because PERM-06 is the claim that all three share a projection

### Facturation (Phase 6)
- `test_fact03_numbers_have_no_gaps_under_concurrency` — N threads, N factures, contiguous
- `test_fact03_rollback_does_not_consume_a_number` — the reason a `SEQUENCE` is forbidden
- `test_fact12_same_idempotency_key_yields_one_facture`
- `test_fact04_tva_broken_out_per_rate_not_a_global_constant`
- `test_fact01_monture_and_verres_are_separate_priced_lines`
- `test_fact08_facture_is_never_deleted_only_corrected_by_avoir`
- `test_fact14_remise_recalculates_tva_and_totals`

### Caisse (Phase 7)
- `test_caisse06_postdated_cheque_does_not_move_the_balance_until_encaisse`
- `test_caisse05_correction_is_a_compensating_entry_not_an_edit`
- `test_caisse03_daily_totals_reconcile_with_the_ledger`

### Stock (Phase 5/6)
- `test_stock02_quantity_is_derived_from_movements_not_stored`
- `test_stock04_sale_warns_before_taking_stock_negative`

### Clients (Phase 4)
- `test_client07_axe_outside_0_180_is_rejected`
- `test_client06_new_ordonnance_versions_rather_than_overwrites`
- `test_client10_search_finds_mohamed_mohammed_and_mhamed`

---

## 6. Coverage policy

No percentage target. A percentage rewards testing getters and punishes nothing that matters here.

The bar is: **every non-negotiable has a named test, and every requirement involving money, a date
rule, a legal number or a permission has a test that cites it.** A phase is not done when its code
works; it is done when reversing its decisions turns the suite red.

---

## 7. Phase 1 has no tests, and that is correct

Phase 1 is CNDP authorization, the hosting-jurisdiction decision and the merchant contract. Its
evidence is documentary: a filing reference recorded, a decision written down with its reasoning, a
contract opened. The verifier should look for those artefacts, not a test run.

Test code starts in Phase 2.
