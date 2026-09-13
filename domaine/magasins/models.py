"""TENANT-07 — magasins, and the scoping convention every later phase inherits.

This module is deliberately small, and deliberately opinionated about what it does *not*
do. Read `MagasinScopedModel`'s docstring before adding a magasin-scoped model in
Phase 5, 6 or 7 — retrofitting these conventions once there are ledgers is expensive.

`domaine/*` never imports from `plateforme/tenancy` except for this base. If
tenant-awareness leaks into sales code, every later feature has to re-learn it.
"""

from __future__ import annotations

from django.db import models


class Magasin(models.Model):
    """One point of sale belonging to the optician business this database *is*.

    **No client ForeignKey.** The database is the client. A `client_id` column here
    would be a second, contradictory source of truth and an invitation to filter by it
    instead of by the connection — which is the leak the whole tenancy phase exists to
    prevent (threat T-02-11).

    Magasins are deactivated (`actif = False`), never deleted: stock and caisse are
    append-only ledgers (CLAUDE.md non-negotiable #4) and their rows PROTECT this one.
    """

    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=120)
    adresse = models.TextField(blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    actif = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "magasin"
        verbose_name_plural = "magasins"

    def __str__(self) -> str:
        return f"{self.code} — {self.nom}"


class MagasinScopedQuerySet(models.QuerySet):
    """Explicit magasin projection. The caller names the magasins; nothing is implicit.

    Phase 3's permission layer decides *which* magasins a user may read, and passes them
    in: `Mouvement.objects.for_magasins(user.magasins_autorises)`. Keeping the "which"
    and the "how" separate is what stops the projection from being re-invented in every
    module.
    """

    def for_magasin(self, magasin):
        return self.filter(magasin=magasin)

    def for_magasins(self, magasins):
        return self.filter(magasin__in=magasins)


class MagasinScopedModel(models.Model):
    """Base for every model whose rows belong to exactly one magasin.

    Stock movements, caisse entries, ventes, séries de facturation.

    Three conventions come with it, and later phases must not re-invent them:

    1. **`on_delete=PROTECT`, never CASCADE.** Stock and caisse are append-only ledgers
       (CLAUDE.md #4); a cascading delete of a magasin would erase fiscal history that
       art. 211 CGI requires be kept ten years. Deactivate (`actif = False`) instead.
    2. **Scoped uniqueness.** Anything unique *within* a magasin is
       ``UniqueConstraint(fields=["magasin", "<field>"], name="uniq_<model>_magasin_<field>")``
       — never ``unique=True`` on the field alone, which would stop two magasins using
       the same article reference.
    3. **Every magasin-scoped index is composite and leads with `magasin`** —
       ``Index(fields=["magasin", "date"])``. An index on ``date`` alone is near-useless
       once there are several magasins.

    And the deliberate non-convention: **there is no implicit magasin filter and no
    magasin contextvar.** Unlike the client boundary, cross-magasin reads are legitimate
    and constant — the owner's dashboard, réappro across magasins, and possibly one
    facture série for the whole company (CLAUDE.md open question #2 is unresolved, so
    the model must not assume either answer). An implicit filter would return a *wrong
    number with no error*, which is worse than a crash.
    """

    magasin = models.ForeignKey(
        "magasins.Magasin",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )

    objects = MagasinScopedQuerySet.as_manager()

    class Meta:
        abstract = True
