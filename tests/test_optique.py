"""CLIENT-07 / CLIENT-08 — les fonctions pures de l'optique, et l'unicité des bornes.

**Aucune fixture de base.** C'est le fichier le plus rapide de la suite et il doit le
rester : la transposition, la canonicalisation de l'axe et la garde de source sont trois
questions qui n'ont besoin d'aucune ligne écrite nulle part. Un `db_all` ajouté ici par
commodité coûterait une transaction par test sur trois bases pour vérifier une addition.

Une garde de source vit ici, **par AST** et accompagnée de son contrôle positif
synthétique : les bornes cliniques n'apparaissent qu'à **un** endroit,
`domaine/ordonnances/bornes.py`. La seconde garde AST de ce plan — rien dans le dépôt ne
*calcule* un écart pupillaire monoculaire depuis un binoculaire — vit dans
`tests/test_ordonnances.py`, collée à l'assertion sur la colonne `ep_saisi` qu'elle
complète.

Pourquoi l'AST et non `grep`. Le piège s'est produit dix fois dans ce projet, dont deux
fois parce qu'un plan demandait d'écrire un commentaire contenant le symbole que sa propre
garde cherchait (CLAUDE.md, section Testing). Une garde qui lit les nœuds `ast.Constant`
ne peut pas attraper la prose qui *cite* un nombre, et le contrôle positif ci-dessous
contient délibérément un module dont la docstring les cite tous.
"""

from __future__ import annotations

import ast
import textwrap
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent


# ======================================================================================
# CLIENT-08 — la transposition minus-cyl <-> plus-cyl, fonction pure
# ======================================================================================
#
# Les ophtalmologistes prescrivent en cylindre négatif ; les opticiens et les verriers
# travaillent en positif et transposent quotidiennement (`04-RESEARCH.md` §6.1). Le
# stockage n'admet qu'une convention ; la seconde forme est **calculée**, jamais stockée.

#: Une table de corrections réelles, en `Decimal`. La dernière ligne est la prescription
#: purement sphérique — sans cylindre ni axe —, qui est le cas le plus fréquent au
#: comptoir et celui qu'une implémentation centrée sur l'astigmatisme oublie.
CORRECTIONS = [
    ("exemple-marocain", Decimal("1.50"), Decimal("-0.50"), 20),
    ("myope-astigmate", Decimal("-3.25"), Decimal("-1.75"), 175),
    ("axe-a-90", Decimal("0.00"), Decimal("-2.00"), 90),
    ("axe-a-180", Decimal("-1.00"), Decimal("-0.25"), 180),
    ("axe-a-1", Decimal("4.75"), Decimal("-10.00"), 1),
    ("sans-cylindre", Decimal("2.00"), None, None),
]


@pytest.mark.parametrize(
    ("etiquette", "sphere", "cylindre", "axe"),
    CORRECTIONS,
    ids=[cas[0] for cas in CORRECTIONS],
)
def test_client07_transposition_aller_retour_est_identite(etiquette, sphere, cylindre, axe):
    """`transposer(transposer(v)) == v`, pour chaque correction de la table.

    Le test le plus court du fichier et le plus difficile à faire passer par hasard : la
    réciprocité tient les **trois** composantes ensemble. Une implémentation qui
    oublierait d'inverser le signe du cylindre, ou qui replierait l'axe dans le mauvais
    sens, produirait un aller simple plausible et un aller-retour faux.

    **Ce qu'il attrape :** la transposition écrite dans un seul sens. C'est la faute
    naturelle, parce que l'opticien n'en voit qu'un — et le second sens est exactement
    celui qui ramène la valeur dans la convention de stockage avant l'enregistrement.
    """
    from domaine.ordonnances.optique import transposer

    aller = transposer(sphere, cylindre, axe)
    retour = transposer(*aller)

    assert retour == (sphere, cylindre, axe), (
        f"{etiquette} : ({sphere}, {cylindre}, {axe}) -> {aller} -> {retour}. "
        "La transposition doit être sa propre réciproque."
    )


def test_client07_la_transposition_suit_l_exemple_marocain_verifie():
    """`+1,50 (−0,50 à 20°)` → `+1,00 (+0,50 à 110°)`, l'exemple travaillé de la recherche.

    Une valeur **publiée** (`04-RESEARCH.md` §6.1, source `lopticomaroc.com`), et non la
    formule ré-appliquée à l'envers dans l'assertion. Un test qui recalculerait
    `sphere + cylindre` pour se comparer à `sphere + cylindre` serait vert contre
    n'importe quelle formule, y compris une soustraction.
    """
    from domaine.ordonnances.optique import transposer

    assert transposer(Decimal("1.50"), Decimal("-0.50"), 20) == (
        Decimal("1.00"),
        Decimal("0.50"),
        110,
    )


def test_client07_la_transposition_replie_l_axe_et_n_emet_jamais_zero():
    """`(axe + 90) mod 180`, **avec 0 ramené à 180**, posé aux deux bords.

    `axe = 90` donnerait `180 mod 180 = 0` en arithmétique nue. Or 0 n'est pas un axe
    écrit sur une ordonnance : 0 et 180 désignent le même méridien et la prescription
    écrit 180. Un 0 émis ici entrerait dans une ordonnance transposée puis serait refusé
    par la borne `1..180` — un refus incompréhensible au comptoir, causé par une
    fonction interne.
    """
    from domaine.ordonnances.optique import transposer

    _, _, axe_depuis_90 = transposer(Decimal("0.00"), Decimal("-1.00"), 90)
    _, _, axe_depuis_180 = transposer(Decimal("0.00"), Decimal("-1.00"), 180)

    assert axe_depuis_90 == 180, f"90° doit donner 180°, obtenu {axe_depuis_90}"
    assert axe_depuis_180 == 90, f"180° doit donner 90°, obtenu {axe_depuis_180}"

    for _, sphere, cylindre, axe in CORRECTIONS:
        if axe is None:
            continue
        assert transposer(sphere, cylindre, axe)[2] != 0, (
            f"la transposition de {axe}° a émis 0, qu'aucune ordonnance ne porte"
        )


def test_client07_la_canonicalisation_de_l_axe_ne_replie_pas_une_faute_de_frappe():
    """`0 → 180`, et **rien d'autre n'est replié**.

    Deux règles en une, et la seconde est la moins évidente : `canonicaliser_axe` ne
    ramène pas 400° à 40°. L'arithmétique du repli existe (`04-RESEARCH.md` §6.2), mais
    l'appliquer à la saisie transformerait une faute de frappe en valeur **plausible**,
    c'est-à-dire exactement le mode de défaillance que tout ce plan combat. Hors de
    `0..180`, la valeur passe intacte à la borne, qui la refuse.
    """
    from domaine.ordonnances.optique import canonicaliser_axe

    assert canonicaliser_axe(0) == 180
    assert canonicaliser_axe(180) == 180
    assert canonicaliser_axe(90) == 90
    assert canonicaliser_axe(1) == 1
    assert canonicaliser_axe(None) is None
    assert canonicaliser_axe(400) == 400, (
        "400° doit rester 400° pour que la borne le refuse. Le replier donnerait 40°, "
        "une valeur plausible et fausse."
    )


@pytest.mark.parametrize(
    ("etiquette", "sphere", "cylindre", "axe"),
    [
        ("sphere-flottante", 1.5, Decimal("-0.50"), 20),
        ("cylindre-flottant", Decimal("1.50"), -0.5, 20),
        ("axe-flottant", Decimal("1.50"), Decimal("-0.50"), 20.0),
        ("sphere-en-chaine", "1.50", Decimal("-0.50"), 20),
    ],
    ids=["sphere-flottante", "cylindre-flottant", "axe-flottant", "sphere-en-chaine"],
)
def test_client07_la_transposition_est_en_decimal_jamais_en_flottant(
    etiquette, sphere, cylindre, axe
):
    """`transposer` reçoit et rend des `Decimal` ; un `float` **lève**.

    **Ce qu'il attrape :** la trappe que CLAUDE.md nomme pour l'argent — une assertion
    sur un flottant passe pendant que la valeur est fausse. Ici la valeur n'est pas de
    l'argent, mais elle a la même propriété : la transposition est une addition sur une
    grille de 0,25, et en binaire flottant `1.1 + (-0.3)` produit une valeur hors grille
    qui serait ensuite refusée par le pas — pour une raison illisible au comptoir, dans
    un champ que l'opticien a correctement rempli.

    Lever plutôt que convertir : `Decimal(1.5)` depuis un flottant reproduit l'erreur
    binaire dans le type exact, ce qui la rend invisible au lieu de l'empêcher.
    """
    from domaine.ordonnances.optique import transposer

    with pytest.raises(TypeError):
        transposer(sphere, cylindre, axe)


# ======================================================================================
# D-4b — les bornes cliniques vivent à UN endroit nommé
# ======================================================================================

#: Les valeurs de `BORNES`, en **magnitude** : le signe est porté par un `ast.UnaryOp`,
#: donc chercher `-20` comme constante ne trouverait jamais rien. Comparer en `Decimal`
#: plutôt qu'en `float` fait tenir `4`, `4.0` et `"4.00"` pour la même valeur, ce qui est
#: le but : les trois formes sont le même nombre clinique recopié.
MAGNITUDES_CLINIQUES = frozenset(
    {
        Decimal("20"),
        Decimal("10"),
        Decimal("1"),
        Decimal("180"),
        Decimal("0.75"),
        Decimal("4"),
        Decimal("0.25"),
        Decimal("45"),
        Decimal("85"),
        Decimal("18"),
        Decimal("44.5"),
        Decimal("0.5"),
    }
)

#: Les mots-clés qui décrivent la **forme** d'une colonne, pas une règle clinique.
#: `DecimalField(max_digits=4, decimal_places=1)` parle de stockage ; le `4` qu'il porte
#: n'est pas l'addition maximale, et l'exclure est ce qui rend la garde utilisable sans
#: l'affaiblir. Tout autre littéral numérique est suspect.
ARGUMENTS_DE_FORME = frozenset({"max_digits", "decimal_places", "max_length"})


def _en_decimal(valeur) -> Decimal | None:
    """La valeur d'un `ast.Constant` en `Decimal`, ou `None` si ce n'est pas un nombre.

    Les chaînes sont converties **seulement si elles sont entièrement numériques** —
    `Decimal("0.25")` est la façon normale d'écrire un décimal en Python, donc l'ignorer
    laisserait la recopie la plus probable passer. Une docstring, elle, n'est pas un
    nombre : c'est ce qui empêche cette garde d'attraper sa propre prose.
    """
    if isinstance(valeur, bool):
        return None
    if isinstance(valeur, int | float):
        return Decimal(str(valeur))
    if isinstance(valeur, str):
        try:
            nombre = Decimal(valeur.strip())
        except (InvalidOperation, ValueError):
            return None
        return nombre if nombre.is_finite() else None
    return None


def literaux_cliniques(source: str) -> list[str]:
    """Les littéraux numériques d'un module qui recopient une valeur de `BORNES`."""
    arbre = ast.parse(source)

    exclus: set[int] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Call):
            for motcle in noeud.keywords:
                if motcle.arg in ARGUMENTS_DE_FORME:
                    exclus.update(id(sous) for sous in ast.walk(motcle.value))

    fautes = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Constant) or id(noeud) in exclus:
            continue
        nombre = _en_decimal(noeud.value)
        if nombre is not None and abs(nombre) in MAGNITUDES_CLINIQUES:
            fautes.append(f"ligne {noeud.lineno} : {noeud.value!r}")
    return fautes


def _modules_du_domaine_ordonnances() -> dict[str, str]:
    """Les modules de `domaine/ordonnances/` que la garde surveille, hors migrations.

    `serializers.py` n'existe qu'au plan 04-05 : la garde le prendra sans qu'une ligne
    change ici, ce qui est le seul moyen qu'elle soit encore vraie dans deux plans.
    """
    paquet = RACINE / "domaine" / "ordonnances"
    surveilles = ("models.py", "serializers.py", "vues.py", "services.py")
    return {
        nom: (paquet / nom).read_text(encoding="utf-8")
        for nom in surveilles
        if (paquet / nom).exists()
    }


def test_client07_les_bornes_vivent_a_un_seul_endroit():
    """Aucun nombre clinique n'est recopié hors de `domaine/ordonnances/bornes.py`.

    D-4b : « les bornes vivent à UN endroit nommé […] le prochain changement doit coûter
    une ligne. » Le propriétaire a déjà changé d'avis une fois sur ces chiffres. Un
    validateur de champ qui écrirait `MinValueValidator(Decimal("-20.00"))` serait un
    second endroit, et les deux dériveraient — silencieusement, puisque rien ne compare
    un validateur à une contrainte.

    **Ce qu'il attrape :** la contrainte de base ou le validateur écrit à la main au lieu
    d'être dérivé de `BORNES`. C'est la forme la plus naturelle à écrire, et la seule
    qui ne rougit jamais toute seule.
    """
    modules = _modules_du_domaine_ordonnances()

    assert "models.py" in modules, (
        "la garde n'a trouvé aucun module à lire dans domaine/ordonnances/ ; "
        "une garde qui ne lit rien est verte pour toujours"
    )

    fautes = {
        nom: literaux
        for nom, source in modules.items()
        if (literaux := literaux_cliniques(source))
    }

    assert not fautes, (
        "Nombres cliniques recopiés hors de bornes.py :\n"
        + "\n".join(f"  {nom} :: {', '.join(lignes)}" for nom, lignes in fautes.items())
        + "\n\nLes lire depuis `domaine.ordonnances.bornes.BORNES`."
    )


BORNE_RECOPIEE_DANS_UN_VALIDATEUR = textwrap.dedent(
    """
    from decimal import Decimal
    from django.core.validators import MinValueValidator
    from django.db import models

    class Ordonnance(models.Model):
        sphere_od = models.DecimalField(
            max_digits=4, decimal_places=2,
            validators=[MinValueValidator(Decimal("-20.00"))],
        )
    """
)

BORNE_RECOPIEE_EN_CONTRAINTE = textwrap.dedent(
    """
    from django.db import models

    class Ordonnance(models.Model):
        class Meta:
            constraints = [
                models.CheckConstraint(
                    condition=models.Q(axe_od__lte=180), name="axe_borne"
                ),
            ]
    """
)

BORNES_LUES_DEPUIS_LE_MODULE = textwrap.dedent(
    """
    from decimal import Decimal
    from django.db import models
    from domaine.ordonnances.bornes import BORNES

    class Ordonnance(models.Model):
        sphere_od = models.DecimalField(max_digits=4, decimal_places=2, null=True)

        class Meta:
            constraints = [
                models.CheckConstraint(
                    condition=models.Q(
                        sphere_od__gte=Decimal(BORNES["sphere"]["min"]),
                        sphere_od__lte=Decimal(BORNES["sphere"]["max"]),
                    ),
                    name="sphere_od_bornes",
                ),
            ]
    """
)

PROSE_QUI_CITE_LES_BORNES = textwrap.dedent(
    '''
    """La sphère va de −20,00 à +20,00, par pas de 0,25, et l'axe de 1 à 180.

    Ces nombres ne vivent pas ici : ils sont lus depuis `bornes.BORNES`. Cette
    docstring les cite pour que le lecteur sache ce que la colonne porte.
    """

    from domaine.ordonnances.bornes import BORNES
    '''
)


@pytest.mark.parametrize(
    ("etiquette", "source", "fautif"),
    [
        ("borne-dans-un-validateur", BORNE_RECOPIEE_DANS_UN_VALIDATEUR, True),
        ("borne-dans-une-contrainte", BORNE_RECOPIEE_EN_CONTRAINTE, True),
        ("bornes-lues-depuis-le-module", BORNES_LUES_DEPUIS_LE_MODULE, False),
        ("prose-qui-cite-les-bornes", PROSE_QUI_CITE_LES_BORNES, False),
    ],
    ids=[
        "borne-dans-un-validateur",
        "borne-dans-une-contrainte",
        "bornes-lues-depuis-le-module",
        "prose-qui-cite-les-bornes",
    ],
)
def test_client07_la_garde_des_bornes_est_prouvee_sur_des_modules_synthetiques(
    etiquette, source, fautif
):
    """Un détecteur jamais éprouvé sur un cas fautif est un détecteur vert et vide.

    Le quatrième cas est le plus important : une docstring qui **cite** les bornes en
    toutes lettres ne doit pas être attrapée. C'est la dixième occurrence, dans ce
    projet, du critère qui attrape sa propre prose, et la seule protection structurelle
    est de lire des nœuds plutôt que du texte.
    """
    fautes = literaux_cliniques(source)

    if fautif:
        assert fautes, f"{etiquette} : la garde a laissé passer une borne recopiée"
    else:
        assert not fautes, f"{etiquette} : faux positif — {fautes}"

