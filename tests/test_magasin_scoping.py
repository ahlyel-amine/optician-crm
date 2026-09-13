"""TENANT-07 — magasins are a column inside a client's database, never a database.

The temptation is to mirror the tenant pattern: an implicit `magasin` contextvar and a
default manager that filters. The asymmetry is real and these tests pin it.

* The isolation boundary for a *client* is the connection. For a *magasin* it is a
  column.
* Cross-client reads are never legitimate. Cross-magasin reads are legitimate and
  constant — the owner's dashboard, réappro across magasins, possibly one facture série
  per company.

So there is deliberately **no implicit magasin filter and no magasin contextvar**. An
implicit filter would return a wrong number with no error, which is worse than a crash.
"""

import pytest
from django.db import models


def test_tenant07_magasin_has_no_client_foreign_key():
    """Threat T-02-11: a `client_id` column here would be a second source of tenancy truth.

    **The database is the client.** A FK from `Magasin` to `control_plane.Client` would
    contradict that, would be an invitation to filter by the column instead of by the
    connection, and would cross the control-plane/tenant boundary that
    `allow_relation` exists to forbid. Isolation is the connection, not a column.
    """
    from domaine.magasins.models import Magasin

    for field in Magasin._meta.get_fields():
        assert field.name != "client", (
            "Magasin has a `client` field. The database is the client — a client column "
            "here is a second, contradictory source of truth (threat T-02-11)."
        )
        remote = getattr(field, "remote_field", None)
        if remote is not None and getattr(remote, "model", None) is not None:
            target = remote.model
            label = getattr(getattr(target, "_meta", None), "label", "")
            assert label != "control_plane.Client", (
                f"Magasin.{field.name} points at control_plane.Client. Business models "
                "must never reference the control plane; they live in a different "
                "database entirely."
            )


def test_tenant07_magasin_scoped_model_protects_ledger_history():
    """CLAUDE.md #4: stock and caisse are append-only ledgers, so PROTECT, never CASCADE.

    A cascading delete of a magasin would erase the caisse and stock history that
    references it — fiscal records that art. 211 CGI requires be kept for ten years.
    Magasins are deactivated (`actif = False`), never deleted.
    """
    from domaine.magasins.models import MagasinScopedModel

    field = MagasinScopedModel._meta.get_field("magasin")
    assert field.remote_field.on_delete is models.PROTECT, (
        f"MagasinScopedModel.magasin uses on_delete={field.remote_field.on_delete!r}. "
        "It must be models.PROTECT: deleting a magasin must not be able to delete the "
        "append-only ledger rows that reference it (CLAUDE.md non-negotiable #4)."
    )


@pytest.mark.pending
@pytest.mark.tenancy
def test_tenant07_stock_and_caisse_are_scoped_per_magasin():
    """Two magasins in one client database; a movement in each; `for_magasin` returns one.

    TENANT-07's own test. It proves that magasin scoping is an explicit queryset
    projection rather than an implicit filter — the caller names the magasins it wants,
    and Phase 3's permission layer decides which magasins that caller may name.

    Pending: needs the stock and caisse ledger models, which plan 02-06 seeds and
    Phase 5/7 build.
    """
    pytest.fail("pending: implemented by plan 02-06")


@pytest.mark.pending
@pytest.mark.slow
def test_tenant07_provisioning_seeds_requested_magasins():
    """`provision_client(--magasin ...)` creates at least one magasin in the new database.

    A client with zero magasins is not a valid state: every sale, every caisse entry and
    every stock movement is scoped to one. `seed_new_client` must enforce it, and the
    seed must be idempotent (`get_or_create` only) so a killed provisioning run that is
    rerun does not duplicate magasins.

    Pending: needs `provision_client`, which plan 02-04 builds and 02-06 extends.
    """
    pytest.fail("pending: implemented by plan 02-06")
