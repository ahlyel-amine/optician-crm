"""Step 4 of provisioning — the rows a brand-new client database cannot open without.

Two rules govern everything in here.

**Idempotent, always.** Provisioning is a state machine that must survive being killed
and rerun, and seeding is the step that would otherwise duplicate. Every write is
`get_or_create` or `update_or_create`; there is no blind `create()` in this module and
there must never be.

**A client business with zero magasins is not a valid state** (`02-RESEARCH.md` section 9
rule 5). Every sale, every caisse entry and every stock movement is scoped to exactly one
magasin, so a client with none is an account that looks provisioned and cannot sell
anything. The rule lives here rather than in the management command, so that the Phase 12
self-serve signup — which calls `provision_client` directly, not the command — inherits it.

Runs inside the caller's `tenant_context`. It must not open its own: `provision_client`
owns the binding, and a second `tenant_context` here would hide a caller that forgot.
"""

from __future__ import annotations

from django.utils.text import slugify


class SeedError(ValueError):
    """A client cannot be seeded into a valid state from the arguments given."""


def _magasin_specs(magasins) -> list[dict[str, str]]:
    """Normalise the `magasins` argument to `[{"code": ..., "nom": ...}, ...]`.

    Accepts a list of names (`["Centre", "Maarif"]`) or a list of dicts carrying an
    explicit `code`. A derived code is the slugified name, upper-cased and truncated to
    the column width, de-duplicated with a numeric suffix.

    **Derivation is deterministic**, which is the whole point: a rerun of a killed
    provisioning run must produce the same codes so that `get_or_create(code=...)` matches
    the existing rows instead of creating a second set (threat T-02-42).
    """
    specs: list[dict[str, str]] = []
    seen: set[str] = set()

    for entry in magasins:
        if isinstance(entry, dict):
            nom = (entry.get("nom") or entry.get("name") or "").strip()
            code = (entry.get("code") or "").strip().upper()
        else:
            nom = str(entry).strip()
            code = ""

        if not nom and not code:
            raise SeedError(
                "A magasin needs at least a name. Got an empty entry in the magasins "
                "list."
            )
        nom = nom or code

        if not code:
            code = slugify(nom).upper().replace("-", "")[:20] or "MAG"

        base, suffix = code, 2
        while code in seen:
            # Deterministic: the same input list always produces the same suffixes.
            code = f"{base[:18]}{suffix}"
            suffix += 1
        seen.add(code)

        specs.append({"code": code, "nom": nom})

    return specs


def seed_new_client(client, magasins) -> list:
    """Create the magasins a new client database needs. Idempotent. Returns the rows.

    `client` is the control-plane `Client` row, passed for context and for later
    extension points; the rows written here go to whichever tenant alias the caller has
    bound, resolved by the router.
    """
    if not magasins:
        raise SeedError(
            f"Client {client.code!r} was requested with no magasin. A client business "
            "must have at least one magasin: every sale, caisse entry and stock movement "
            "is scoped to exactly one, so a client with none is an account that looks "
            "provisioned and cannot sell anything."
        )

    from domaine.magasins.models import Magasin

    rows = []
    for spec in _magasin_specs(magasins):
        magasin, _ = Magasin.objects.get_or_create(
            code=spec["code"], defaults={"nom": spec["nom"]}
        )
        rows.append(magasin)

    # ----------------------------------------------------------------------------------
    # EXTENSION POINT — later phases seed their own defaults here, in this order:
    #
    #   Phase 5 (stock)       : none currently foreseen; articles are entered, not seeded.
    #   Phase 6 (facturation) : TVA rates per article category, and the facture série.
    #                           Blocked on CLAUDE.md open questions #1 and #2 — which TVA
    #                           rates apply after the 2026 reform, and whether a série per
    #                           magasin is legal or one continuous série per company is
    #                           required. Do not guess: the shape of the seed depends on
    #                           the answer, and a wrong série is the client's tax exposure.
    #   Phase 8 (branding)    : logo, couleurs, mentions légales on the facture footer.
    #
    # Whatever lands here must stay `get_or_create` / `update_or_create`.
    # ----------------------------------------------------------------------------------

    return rows
