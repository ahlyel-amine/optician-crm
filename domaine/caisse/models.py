"""The caisse ledger — append-only, magasin-scoped, with a derived balance.

The **Phase 2 core that Phase 7 extends, not a placeholder.** It carries a magasin, a
sens, an amount, a label, a timestamp, and the one flag that Phase 7 cannot be built
without. Session de caisse, mode de règlement detail, the chèque encaissement lifecycle
and the daily reconciliation belong to Phase 7.

**No magasin contextvar and no implicit default-manager filter, deliberately** — see the
same note in `domaine/stock/models.py`. Phase 3 resolves which magasins; the caller passes
them to `for_magasins()`.
"""

from __future__ import annotations

from django.db import models

from domaine.magasins.models import MagasinScopedModel


class SensEcriture(models.TextChoices):
    ENTREE = "entree", "Entrée"
    SORTIE = "sortie", "Sortie"


class EcritureCaisse(MagasinScopedModel):
    """One movement of money in one magasin's caisse.

    **The balance is DERIVED**, by summing signed `montant` over the entries that count
    (CLAUDE.md non-negotiable #4). There is no `solde` column and there must never be:
    a stored balance is a second source of truth, and the optician finds the drift by
    counting the drawer.

    `montant` is always **positive**; direction is `sens`. Storing a signed amount would
    make "is this a refund or a negative sale?" ambiguous, and it would let a sign error
    pass the constraint.

    `effet_sur_solde` exists in Phase 2 rather than Phase 7 because CLAUDE.md
    non-negotiable #5 cannot be retrofitted onto a ledger that assumes it: **a chèque is
    not cash until `encaissé`.** Post-dated chèques are normal in Morocco, and counting one
    as cash on the day it is taken makes the caisse balance wrong. So an écriture carries
    an explicit flag rather than being assumed to move the balance on its creation date.
    Phase 7 adds the échéance, the encaissement date and the lifecycle that flips it.

    Corrections are compensating entries — an opposite `sens` — never an edit
    (CLAUDE.md #4, and `test_caisse05_correction_is_a_compensating_entry_not_an_edit` in
    Phase 7).
    """

    sens = models.CharField(max_length=8, choices=SensEcriture.choices)
    #: MAD. Decimal, never float (CLAUDE.md non-negotiable #7): a binary float cannot
    #: represent 0.10, and a caisse that totals floats disagrees with the drawer by
    #: centimes that accumulate.
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    libelle = models.CharField(max_length=200)
    #: False for a chèque not yet encaissé. See the class docstring.
    effet_sur_solde = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "écriture de caisse"
        verbose_name_plural = "écritures de caisse"
        indexes = [
            # Composite and leading with `magasin`: the daily caisse view is always
            # "this magasin, this day", never "this day across the company".
            models.Index(
                fields=["magasin", "created_at"], name="idx_ecr_magasin_date"
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(montant__gt=0),
                name="ecriture_caisse_montant_positif",
                violation_error_message=(
                    "An écriture's montant is always positive; direction is `sens`. A "
                    "signed amount makes a sign error indistinguishable from a refund."
                ),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.sens} {self.montant} — {self.libelle}"
