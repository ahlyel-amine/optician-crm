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


@pytest.mark.tenancy
def test_tenant07_stock_and_caisse_are_scoped_per_magasin(tenant_a):
    """Two magasins in one client database; a movement in each; `for_magasin` returns one.

    TENANT-07's own test. It proves that magasin scoping is an explicit queryset
    projection rather than an implicit filter — the caller names the magasins it wants,
    and Phase 3's permission layer decides which magasins that caller may name.

    **The unscoped half is as load-bearing as the scoped half.** A test that only proved
    `for_magasin` filters would pass against an implicit default-manager filter, and an
    implicit filter silently returns partial data to the owner's dashboard — a wrong
    number with no error, which is worse than a crash. Cross-magasin reads are legitimate
    and constant here, so the plain manager must keep returning everything.
    """
    from decimal import Decimal

    from domaine.caisse.models import EcritureCaisse
    from domaine.magasins.models import Magasin
    from domaine.stock.models import MouvementStock

    centre = Magasin.objects.create(code="CENTRE", nom="Centre")
    maarif = Magasin.objects.create(code="MAARIF", nom="Maarif")

    MouvementStock.objects.create(
        magasin=centre, reference_article="MONT-001", type_mouvement="entree",
        quantite_delta=10,
    )
    MouvementStock.objects.create(
        magasin=maarif, reference_article="MONT-002", type_mouvement="entree",
        quantite_delta=4,
    )
    EcritureCaisse.objects.create(
        magasin=centre, sens="entree", montant=Decimal("1800.00"), libelle="Vente"
    )
    EcritureCaisse.objects.create(
        magasin=maarif, sens="entree", montant=Decimal("950.50"), libelle="Vente"
    )

    scoped_stock = MouvementStock.objects.for_magasin(centre)
    assert scoped_stock.count() == 1
    assert scoped_stock.get().reference_article == "MONT-001"

    scoped_caisse = EcritureCaisse.objects.for_magasin(centre)
    assert scoped_caisse.count() == 1
    assert scoped_caisse.get().montant == Decimal("1800.00")

    # Unscoped reads still see both magasins. This is the assertion that fails if anyone
    # adds an implicit filter in Phase 5, 6 or 7.
    assert MouvementStock.objects.count() == 2
    assert EcritureCaisse.objects.count() == 2
    assert MouvementStock.objects.for_magasins([centre, maarif]).count() == 2


@pytest.mark.tenancy
def test_tenant07_a_magasin_with_ledger_history_cannot_be_deleted(tenant_a):
    """CLAUDE.md #4: the database refuses it, not application code.

    A cascading delete of a magasin would erase the caisse and stock history that
    references it — fiscal records art. 211 CGI requires be kept for ten years. Magasins
    are deactivated (`actif = False`), never deleted. `ProtectedError` comes from
    `on_delete=PROTECT` on the base class, which is why no subclass may override it.
    """
    from django.db.models import ProtectedError

    from domaine.magasins.models import Magasin
    from domaine.stock.models import MouvementStock

    magasin = Magasin.objects.create(code="DEL01", nom="À supprimer")
    MouvementStock.objects.create(
        magasin=magasin, reference_article="X", type_mouvement="entree", quantite_delta=1
    )

    with pytest.raises(ProtectedError):
        magasin.delete()

    assert Magasin.objects.filter(code="DEL01").exists()

    # The supported alternative, so the test also documents what to do instead.
    magasin.actif = False
    magasin.save()
    assert not Magasin.objects.get(code="DEL01").actif


def test_tenant07_ledgers_have_no_mutable_balance_column():
    """CLAUDE.md non-negotiable #4, asserted at the model level.

    Stock and caisse are **append-only ledgers with derived balances**. Quantity on hand
    is the sum of `quantite_delta`; the caisse balance is the sum of `montant`. A stored
    running total is a second source of truth that drifts from the ledger, and the drift
    is discovered by an optician counting the drawer.

    This turns red the moment someone adds a convenience column in Phase 5 or 7, which is
    exactly when it will be tempting.
    """
    from domaine.caisse.models import EcritureCaisse
    from domaine.stock.models import MouvementStock

    forbidden = {
        "solde",
        "solde_actuel",
        "quantite",
        "quantite_stock",
        "quantite_en_stock",
        "stock_actuel",
        "montant_paye",
        "montant_restant",
        "total",
        "balance",
    }
    for model in (MouvementStock, EcritureCaisse):
        names = {f.name for f in model._meta.get_fields()}
        clash = names & forbidden
        assert not clash, (
            f"{model.__name__} has {sorted(clash)}. Stock and caisse are append-only "
            "ledgers with DERIVED balances (CLAUDE.md non-negotiable #4). A stored "
            "running total is a second source of truth and it will drift."
        )


def test_tenant07_ledger_amounts_are_decimal_not_float():
    """CLAUDE.md non-negotiable #7, asserted where it is cheapest.

    Money is `Decimal` with an explicit `decimal_places`, never float. A binary float
    cannot represent 0.10 MAD, so a caisse that totals floats disagrees with the drawer
    by centimes that accumulate — and `assert total == 1800.0` passes while it does.
    """
    from django.db import models

    from domaine.caisse.models import EcritureCaisse
    from domaine.stock.models import MouvementStock

    montant = EcritureCaisse._meta.get_field("montant")
    assert isinstance(montant, models.DecimalField)
    assert montant.decimal_places == 2, (
        f"EcritureCaisse.montant has decimal_places={montant.decimal_places}; MAD has two."
    )
    assert montant.max_digits and montant.max_digits >= 10

    for model in (MouvementStock, EcritureCaisse):
        for field in model._meta.get_fields():
            assert not isinstance(field, models.FloatField), (
                f"{model.__name__}.{field.name} is a FloatField. Money is Decimal "
                "(CLAUDE.md non-negotiable #7), and a float quantity is no better."
            )


def test_tenant04_new_business_apps_are_classified():
    """Pitfall 12: an unclassified new app silently lands on the control-plane database.

    Adding `stock` and `caisse` to `INSTALLED_APPS` without adding them to `BUSINESS_APPS`
    would make the router's `allow_migrate` return `None` for them — no opinion — and
    their tables would be created in `default`, alongside the control plane, for every
    client at once. The `tenancy.E001` system check is what makes forgetting impossible
    rather than merely unlikely; this asserts it is satisfied *and* that it would have
    fired.
    """
    from django.core.management import call_command
    from django.core.management.base import SystemCheckError

    from plateforme.tenancy.router import BUSINESS_APPS

    assert {"stock", "caisse"} <= BUSINESS_APPS, (
        f"stock and caisse are not classified: {sorted(BUSINESS_APPS)}"
    )

    call_command("check")  # raises SystemCheckError on tenancy.E001

    # Negative control: the check must actually fire when an app is unclassified,
    # or "no E001" above is evidence of nothing.
    import plateforme.tenancy.router as router_module

    original = router_module.BUSINESS_APPS
    router_module.BUSINESS_APPS = original - {"caisse"}
    try:
        with pytest.raises(SystemCheckError, match="tenancy.E001"):
            call_command("check")
    finally:
        router_module.BUSINESS_APPS = original

    call_command("check")
