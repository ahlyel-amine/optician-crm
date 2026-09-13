"""The stock ledger — append-only, magasin-scoped, with a derived quantity on hand.

This is the **Phase 2 core that Phase 5 extends, not a placeholder and not a fixture.**
It carries only what TENANT-07 needs — a magasin, a type, a signed quantity, a reference,
a timestamp. Article references, fournisseur links, achat links, prix d'achat and
inventaire sessions belong to Phase 5, which has its own requirements and its own open
questions; inventing their shapes here would pre-empt them.

**No magasin contextvar and no implicit default-manager filter, deliberately.** The
asymmetry with client scoping is the point: a client is a connection and fails closed, a
magasin is a column and is explicit. Cross-magasin reads are legitimate and constant here
— the owner's dashboard, réappro across magasins — and an implicit filter would silently
return partial data to that dashboard: a wrong number with no error, which is worse than a
crash. Phase 3's permission layer resolves *which* magasins a caller may read and the
caller passes them:

    MouvementStock.objects.for_magasins(request.user.magasins_autorises)

Phase 2 supplies the queryset method; Phase 3 supplies the list. Keeping them separate is
what stops every module re-inventing the projection layer.
"""

from __future__ import annotations

from django.db import models

from domaine.magasins.models import MagasinScopedModel


class TypeMouvement(models.TextChoices):
    ENTREE = "entree", "Entrée"
    SORTIE = "sortie", "Sortie"
    AJUSTEMENT = "ajustement", "Ajustement"
    INVENTAIRE = "inventaire", "Inventaire"


class MouvementStock(MagasinScopedModel):
    """One movement of one article in one magasin.

    **Quantity on hand is DERIVED**, by summing `quantite_delta` for an article in a
    magasin. There is deliberately no stored quantity column (CLAUDE.md non-negotiable
    #4), which is why the field is a signed *delta* and never a running total: a stored
    total is a second source of truth, and the drift is discovered by someone counting
    the shelf.

    Corrections are compensating entries — a movement of the opposite sign — never an
    edit of an existing row.
    """

    reference_article = models.CharField(max_length=64, db_index=True)
    type_mouvement = models.CharField(max_length=16, choices=TypeMouvement.choices)
    #: Signed. +10 received, -1 sold, and a correction is another row, never an edit.
    quantite_delta = models.IntegerField()
    motif = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "mouvement de stock"
        verbose_name_plural = "mouvements de stock"
        indexes = [
            # Composite and leading with `magasin`, per MagasinScopedModel's convention:
            # an index on created_at alone is near-useless once there are several magasins.
            models.Index(
                fields=["magasin", "reference_article", "created_at"],
                name="idx_mvt_magasin_ref_date",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(quantite_delta=0),
                name="mouvement_stock_delta_non_nul",
                violation_error_message=(
                    "A stock movement of zero moves nothing. It is either a mistake or a "
                    "row that should not exist; either way the ledger must not carry it."
                ),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.reference_article} {self.quantite_delta:+d} ({self.magasin_id})"
