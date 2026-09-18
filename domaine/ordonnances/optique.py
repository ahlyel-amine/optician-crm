"""Les fonctions pures de l'optique : canonicaliser un axe, transposer, figer une copie.

Trois fonctions, aucun accès base, aucun import Django. C'est délibéré : ce sont des
règles d'arithmétique clinique, elles se testent sans une seule ligne écrite nulle part,
et `tests/test_optique.py` est en conséquence le fichier le plus rapide de la suite.

**La convention de stockage est le cylindre négatif, et il n'y en a qu'une.** La forme
positive existe et sert tous les jours — `04-RESEARCH.md` §6.1, sources françaises et
marocaine concordantes : « l'ophtalmologiste prescrit en cylindre négatif […] l'opticien
et le verrier travaillent en cylindre positif, mieux adapté au surfaçage et à la commande
des verres. » Elle est donc **calculée**, jamais rangée dans une seconde colonne : une
seconde colonne serait une seconde source de vérité, et les deux dériveraient le jour où
une correction n'en met à jour qu'une.
"""

from __future__ import annotations

from decimal import Decimal

#: Le quart de tour qui sépare les deux méridiens d'une transposition, et le tour complet
#: d'un axe. Nommés parce qu'ils décrivent la **géométrie**, pas une borne de saisie :
#: `DEMI_TOUR` est la période de l'axe (un axe de 180° et un axe de 0° sont le même
#: méridien), et elle ne change pas quand le propriétaire change d'avis sur les bornes.
QUART_DE_TOUR = 90
DEMI_TOUR = 180


def _exiger_decimal(nom: str, valeur):
    """Refuse tout ce qui n'est pas un `Decimal`. **Lever, jamais convertir.**

    `Decimal(1.5)` depuis un flottant reproduit l'erreur binaire *dans* le type exact, ce
    qui la rend invisible au lieu de l'empêcher. Une transposition est une addition sur
    une grille de 0,25 ; en binaire flottant elle produit des valeurs hors grille, qui
    sont ensuite refusées par le pas — pour une raison incompréhensible au comptoir, dans
    un champ que l'opticien a correctement rempli.
    """
    if not isinstance(valeur, Decimal):
        raise TypeError(
            f"{nom} doit être un Decimal, reçu {type(valeur).__name__} ({valeur!r}). "
            "Une valeur clinique ne transite jamais par un binaire flottant."
        )
    return valeur


def _exiger_entier(nom: str, valeur):
    """Un axe est un nombre entier de degrés. `bool` est un `int` et n'en est pas un."""
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        raise TypeError(
            f"{nom} doit être un entier de degrés, reçu {type(valeur).__name__} "
            f"({valeur!r})."
        )
    return valeur


def canonicaliser_axe(axe: int | None) -> int | None:
    """0 et 180 sont le même axe. **On stocke 180.**

    CLIENT-07 écrit littéralement « 0–180 », donc 0 est **accepté** à la saisie ; mais
    admettre les deux encodages rendrait deux ordonnances portant le même méridien
    incomparables — une recherche, une comparaison de versions et un envoi au verrier les
    traiteraient comme différentes (menace T-04-23).

    **Ce qui n'est délibérément pas fait ici : replier un axe hors plage.**
    L'arithmétique du repli existe (200° est un 20° mal écrit, `04-RESEARCH.md` §6.2),
    mais l'appliquer à la saisie transformerait une faute de frappe en valeur
    **plausible** — c'est-à-dire exactement le mode de défaillance contre lequel tout ce
    module est écrit. Hors de la plage, la valeur passe intacte à la contrainte de base,
    qui la refuse et fait relire l'ordonnance.
    """
    if axe is None:
        return None
    _exiger_entier("axe", axe)
    if axe == 0:
        return DEMI_TOUR
    return axe


def transposer(
    sphere: Decimal, cylindre: Decimal | None, axe: int | None
) -> tuple[Decimal, Decimal | None, int | None]:
    """minus-cyl ↔ plus-cyl. **Sa propre réciproque.**

        sphere'   = sphere + cylindre
        cylindre' = -cylindre
        axe'      = (axe + 90) mod 180, avec 0 ramené à 180

    Vérifiée contre un exemple marocain publié (`04-RESEARCH.md` §6.1,
    `lopticomaroc.com`) : `+1,50 (−0,50 à 20°)` → `+1,00 (+0,50 à 110°)`.

    **Elle n'impose aucun signe au cylindre, et c'est ce qui la rend réciproque.** Le
    refus du cylindre positif est une règle de *stockage*, tenue par une contrainte de
    base ; l'imposer ici rendrait le second aller impossible, donc rendrait la fonction
    inutilisable pour ce à quoi elle sert — ramener dans la convention de stockage une
    valeur saisie en positif.

    Une correction purement sphérique (ni cylindre ni axe) traverse inchangée : c'est le
    cas le plus fréquent au comptoir, et une implémentation centrée sur l'astigmatisme
    l'oublie.
    """
    _exiger_decimal("sphere", sphere)

    if cylindre is None and axe is None:
        return sphere, None, None
    if cylindre is None or axe is None:
        raise ValueError(
            "un cylindre et un axe vont ensemble : transposer l'un sans l'autre "
            "produirait une correction que personne ne peut commander"
        )

    _exiger_decimal("cylindre", cylindre)
    _exiger_entier("axe", axe)

    return (
        sphere + cylindre,
        -cylindre,
        canonicaliser_axe((axe + QUART_DE_TOUR) % DEMI_TOUR),
    )


#: La valeur portée par la clé `convention` d'un instantané. Écrite en clair dans la
#: charge utile parce qu'un verrier qui reçoit trois nombres sans convention monte
#: **l'autre** correction, et qu'aucune des deux ne se devine depuis les valeurs seules.
CONVENTION_DU_SNAPSHOT = "cylindre_positif"


def snapshot_pour_fournisseur(ordonnance) -> dict:
    """Les valeurs **copiées**, en cylindre positif, avec la convention en clair.

    `.planning/research/ARCHITECTURE.md:290` a déjà tranché le point difficile : sur une
    ligne de commande fournisseur, la prescription est **copiée (figée), pas
    référencée**, pour qu'une correction saisie après l'envoi ne change pas
    silencieusement ce qui a été commandé. Cette fonction produit cette copie — un
    dictionnaire de valeurs immuables, détaché de l'instance.

    **Elle ne crée aucune table de suivi de commande spéciale, et ce n'est pas un
    oubli.** `04-RESEARCH.md` §3.4 et la zone grise 2 de `04-CONTEXT.md` en proposaient
    une ; mais la feuille de route donne le cycle de vie de la commande spéciale —
    commandé → prêt → client prévenu → livré — à **STOCK-08, phase 5**. La poser ici
    préempterait cette phase-là, qui aurait alors à migrer une table qu'elle n'a pas
    dessinée. **La phase 4 livre le producteur de la copie et son test ; la phase 5 pose
    la table ; la phase 8 la branche au bon de commande. CLIENT-08 n'est cochée par
    aucune des trois** — une case cochée doit vouloir dire « un opticien peut le faire ».
    """
    return {
        "convention": CONVENTION_DU_SNAPSHOT,
        "ordonnance_id": ordonnance.pk,
        "version": ordonnance.version,
        "date_prescription": ordonnance.date_prescription,
        "od": _oeil_transpose(
            ordonnance.sphere_od,
            ordonnance.cylindre_od,
            ordonnance.axe_od,
            ordonnance.addition_od,
        ),
        "og": _oeil_transpose(
            ordonnance.sphere_og,
            ordonnance.cylindre_og,
            ordonnance.axe_og,
            ordonnance.addition_og,
        ),
        "ep_saisi": ordonnance.ep_saisi,
        "ep_binoculaire": ordonnance.ep_binoculaire,
        "ep_mono_od": ordonnance.ep_mono_od,
        "ep_mono_og": ordonnance.ep_mono_og,
    }


def _oeil_transpose(sphere, cylindre, axe, addition) -> dict:
    """Un œil en cylindre positif. Un œil non corrigé reste entièrement vide.

    L'addition ne se transpose pas : elle est une addition de puissance en vision de
    près, pas une composante du cylindre, et la transposer serait une faute silencieuse
    de +0,25 à +4,00 dioptries sur le verre de lecture.
    """
    if sphere is None:
        return {"sphere": None, "cylindre": None, "axe": None, "addition": addition}

    sphere_plus, cylindre_plus, axe_plus = transposer(sphere, cylindre, axe)
    return {
        "sphere": sphere_plus,
        "cylindre": cylindre_plus,
        "axe": axe_plus,
        "addition": addition,
    }
