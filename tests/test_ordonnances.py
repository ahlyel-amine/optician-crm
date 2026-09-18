"""CLIENT-03/04/05/07/08 — le modèle `Ordonnance` et ses règles cliniques.

Le mode de défaillance contre lequel ce fichier est écrit n'est pas la valeur hors
bornes : c'est la **valeur plausible et fausse**. Un axe de 90 saisi pour 9 passe toutes
les bornes. La validation attrape l'impossible ; le rattrapage de la faute crédible est
structurel — CLIENT-06 (plan 04-05) et l'écran de relecture (plan 04-08).

Ce que ce fichier tient, et que rien d'autre ne tient :

* la borne est refusée **par la base**, prouvé par un `bulk_create` — un test qui
  passerait par l'API serait vert au-dessus d'un modèle sans contrainte ;
* `Ordonnance` **n'est pas** scopée au magasin, et le porte quand même. Le garde
  `vues_sans_portee_magasin` est structurellement aveugle à un modèle non scopé, donc
  seule une assertion **positive** peut tenir cette décision (D-4a, menace T-04-22) ;
* aucune ligne du dépôt ne calcule un écart pupillaire monoculaire depuis un binoculaire.

**Pourquoi `bulk_create` et pas `Model.objects.create`.** `bulk_create` contourne
`save()` et `clean()`. Si la borne n'existe que dans le sérialiseur ou dans `save()`, la
ligne entre en base et la fiche est fausse sans qu'aucun test ne rougisse. C'est le
raisonnement que `plateforme/control_plane/models.py` a déjà écrit pour
`active_client_has_db_name`, appliqué au domaine clinique.
"""

from __future__ import annotations

import ast
import textwrap
from decimal import Decimal
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent

#: Les arbres applicatifs scannés par la garde de l'écart pupillaire. `tests/` en est
#: exclu : la source synthétique du contrôle positif contient, exprès, la faute.
ARBRES_SCANNES = ("plateforme", "domaine")

ALIAS = "tenant_a"


def _ordonnance_valide(client, magasin, **surcharges):
    """Une ordonnance **non enregistrée**, cliniquement valide, prête à être surchargée.

    Construite par la fabrique en mode `build` : `bulk_create` a besoin d'instances non
    sauvegardées, et une `SubFactory` en mode `build` produirait un client sans clé
    primaire. Le client et le magasin sont donc passés, déjà enregistrés.
    """
    from tests.factories import OrdonnanceFactory

    return OrdonnanceFactory.build(client=client, magasin=magasin, **surcharges)


def _inserer(instances):
    """`bulk_create` sur la base du locataire, en passant à côté de `save()`."""
    from domaine.ordonnances.models import Ordonnance

    return Ordonnance.objects.bulk_create(instances)


def _refus(instances):
    """Attend une `IntegrityError` de la base, dans un point de reprise propre.

    Le `atomic()` est **à l'intérieur** du `pytest.raises` : sans lui, la transaction du
    test reste cassée après le refus et tout ce qui suit échoue avec
    `current transaction is aborted`, c'est-à-dire pour une raison qui ne nomme pas la
    cause.
    """
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError), transaction.atomic(using=ALIAS):
        _inserer(instances)


# ======================================================================================
# CLIENT-03 — la grille OD/OG, structurée et plate
# ======================================================================================
def test_client03_od_og_sont_structures_et_plats(db_all, deux_magasins):
    """Onze colonnes distinctes, en `Decimal` — jamais une ligne par œil, jamais un float.

    **Colonnes plates plutôt que deux lignes par ordonnance.** Deux lignes rendraient
    représentable « axe OD présent, sphère OD absente », feraient de chaque lecture une
    agrégation et de chaque contrôle inter-yeux une auto-jointure. Onze colonnes n'est
    pas un échec de modélisation, c'est le domaine.

    **Ce qu'il attrape :** un `FloatField` posé par habitude. `0.1 + 0.2` sort de la
    grille de 0,25 et la valeur devient irreprésentable — la même trappe que CLAUDE.md
    nomme pour l'argent, sur une valeur qui décide d'une paire de verres.
    """
    from django.db import models

    from domaine.ordonnances.models import Ordonnance

    decimales = [
        "sphere_od",
        "sphere_og",
        "cylindre_od",
        "cylindre_og",
        "addition_od",
        "addition_og",
        "ep_binoculaire",
        "ep_mono_od",
        "ep_mono_og",
    ]
    entieres = ["axe_od", "axe_og"]

    for nom in decimales:
        champ = Ordonnance._meta.get_field(nom)
        assert isinstance(champ, models.DecimalField), (
            f"{nom} est un {type(champ).__name__} ; une valeur clinique se stocke en "
            "Decimal, jamais en binaire flottant"
        )
        assert not isinstance(champ, models.FloatField)
        assert champ.null, f"{nom} doit accepter NULL : une ordonnance peut ne pas le porter"

    for nom in entieres:
        champ = Ordonnance._meta.get_field(nom)
        assert isinstance(champ, models.PositiveSmallIntegerField), (
            f"{nom} est un {type(champ).__name__} ; un axe est un entier de degrés"
        )

    assert len(set(decimales + entieres)) == 11


# ======================================================================================
# CLIENT-04 / CLIENT-05 — le prescripteur, la date, et la source
# ======================================================================================
def test_client04_prescripteur_et_date_de_prescription_sont_enregistres(
    db_all, deux_magasins
):
    """La date de prescription est une **colonne**, distincte de la date de saisie.

    Les deux diffèrent normalement : l'ordonnance est datée du jour de la consultation et
    saisie au comptoir des jours plus tard. Déduire l'une de l'autre daterait la
    prescription du jour de la frappe, ce qui fausse le calcul de validité (trois ans,
    ou un an chez l'enfant) que la phase 10 fera.
    """
    from tests.factories import FicheClientFactory

    fiche = FicheClientFactory()
    magasin = deux_magasins[0]

    ordonnance = _ordonnance_valide(
        fiche,
        magasin,
        prescripteur="Dr Bennani",
        date_prescription="2026-03-14",
    )
    ordonnance.save()
    ordonnance.refresh_from_db()

    assert ordonnance.prescripteur == "Dr Bennani"
    assert str(ordonnance.date_prescription) == "2026-03-14"
    assert ordonnance.created_at.date() != ordonnance.date_prescription, (
        "la date de prescription doit être indépendante de la date de saisie"
    )


def test_client05_la_source_est_medicale_ou_opticien(db_all, deux_magasins):
    """La source est une valeur, sans défaut, et le prescripteur la suit — **en base**.

    `prescripteur` est exigé **si et seulement si** `source = ordonnance_medicale`. Les
    deux moitiés comptent : un prescripteur posé sur une réfraction d'opticien affirme
    qu'un médecin a prescrit ce qui a été mesuré au comptoir — et c'est exactement ce que
    CLIENT-05 existe pour distinguer.

    **Ce qu'il attrape :** la règle écrite dans le seul sérialiseur. Un import de
    reprise, un `RunPython` ou le shell poseraient alors une ordonnance médicale sans
    médecin, et rien ne le dirait.
    """
    from domaine.ordonnances.models import Ordonnance, SourceOrdonnance

    from tests.factories import FicheClientFactory

    fiche = FicheClientFactory()
    magasin = deux_magasins[0]

    assert Ordonnance._meta.get_field("source").has_default() is False, (
        "une source par défaut choisirait à la place de l'opticien ; CLIENT-05 veut la "
        "distinction saisie, pas devinée"
    )

    _inserer(
        [
            _ordonnance_valide(
                fiche,
                magasin,
                version=1,
                source=SourceOrdonnance.MEDICALE,
                prescripteur="Dr Bennani",
            ),
            _ordonnance_valide(
                fiche,
                magasin,
                version=2,
                source=SourceOrdonnance.REFRACTION,
                prescripteur="",
            ),
        ]
    )
    assert Ordonnance.objects.count() == 2

    _refus(
        [
            _ordonnance_valide(
                fiche,
                magasin,
                version=3,
                source=SourceOrdonnance.MEDICALE,
                prescripteur="",
            )
        ]
    )
    _refus(
        [
            _ordonnance_valide(
                fiche,
                magasin,
                version=4,
                source=SourceOrdonnance.REFRACTION,
                prescripteur="Dr Bennani",
            )
        ]
    )


# ======================================================================================
# CLIENT-07 — ce que la base refuse, et que le sérialiseur seul ne refuserait pas
# ======================================================================================
def test_client07_une_valeur_hors_bornes_est_refusee_par_la_base_pas_seulement_par_le_serialiseur(
    db_all, deux_magasins
):
    """Le test qui compte le plus de ce fichier : la borne est une **contrainte de base**.

    `bulk_create` contourne `save()` et `clean()` — comme `queryset.update()`, comme un
    `RunPython` de migration, comme le shell. Une borne qui ne vit que dans le
    sérialiseur laisse donc entrer `-40,00` de sphère par quatre chemins, et la seule
    trace en sera une paire de verres impossible commandée chez le verrier.

    Le pas est vérifié dans le même test parce qu'il est la même famille : `-0,17` est
    **dans** la borne et n'existe sur aucune ordonnance.
    """
    from domaine.ordonnances.models import Ordonnance

    from tests.factories import FicheClientFactory

    fiche = FicheClientFactory()
    magasin = deux_magasins[0]

    _refus([_ordonnance_valide(fiche, magasin, version=1, sphere_od=Decimal("-40.00"))])
    _refus([_ordonnance_valide(fiche, magasin, version=2, addition_od=Decimal("0.50"))])
    _refus([_ordonnance_valide(fiche, magasin, version=3, sphere_od=Decimal("-0.17"))])
    _refus(
        [
            _ordonnance_valide(
                fiche, magasin, version=4, cylindre_od=Decimal("-1.00"), axe_od=400
            )
        ]
    )
    _refus([_ordonnance_valide(fiche, magasin, version=5, ep_binoculaire=Decimal("6.0"))])

    assert Ordonnance.objects.count() == 0, (
        "aucune des cinq lignes fautives ne doit être entrée en base"
    )

    _inserer([_ordonnance_valide(fiche, magasin, version=6, sphere_od=Decimal("-20.00"))])
    assert Ordonnance.objects.count() == 1, (
        "la borne inférieure exacte est une valeur légitime, pas un refus"
    )


def test_client07_un_cylindre_positif_est_refuse_au_stockage(db_all, deux_magasins):
    """Une seule convention est stockée : le cylindre négatif.

    La même correction s'écrit `+2,00 −1,00 × 90` ou `+1,00 +1,00 × 180`. Les deux
    conventions ne sont pas interchangeables, et accepter les deux sans le dire produit
    des verres faux (`04-CONTEXT.md` zone grise 1, menace T-04-21). La forme positive
    existe — l'opticien et le verrier y travaillent — mais elle est **calculée** par
    `snapshot_pour_fournisseur`, jamais rangée dans une seconde colonne, qui serait une
    seconde source de vérité.
    """
    from domaine.ordonnances.models import Ordonnance

    from tests.factories import FicheClientFactory

    fiche = FicheClientFactory()
    magasin = deux_magasins[0]

    _refus(
        [
            _ordonnance_valide(
                fiche, magasin, version=1, cylindre_od=Decimal("1.00"), axe_od=90
            )
        ]
    )

    _inserer(
        [
            _ordonnance_valide(
                fiche, magasin, version=2, cylindre_od=Decimal("-1.00"), axe_od=90
            )
        ]
    )
    assert Ordonnance.objects.get().cylindre_od == Decimal("-1.00")


CAS_AXE_ET_CYLINDRE = [
    ("cylindre-et-axe", Decimal("-1.25"), 45, True),
    ("cylindre-sans-axe", Decimal("-1.25"), None, False),
    ("axe-sans-cylindre", None, 45, False),
    ("ni-l-un-ni-l-autre", None, None, True),
]


@pytest.mark.parametrize(
    ("etiquette", "cylindre", "axe", "accepte"),
    CAS_AXE_ET_CYLINDRE,
    ids=[cas[0] for cas in CAS_AXE_ET_CYLINDRE],
)
def test_client07_l_axe_est_exige_si_et_seulement_si_le_cylindre_est_non_nul(
    db_all, deux_magasins, etiquette, cylindre, axe, accepte
):
    """Une contrainte **croisée**, qu'aucun intervalle n'attrape, aux quatre cas.

    Un axe sans cylindre ne veut rien dire ; un cylindre sans axe n'est pas commandable.
    C'est une classe d'erreur entière, et elle n'était dans **aucun** des trois jeux de
    bornes que le projet a discutés — précisément parce qu'on la cherche en pensant
    « intervalle » plutôt que « paire ».
    """
    from domaine.ordonnances.models import Ordonnance

    from tests.factories import FicheClientFactory

    fiche = FicheClientFactory()
    magasin = deux_magasins[0]
    ligne = _ordonnance_valide(fiche, magasin, cylindre_od=cylindre, axe_od=axe)

    if accepte:
        _inserer([ligne])
        assert Ordonnance.objects.count() == 1, f"{etiquette} est une saisie légitime"
    else:
        _refus([ligne])
        assert Ordonnance.objects.count() == 0, f"{etiquette} doit être refusé par la base"


def test_client07_un_cylindre_de_zero_est_stocke_null_et_l_axe_avec(db_all, deux_magasins):
    """« Pas d'astigmatisme » et « astigmatisme de zéro dioptrie » sont un seul fait.

    Deux encodages d'un même fait rendent deux fiches incomparables : une recherche de
    « les clients sans astigmatisme » en manquerait la moitié, et la comparaison entre
    deux versions signalerait un changement là où rien n'a changé.

    Les deux moitiés sont tenues séparément, et c'est délibéré : `save()` canonicalise
    (le chemin normal), la contrainte refuse (le chemin `bulk_create`). La première seule
    serait contournée ; la seconde seule refuserait une saisie légitime au comptoir.
    """
    from domaine.ordonnances.models import Ordonnance

    from tests.factories import FicheClientFactory

    fiche = FicheClientFactory()
    magasin = deux_magasins[0]

    ordonnance = _ordonnance_valide(
        fiche, magasin, version=1, cylindre_od=Decimal("0.00"), axe_od=0
    )
    ordonnance.save()
    ordonnance.refresh_from_db()

    assert ordonnance.cylindre_od is None, "un cylindre de zéro se range NULL"
    assert ordonnance.axe_od is None, "l'axe d'un cylindre nul part avec lui"

    # **Avec l'axe posé**, et c'est ce qui rend l'assertion utile : un cylindre de zéro
    # sans axe est déjà refusé par la contrainte croisée, donc la version sans axe
    # laisserait `ordonnance_cylindre_od_non_nul_ou_absent` entièrement non éprouvée —
    # verte sans jamais avoir été consultée. Mesuré : c'est bien elle qui refuse ici.
    _refus(
        [
            _ordonnance_valide(
                fiche, magasin, version=2, cylindre_od=Decimal("0.00"), axe_od=90
            )
        ]
    )
    assert Ordonnance.objects.count() == 1


def test_client07_l_axe_zero_saisi_est_canonicalise_en_180(db_all, deux_magasins):
    """CLIENT-07 dit « 0–180 » : on **accepte** 0 et on stocke 180.

    L'exigence est servie à la lettre — la saisie admet 0 — et le stockage est plus
    strict que son énoncé, parce que 0 et 180 sont le même méridien et que deux encodages
    d'un même axe produisent deux fiches qui ne se comparent pas (menace T-04-23).
    """
    from tests.factories import FicheClientFactory

    fiche = FicheClientFactory()
    ordonnance = _ordonnance_valide(
        fiche, deux_magasins[0], cylindre_od=Decimal("-0.75"), axe_od=0
    )
    ordonnance.save()
    ordonnance.refresh_from_db()

    assert ordonnance.axe_od == 180


# ======================================================================================
# CLIENT-07 — l'écart pupillaire : enregistré, jamais déduit
# ======================================================================================
def _nomme_un_ep(noeud) -> bool:
    """Vrai si le sous-arbre nomme un identifiant `ep_…` — attribut ou variable."""
    for sous in ast.walk(noeud):
        nom = getattr(sous, "attr", None) or getattr(sous, "id", None)
        if isinstance(nom, str) and nom.startswith("ep_"):
            return True
    return False


def _vaut(noeud, valeurs: set[Decimal]) -> bool:
    """Vrai si le nœud est un littéral numérique — nu ou dans `Decimal("…")` — attendu."""
    if isinstance(noeud, ast.Call):
        nom = getattr(noeud.func, "attr", None) or getattr(noeud.func, "id", None)
        if nom == "Decimal" and noeud.args:
            return _vaut(noeud.args[0], valeurs)
        return False
    if isinstance(noeud, ast.Constant) and not isinstance(noeud.value, bool):
        try:
            return Decimal(str(noeud.value)) in valeurs
        except Exception:  # noqa: BLE001 — une chaîne non numérique n'est pas un nombre
            return False
    return False


def derivations_d_ecart_pupillaire(source: str) -> list[str]:
    """Les endroits où un `ep_…` est divisé par deux, ou multiplié par un demi."""
    fautes = []
    for noeud in ast.walk(ast.parse(source)):
        if not isinstance(noeud, ast.BinOp):
            continue
        deux = {Decimal("2")}
        demi = {Decimal("0.5")}
        if isinstance(noeud.op, ast.Div | ast.FloorDiv):
            if _nomme_un_ep(noeud.left) and _vaut(noeud.right, deux):
                fautes.append(f"ligne {noeud.lineno} : division d'un ep_ par deux")
        elif isinstance(noeud.op, ast.Mult) and (
            (_nomme_un_ep(noeud.left) and _vaut(noeud.right, demi))
            or (_nomme_un_ep(noeud.right) and _vaut(noeud.left, demi))
        ):
            fautes.append(f"ligne {noeud.lineno} : moitié d'un ep_")
    return fautes


def _sources_du_depot() -> list[tuple[str, str]]:
    """Chaque module applicatif, en (chemin relatif, source)."""
    lus = []
    for arbre in ARBRES_SCANNES:
        for chemin in sorted((RACINE / arbre).rglob("*.py")):
            lus.append(
                (str(chemin.relative_to(RACINE)), chemin.read_text(encoding="utf-8"))
            )
    return lus


def test_client07_l_ecart_pupillaire_saisi_est_stocke_jamais_deduit(db_all, deux_magasins):
    """`ep_saisi` est une **colonne**, et rien ne calcule un monoculaire.

    `NULL` est ambigu entre « non mesuré » et « sans objet », donc déduire la forme
    saisie de la nullité des colonnes est une lecture d'intention dans une absence. La
    règle, écrite une fois pour toutes (`04-RESEARCH.md` §6.5) : **on enregistre ce qui a
    été saisi ; la somme binoculaire s'affiche comme contrôle quand les deux monoculaires
    existent ; on ne calcule jamais un monoculaire.** Découper un binoculaire en deux
    suppose la symétrie à laquelle les progressifs sont précisément sensibles — et un
    verre progressif décentré de deux millimètres est un verre à refaire.

    La seconde moitié est une garde de source par AST, parce que le chemin fautif ne
    s'exécute jamais dans la suite : personne n'écrit un test pour la commodité qu'il
    vient d'ajouter.
    """
    from django.db import models

    from domaine.ordonnances.models import Ordonnance

    champ = Ordonnance._meta.get_field("ep_saisi")
    assert isinstance(champ, models.CharField)
    assert champ.choices, "ep_saisi doit énumérer ce qui a été saisi, pas se deviner"

    fautes = {
        chemin: trouvees
        for chemin, source in _sources_du_depot()
        if (trouvees := derivations_d_ecart_pupillaire(source))
    }
    assert not fautes, (
        "Un écart pupillaire monoculaire est calculé depuis un binoculaire :\n"
        + "\n".join(f"  {chemin} :: {', '.join(l)}" for chemin, l in fautes.items())
    )


MOITIE_PAR_DIVISION = textwrap.dedent(
    """
    def monoculaire(ordonnance):
        return ordonnance.ep_binoculaire / 2
    """
)

MOITIE_PAR_MULTIPLICATION = textwrap.dedent(
    """
    from decimal import Decimal

    def monoculaire(ep_binoculaire):
        return ep_binoculaire * Decimal("0.5")
    """
)

SOMME_DES_MONOCULAIRES = textwrap.dedent(
    """
    def controle(ordonnance):
        return ordonnance.ep_mono_od + ordonnance.ep_mono_og
    """
)


@pytest.mark.parametrize(
    ("etiquette", "source", "fautif"),
    [
        ("moitie-par-division", MOITIE_PAR_DIVISION, True),
        ("moitie-par-multiplication", MOITIE_PAR_MULTIPLICATION, True),
        ("somme-des-monoculaires", SOMME_DES_MONOCULAIRES, False),
    ],
    ids=["moitie-par-division", "moitie-par-multiplication", "somme-des-monoculaires"],
)
def test_client07_la_garde_de_l_ecart_pupillaire_est_prouvee_sur_des_modules_synthetiques(
    etiquette, source, fautif
):
    """Le troisième cas est le contrôle : la **somme** des monoculaires est autorisée.

    Elle est même la forme correcte — elle s'affiche comme contrôle. Une garde qui
    refuserait toute arithmétique sur un `ep_` interdirait la seule opération légitime.
    """
    fautes = derivations_d_ecart_pupillaire(source)

    if fautif:
        assert fautes, f"{etiquette} : la garde a laissé passer une dérivation"
    else:
        assert not fautes, f"{etiquette} : faux positif — {fautes}"


# ======================================================================================
# D-4a — l'ordonnance est à l'échelle du CLIENT, jamais du magasin
# ======================================================================================
def test_client07_une_ordonnance_n_est_pas_scopee_au_magasin(db_all, deux_magasins):
    """La garde **positive** de D-4a. Sans elle, rien ne tient cette décision.

    `plateforme/projection/checks.py::vues_sans_portee_magasin` saute tout modèle
    n'héritant pas de `MagasinScopedModel` — il est donc structurellement aveugle à
    celui-ci, dans un sens comme dans l'autre. Un relecteur de la phase 7 qui ferait
    hériter `Ordonnance` du mixin allumerait le filtrage, le garde exigerait alors le
    mixin de vue, il l'ajouterait, tout serait vert, et le danger clinique serait revenu
    sans qu'une seule ligne rougisse (menace T-04-22).

    L'assertion jumelle est aussi importante que la première : le magasin **existe** en
    colonne. Sans elle, une implémentation qui aurait simplement omis le magasin serait
    verte — et la provenance d'une donnée de santé serait perdue.
    """
    from domaine.magasins.models import MagasinScopedModel
    from domaine.ordonnances.models import Ordonnance

    assert not issubclass(Ordonnance, MagasinScopedModel), (
        "Scoper l'ordonnance au magasin produit le danger que D-4a nomme : un gérant de "
        "Maârif qui ne voit pas l'ordonnance saisie à Anfa en saisit une seconde, et le "
        "client se retrouve avec deux historiques divergents pour un seul œil. Le "
        "magasin est porté pour la provenance, jamais pour filtrer."
    )

    magasin = Ordonnance._meta.get_field("magasin")
    assert magasin.is_relation, (
        "la colonne de provenance a disparu : sans elle, on ne sait plus quel comptoir a "
        "saisi une donnée de santé, et les rappels de la phase 10 n'ont plus d'émetteur"
    )
    assert magasin.remote_field.on_delete.__name__ == "PROTECT"

    from tests.factories import FicheClientFactory

    fiche = FicheClientFactory()
    anfa, maarif = deux_magasins
    _inserer(
        [
            _ordonnance_valide(fiche, anfa, version=1),
            _ordonnance_valide(fiche, maarif, version=2),
        ]
    )

    assert fiche.ordonnances.count() == 2, (
        "les deux ordonnances d'une même personne se lisent ensemble, quel que soit le "
        "comptoir qui les a saisies"
    )


# ======================================================================================
# CLIENT-08 — la moitié que la phase 4 possède
# ======================================================================================
def test_client08_le_snapshot_fournisseur_est_une_copie_figee_en_cylindre_positif(
    db_all, deux_magasins
):
    """Une **copie**, en plus-cyl, que la correction suivante ne réécrit pas.

    `.planning/research/ARCHITECTURE.md:290` a déjà tranché le point difficile : la
    prescription est copiée (figée), pas référencée, sur la ligne de commande
    fournisseur — sinon une correction saisie après l'envoi changerait silencieusement ce
    qui a été commandé, et personne ne saurait quelle paire arrive.

    **Ce que ce test ne prouve pas, et qui n'est pas cochable ici :** CLIENT-08 veut que
    la commande spéciale porte ces valeurs *jusqu'au fournisseur*. Le bon de commande est
    la phase 8 et la table de commande spéciale la phase 5 (STOCK-08). La phase 4 livre
    le producteur de la copie, et rien de plus.
    """
    from domaine.ordonnances.optique import snapshot_pour_fournisseur

    from tests.factories import FicheClientFactory

    fiche = FicheClientFactory()
    ordonnance = _ordonnance_valide(
        fiche,
        deux_magasins[0],
        sphere_od=Decimal("1.50"),
        cylindre_od=Decimal("-0.50"),
        axe_od=20,
        sphere_og=Decimal("2.00"),
        cylindre_og=None,
        axe_og=None,
    )
    ordonnance.save()

    snapshot = snapshot_pour_fournisseur(ordonnance)

    assert snapshot["convention"] == "cylindre_positif", (
        "la convention voyage avec les valeurs ; un verrier qui reçoit trois nombres sans "
        "convention monte l'autre correction"
    )
    assert snapshot["od"] == {
        "sphere": Decimal("1.00"),
        "cylindre": Decimal("0.50"),
        "axe": 110,
        "addition": None,
    }
    assert snapshot["og"]["sphere"] == Decimal("2.00")
    assert snapshot["og"]["cylindre"] is None
    assert snapshot["og"]["axe"] is None

    ordonnance.sphere_od = Decimal("-5.00")
    ordonnance.save()

    assert snapshot["od"]["sphere"] == Decimal("1.00"), (
        "le snapshot a suivi une correction postérieure : c'est une référence, pas une "
        "copie, et le verrier recevrait une correction que personne n'a commandée"
    )


def test_client08_aucune_table_de_commande_speciale_n_est_creee():
    """La phase 4 ne pose **pas** la table que la phase 5 possède.

    `04-RESEARCH.md` §3.4 et la zone grise 2 en proposaient une. La feuille de route donne
    le suivi de la commande spéciale — `commandé → prêt → client prévenu → livré` — à
    STOCK-08, phase 5. La créer ici préempterait ce cycle de vie, et la phase 5 aurait
    à migrer une table qu'elle n'a pas dessinée.

    La garde lit les **définitions de classe** de l'application, pas son texte : la
    docstring d'`optique.py` explique justement pourquoi cette table n'est pas là, et un
    `grep` du nom attraperait cette explication (CLAUDE.md, section Testing).
    """
    paquet = RACINE / "domaine" / "ordonnances"
    fichiers = sorted(paquet.rglob("*.py"))

    assert fichiers, "l'application ordonnances n'existe pas"

    definies = {
        noeud.name
        for chemin in fichiers
        for noeud in ast.walk(ast.parse(chemin.read_text(encoding="utf-8")))
        if isinstance(noeud, ast.ClassDef)
    }

    assert "CommandeSpeciale" not in definies, (
        "la commande spéciale et son statut appartiennent à STOCK-08, phase 5 ; "
        f"classes définies ici : {sorted(definies)}"
    )


# ======================================================================================
# CLIENT-06 — une nouvelle version, et aucune route qui réécrive la précédente
# ======================================================================================
#
# **Pourquoi ces tests passent par l'API et non par le service seul.** CLIENT-06 promet
# deux choses à un opticien, pas à un appelant Python : que la correction d'une erreur
# crée une version, et qu'aucun bouton ne réécrit l'ancienne. La seconde moitié n'est
# vérifiable que sur la **surface** — un service parfaitement immuable derrière une vue
# qui expose `partial_update` ne tient rien du tout.

#: Les routes imbriquées, écrites une fois. Un test qui recopie une URL reste vert le
#: jour où la route déménage : il vérifie alors une 404 bien formée.
ORDONNANCES = "/api/clients/{client}/ordonnances/"
ORDONNANCE = "/api/clients/{client}/ordonnances/{pk}/"


def _proprietaire():
    from plateforme.comptes.acces import acces_pour
    from tests.factories import ProprietaireFactory

    compte = ProprietaireFactory()
    return compte, acces_pour(compte)


def _gerant_avec(magasins, codes):
    """Un gérant ayant accès aux `magasins` et y détenant `codes`, dans **tous**.

    `Acces.peut(code)` sans argument magasin est une conjonction (plan 03-05) : un droit
    accordé dans un seul des deux magasins n'autorise rien, et un helper qui n'en servirait
    qu'un produirait des 403 inexplicables dans un fichier qui ne parle pas de portée.
    """
    from plateforme.comptes.acces import acces_pour
    from tests.factories import AccesMagasinFactory, DroitAccordeFactory, GerantFactory

    compte = GerantFactory()
    for magasin in magasins:
        AccesMagasinFactory(utilisateur=compte, magasin_code=magasin.code)
        for code in codes:
            DroitAccordeFactory(utilisateur=compte, magasin_code=magasin.code, code=code)
    return compte, acces_pour(compte)


def _appeler_ordonnances(utilisateur, methode, actions, chemin, **kwargs):
    """Une vraie requête : principal -> `AccesMiddleware` -> `VueOrdonnances` -> JSON rendu.

    `actions` est le dictionnaire passé à `as_view`, donc **ce que la route monte** — et
    non ce que la requête demande. C'est délibéré : le test des 405 envoie un `PATCH` à la
    route de détail telle qu'elle est réellement montée, ce qui est la seule façon de
    distinguer « la vue ne sert pas ce verbe » de « ce test a monté une vue sur mesure ».
    """
    from rest_framework.test import APIRequestFactory, force_authenticate

    from domaine.ordonnances.vues import VueOrdonnances
    from plateforme.comptes.middleware import AccesMiddleware

    vue = VueOrdonnances.as_view(actions)
    fabrique = APIRequestFactory()
    corps = kwargs.pop("corps", None)
    requete = getattr(fabrique, methode)(
        chemin, *( (corps,) if corps is not None else () ),
        **({"format": "json"} if corps is not None else {}),
    )
    requete.user = utilisateur
    force_authenticate(requete, user=utilisateur)
    reponse = AccesMiddleware(lambda recue: vue(recue, **kwargs))(requete)
    reponse.render()
    return reponse


def _corps_de_saisie(magasin, **surcharges):
    """Le corps minimal d'une saisie valide, surchargeable.

    Les valeurs sont écrites en **chaînes**, comme le SPA les enverra : JSON n'a pas de
    type décimal, et un flottant dans ce corps reproduirait la trappe que
    `tests/test_optique.py` interdit déjà côté serveur.
    """
    charge = {
        "magasin": magasin.pk,
        "source": "ordonnance_medicale",
        "prescripteur": "Dr Bennani",
        "date_prescription": "2026-03-14",
        "sphere_od": "-1.00",
        "sphere_og": "-1.25",
        "ep_binoculaire": "62.0",
        "ep_saisi": "binoculaire",
    }
    charge.update(surcharges)
    return charge


def _saisir(utilisateur, fiche, magasin, **surcharges):
    return _appeler_ordonnances(
        utilisateur,
        "post",
        {"post": "create"},
        ORDONNANCES.format(client=fiche.pk),
        client_id=fiche.pk,
        corps=_corps_de_saisie(magasin, **surcharges),
    )


def test_client06_une_nouvelle_version_ne_modifie_jamais_la_precedente(
    db_all, deux_magasins
):
    """La version 1 est **identique champ par champ** après l'arrivée de la version 2.

    L'assertion porte sur `model_to_dict` **entier**, et c'est le point. Trois assertions
    sur trois colonnes seraient vertes au-dessus d'une implémentation qui écraserait la
    quatrième — et la colonne écrasée serait celle que personne n'a pensé à nommer, ce qui
    est la définition du champ qu'on oublie. `created_at` est relevé séparément parce que
    `model_to_dict` saute les champs non éditables, donc l'horodatage de saisie — qui est
    précisément ce qu'une réécriture déplacerait — n'y figure pas.

    **Ce qu'il attrape :** l'implémentation qui « met à jour » la dernière ordonnance au
    lieu d'en insérer une nouvelle, c'est-à-dire la forme naturelle si l'on pense
    « corriger une fiche » plutôt que « verser une pièce au dossier ».
    """
    from django.forms.models import model_to_dict

    from domaine.ordonnances.models import Ordonnance
    from tests.factories import FicheClientFactory

    fiche = FicheClientFactory()
    anfa, maarif = deux_magasins
    proprietaire, _ = _proprietaire()

    premiere = _saisir(proprietaire, fiche, anfa, sphere_od="-1.00")
    assert premiere.status_code == 201, premiere.data
    assert premiere.data["version"] == 1

    v1 = Ordonnance.objects.get(pk=premiere.data["id"])
    avant = model_to_dict(v1)
    horodatage_avant = v1.created_at

    seconde = _saisir(
        proprietaire,
        fiche,
        maarif,
        sphere_od="-2.75",
        sphere_og="-3.00",
        prescripteur="Dr Tazi",
        date_prescription="2026-06-01",
    )
    assert seconde.status_code == 201, seconde.data
    assert seconde.data["version"] == 2, (
        "La seconde saisie n'a pas produit la version 2 : soit elle a réécrit la "
        "première, soit la numérotation ne part pas du maximum existant."
    )

    v1_relue = Ordonnance.objects.get(pk=v1.pk)
    assert model_to_dict(v1_relue) == avant, (
        "La version 1 a changé. CLIENT-06 promet qu'une version précédente reste "
        "lisible **exactement telle qu'elle a été saisie** ; une seule colonne réécrite "
        "suffit à faire de l'historique une suggestion.\n"
        f"  avant : {avant}\n  après : {model_to_dict(v1_relue)}"
    )
    assert v1_relue.created_at == horodatage_avant

    assert Ordonnance.objects.filter(client=fiche).count() == 2


def test_client06_aucune_route_ne_modifie_une_ordonnance(db_all, deux_magasins):
    """**Deux moitiés, et il faut les deux.** Le MRO, puis deux vraies requêtes en 405.

    L'introspection seule laisserait passer une route montée à la main qui appellerait un
    service d'écriture ; les requêtes seules laisseraient passer l'ajout d'un mixin de
    modification à une vue dont personne n'a encore monté le verbe. Ensemble elles disent
    la chose entière : la surface ne porte pas d'écriture, et aucun chemin ne la sert.

    **405 et non 403, et la différence est toute la garantie.** Un 403 voudrait dire que
    la route existe et qu'un droit la garde — donc qu'il suffit d'accorder ce droit, ou
    de se tromper dans une classe de permission, pour que l'historique redevienne
    réécrivable. Les requêtes sont donc jouées par le **propriétaire**, qui détient tout :
    s'il obtient 405, aucun titulaire de droit n'obtiendra autre chose.

    **Ce qu'il attrape :** l'ajout d'un mixin de modification six phases plus tard, « pour
    corriger une faute de frappe ».
    """
    from rest_framework import mixins

    from domaine.ordonnances.models import Ordonnance
    from plateforme.projection.checks import _modele_de_la_vue, toutes_les_vues
    from tests.factories import FicheClientFactory

    interdits = (mixins.UpdateModelMixin, mixins.DestroyModelMixin)
    verbes_interdits = {"put", "patch", "delete"}

    servant_lordonnance = [
        vue for vue in toutes_les_vues() if _modele_de_la_vue(vue) is Ordonnance
    ]
    assert servant_lordonnance, (
        "Aucune vue chargée ne sert `Ordonnance`. Le test est vacant : il passerait tout "
        "aussi bien le jour où quelqu'un en ajoute une avec un mixin de modification."
    )

    for vue in servant_lordonnance:
        etiquette = f"{vue.__module__}.{vue.__qualname__}"
        presents = [base.__name__ for base in interdits if base in vue.__mro__]
        assert not presents, (
            f"{etiquette} hérite de {presents}. Une ordonnance ne se corrige pas : elle "
            "est remplacée par une nouvelle version dont `supersede` désigne l'ancienne."
        )
        servis = verbes_interdits & set(vue.http_method_names)
        assert not servis, (
            f"{etiquette} déclare {sorted(servis)} dans `http_method_names`. Le second "
            "verrou existe parce que le premier se retire par un ajout de base distrait, "
            "et celui-ci se voit en diff."
        )

    fiche = FicheClientFactory()
    proprietaire, acces = _proprietaire()
    from plateforme.comptes.permissions_catalogue import Permission

    assert acces.peut(Permission.ORDONNANCE_SAISIR) is True, (
        "L'appelant du test n'a pas le droit d'écrire : un 403 serait alors le verdict, "
        "et ce test dirait « un droit manque » là où il doit dire « la route n'existe "
        "pas »."
    )

    creation = _saisir(proprietaire, fiche, deux_magasins[0])
    assert creation.status_code == 201, creation.data
    identifiant = creation.data["id"]

    chemin = ORDONNANCE.format(client=fiche.pk, pk=identifiant)
    for methode in ("patch", "delete"):
        reponse = _appeler_ordonnances(
            proprietaire,
            methode,
            {"get": "retrieve"},
            chemin,
            client_id=fiche.pk,
            pk=identifiant,
            **({"corps": {"sphere_od": "-9.00"}} if methode == "patch" else {}),
        )
        assert reponse.status_code == 405, (
            f"{methode.upper()} a répondu {reponse.status_code} : {reponse.data}. "
            "Attendu **405**. Un 403 dirait que la route existe et qu'un droit la garde, "
            "ce qui est une garantie strictement plus faible — elle tombe avec une "
            "classe de permission mal écrite."
        )


def test_client06_une_version_proposee_par_le_client_est_ignoree(db_all, deux_magasins):
    """T-04-31 — `version` n'est pas dans le sérialiseur d'écriture, donc elle est ignorée.

    **L'assertion est « ignorée », pas « refusée », et ce n'est pas de la mollesse.** DRF
    ne lève sur aucune clé inconnue d'un corps de requête : un test qui attendrait 400
    serait rouge au-dessus d'un code parfaitement correct, après quoi quelqu'un le
    « réparerait » en rendant le champ inscriptible — ce qui est exactement la menace.
    C'est le même raisonnement que
    `test_perm06_un_champ_protege_ne_peut_pas_etre_ecrit_par_un_gerant`.

    Ce test vit dans la porte **rapide**, séparé du test de concurrence qui est `slow` :
    la propriété qu'il tient — le client ne choisit pas le numéro — n'a aucun besoin de
    deux fils, et l'enterrer dans un test lent la retirerait de la boucle courte.
    """
    from tests.factories import FicheClientFactory

    fiche = FicheClientFactory()
    proprietaire, _ = _proprietaire()

    reponse = _saisir(proprietaire, fiche, deux_magasins[0], version=999)
    assert reponse.status_code == 201, reponse.data
    assert reponse.data["version"] == 1, (
        "Le numéro proposé par le client a été obéi. Le serveur émet la version sous "
        "verrou ; un client qui la choisit peut écraser une version existante ou en "
        "réserver une à l'avance."
    )

    seconde = _saisir(proprietaire, fiche, deux_magasins[0], version=1)
    assert seconde.status_code == 201, seconde.data
    assert seconde.data["version"] == 2


def test_client06_une_correction_exige_un_supersede_du_meme_client(db_all, deux_magasins):
    """Une `correction` nomme ce qu'elle remplace, et ne peut pas désigner un autre dossier.

    Deux règles, et la seconde est une IDOR qu'aucune contrainte de base n'attrape :
    `supersede` est une clé étrangère vers `Ordonnance`, donc la base accepte parfaitement
    qu'une correction du dossier A pointe vers une version du dossier B. Le résultat
    serait un historique dans lequel « remplace la version 2 » ouvre la fiche de quelqu'un
    d'autre — une divulgation de donnée de santé, pas une incohérence d'affichage.

    Un `renouvellement`, lui, n'exige ni `supersede` ni motif : c'est une ordonnance neuve,
    pas la correction d'une faute.
    """
    from tests.factories import FicheClientFactory

    anfa = deux_magasins[0]
    proprietaire, _ = _proprietaire()

    fiche = FicheClientFactory()
    autre = FicheClientFactory()

    premiere = _saisir(proprietaire, fiche, anfa)
    assert premiere.status_code == 201, premiere.data
    chez_lautre = _saisir(proprietaire, autre, anfa)
    assert chez_lautre.status_code == 201, chez_lautre.data

    sans_motif = _saisir(
        proprietaire,
        fiche,
        anfa,
        type_revision="correction",
        supersede=premiere.data["id"],
    )
    assert sans_motif.status_code == 400, sans_motif.data

    sans_supersede = _saisir(
        proprietaire,
        fiche,
        anfa,
        type_revision="correction",
        motif_revision="axe OD saisi 90 au lieu de 9",
    )
    assert sans_supersede.status_code == 400, sans_supersede.data

    dun_autre_dossier = _saisir(
        proprietaire,
        fiche,
        anfa,
        type_revision="correction",
        motif_revision="axe OD saisi 90 au lieu de 9",
        supersede=chez_lautre.data["id"],
    )
    assert dun_autre_dossier.status_code == 400, (
        "Une correction a pu désigner l'ordonnance d'un autre client. L'historique de "
        "cette fiche renverrait alors vers le dossier de quelqu'un d'autre."
    )

    # Le contrôle positif : la même correction, bien formée, est acceptée.
    correcte = _saisir(
        proprietaire,
        fiche,
        anfa,
        type_revision="correction",
        motif_revision="axe OD saisi 90 au lieu de 9",
        supersede=premiere.data["id"],
    )
    assert correcte.status_code == 201, correcte.data
    assert correcte.data["supersede"] == premiere.data["id"]

    # Et un renouvellement n'exige rien de tout cela.
    renouvellement = _saisir(proprietaire, fiche, anfa, type_revision="renouvellement")
    assert renouvellement.status_code == 201, renouvellement.data
    assert renouvellement.data["supersede"] is None


def test_client06_une_version_stockee_ne_se_revalide_pas_a_la_lecture(
    db_all, deux_magasins, monkeypatch
):
    """`04-UI-SPEC.md` §21.2 — une règle qui bouge ne rend pas l'ancien fautif.

    Les bornes vivent à un seul endroit servi et **le propriétaire les a déjà changées une
    fois**. Une version portant une valeur que les bornes d'aujourd'hui refuseraient doit
    donc se rendre sans avertissement, sans badge d'erreur, sans annotation : faire
    paraître fausses toutes les fiches parce qu'un chiffre a bougé détruit exactement la
    garantie que CLIENT-06 achète.

    **Le resserrement est prouvé avant d'être invoqué.** Une valeur enregistrée, puis
    `BORNES` resserré, puis *la même saisie refusée en 400* — sans cette troisième étape,
    le test comparerait deux charges utiles identiques au-dessus d'un monkeypatch qui
    n'aurait rien changé, et serait vert pour toujours. C'est la leçon de la sonde du plan
    04-04 : une garantie qu'on n'a pas vue mordre n'est pas une garantie.

    **Ce qu'il attrape :** le sérialiseur de lecture qui réutiliserait les validateurs de
    celui d'écriture — l'erreur naturelle, et la seule qui casse toutes les fiches d'un
    coup.
    """
    from domaine.ordonnances import bornes
    from tests.factories import FicheClientFactory

    fiche = FicheClientFactory()
    proprietaire, _ = _proprietaire()
    anfa = deux_magasins[0]

    # Une sphère parfaitement légitime **aujourd'hui**, et hors des bornes de demain.
    saisie = _saisir(proprietaire, fiche, anfa, sphere_od="-12.00")
    assert saisie.status_code == 201, saisie.data
    identifiant = saisie.data["id"]

    chemin = ORDONNANCE.format(client=fiche.pk, pk=identifiant)

    def _lire():
        reponse = _appeler_ordonnances(
            proprietaire, "get", {"get": "retrieve"}, chemin,
            client_id=fiche.pk, pk=identifiant,
        )
        assert reponse.status_code == 200, reponse.data
        return reponse

    avant = _lire()

    resserre = dict(bornes.BORNES["sphere"])
    resserre["min"] = "-6.00"
    monkeypatch.setitem(bornes.BORNES, "sphere", resserre)

    # 1. Le resserrement mord réellement : la **même** saisie est maintenant refusée.
    refusee = _saisir(proprietaire, fiche, anfa, sphere_od="-12.00")
    assert refusee.status_code == 400, (
        "Le resserrement des bornes n'a rien changé à l'écriture. Le sérialiseur "
        "d'écriture ne lit donc pas `BORNES` à la validation, et la comparaison "
        "ci-dessous porterait sur deux lectures identiques pour une raison creuse."
    )

    # 2. Et pourtant la lecture est identique, octet pour octet.
    apres = _lire()
    assert apres.data == avant.data, (
        "La charge utile d'une version stockée a changé avec les bornes. Une ordonnance "
        "correctement saisie en 2026 se lirait comme fautive en 2027 parce que le "
        "propriétaire a bougé un chiffre."
    )
    assert apres.rendered_content == avant.rendered_content
    assert apres.data["sphere_od"] == "-12.00"

    # 3. Aucun champ d'avertissement, de drapeau ni d'annotation n'apparaît.
    suspects = [
        cle
        for cle in apres.data
        if any(mot in cle for mot in ("avert", "warning", "invalide", "erreur", "alerte"))
    ]
    assert not suspects, (
        f"La lecture porte {suspects}. `04-UI-SPEC.md` §21.2 : « une version enregistrée "
        "se rend telle qu'elle a été saisie ; l'affichage ne la revalide jamais. »"
    )


def test_client06_le_resume_de_la_fiche_ne_fait_pas_une_requete_par_ligne(
    db_all, deux_magasins, django_assert_max_num_queries
):
    """Le résumé est préchargé, pas rechargé par ligne. Une mesure, pas une intention.

    Le plan 04-05 exige que les deux champs soient alimentés « par une annotation ou un
    `prefetch_related` […] jamais par une requête par ligne : une liste de deux cents
    clients ne fait pas deux cents requêtes ». Une intention écrite dans une docstring
    n'est pas une garantie — un `SerializerMethodField` qui interroge la base est
    exactement ce qu'on écrit sans y penser, et rien ne le signale tant qu'on ne compte
    pas.

    Le seuil est un **plafond** et non un nombre exact : le compte réel dépend de ce que
    DRF, la pagination et le middleware font autour, et un test qui fixerait l'égalité
    rougirait au premier réglage sans rapport. Ce qui doit rester vrai est que le compte
    ne **croît pas avec le nombre de lignes**, et c'est ce que douze requêtes pour douze
    clients disent.
    """
    from decimal import Decimal

    from tests.factories import FicheClientFactory, OrdonnanceFactory

    anfa = deux_magasins[0]
    proprietaire, _ = _proprietaire()

    combien = 12
    for indice in range(combien):
        fiche = FicheClientFactory()
        OrdonnanceFactory(
            client=fiche,
            magasin=anfa,
            version=1,
            sphere_od=Decimal("-1.00"),
        )

    from rest_framework.test import APIRequestFactory, force_authenticate

    from domaine.clients.vues import VueClients
    from plateforme.comptes.middleware import AccesMiddleware

    vue = VueClients.as_view({"get": "list"})
    requete = APIRequestFactory().get("/api/clients/")
    requete.user = proprietaire
    force_authenticate(requete, user=proprietaire)

    from django.db import connections

    with django_assert_max_num_queries(combien // 2, connection=connections[ALIAS]):
        reponse = AccesMiddleware(lambda recue: vue(recue))(requete)
        reponse.render()

    assert reponse.status_code == 200, reponse.data
    assert len(reponse.data) >= combien
    assert sum(1 for ligne in reponse.data if ligne["derniere_ordonnance"]) == combien, (
        "Les résumés ne sont pas servis : un chemin qui ne rend rien ne fait aucune "
        "requête, donc le plafond ci-dessus serait tenu pour une raison creuse."
    )


@pytest.mark.slow
@pytest.mark.django_db(transaction=True, databases=("default", "tenant_a", "tenant_b"))
def test_client06_le_numero_de_version_est_emis_par_le_serveur_sous_verrou():
    """Deux comptoirs, une même fiche, au même instant : les versions sont `{1, 2}`.

    **Le `transaction=True` EST le test.** `TestCase` enveloppe chaque test dans une
    transaction sur la connexion du fil principal : `select_for_update()` n'entre alors
    jamais en contention, et une implémentation **sans aucun verrou** passerait toutes les
    assertions. C'est la trappe que CLAUDE.md nomme en toutes lettres et la raison pour
    laquelle ce test est `slow` — il écrit hors transaction et nettoie derrière lui.

    **C'est la même propriété que le numéro de facture de la phase 6** (CLAUDE.md #3), sur
    un enjeu plus faible : un trou dans les versions d'une ordonnance n'est pas une
    exposition fiscale. Le **mécanisme** est en revanche identique — une ligne verrouillée
    `FOR UPDATE` dans la transaction d'insertion, jamais une `SEQUENCE` Postgres, qui
    produit des trous au rollback. La phase 6 réutilise ce test comme modèle : deux fils
    réels, une barrière, et une assertion sur l'**ensemble** des numéros émis, parce qu'un
    doublon et un trou se lisent tous les deux dedans et ni l'un ni l'autre dans un
    compte.

    Les fixtures de locataire ne sont pas utilisées : `conftest.pytest_collection_modifyitems`
    repose un marqueur `django_db` sur tout test qui les demande, et ce marqueur
    **écraserait** le `transaction=True` ci-dessus — le test redeviendrait alors
    silencieusement enveloppé, c'est-à-dire vert et vide. Le contexte est donc lié à la
    main.
    """
    import threading

    from django.db import connections

    from domaine.magasins.models import Magasin
    from domaine.ordonnances.models import Ordonnance
    from domaine.ordonnances.services import enregistrer_ordonnance
    from plateforme.tenancy.context import tenant_context
    from tests.factories import FicheClientFactory

    with tenant_context(ALIAS):
        magasin = Magasin.objects.create(code="CONCUR", nom="Optique Concurrente")
        fiche = FicheClientFactory()

    barriere = threading.Barrier(2, timeout=10)
    resultats: dict[str, object] = {}
    erreurs: list[BaseException] = []

    def saisir(etiquette):
        try:
            with tenant_context(ALIAS):
                # Les deux fils se donnent rendez-vous **avant** d'ouvrir leur
                # transaction : sans la barrière, le premier commettrait souvent avant
                # que le second ne commence, et le verrou ne serait jamais sollicité.
                barriere.wait()
                ordonnance = enregistrer_ordonnance(
                    client=fiche,
                    magasin=magasin,
                    valeurs={
                        "source": "refraction_opticien",
                        "prescripteur": "",
                        "date_prescription": "2026-03-14",
                        "sphere_od": Decimal("-1.00"),
                        "ep_binoculaire": Decimal("62.0"),
                        "ep_saisi": "binoculaire",
                    },
                    par=f"{etiquette}@optique.test",
                )
                resultats[etiquette] = ordonnance.version
        except BaseException as erreur:  # noqa: BLE001 — remonté tel quel ci-dessous
            erreurs.append(erreur)
        finally:
            connections.close_all()

    fils = [
        threading.Thread(target=saisir, args=(etiquette,), name=f"comptoir-{etiquette}")
        for etiquette in ("anfa", "maarif")
    ]
    try:
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join(timeout=30)

        assert not erreurs, f"Un fil a levé : {erreurs!r}"
        assert not [fil for fil in fils if fil.is_alive()], (
            "Un fil ne s'est pas terminé : les deux transactions se sont mutuellement "
            "bloquées, ce qui est un interblocage, pas une sérialisation."
        )

        with tenant_context(ALIAS):
            versions = sorted(
                Ordonnance.objects.filter(client=fiche).values_list("version", flat=True)
            )
        assert versions == [1, 2], (
            f"Les versions émises sont {versions}. Deux `1` veulent dire que les deux "
            "fils ont lu le même maximum — donc qu'aucune ligne n'était verrouillée ; un "
            "trou veut dire qu'un numéro a été consommé puis perdu, ce qui est ce qu'une "
            "`SEQUENCE` Postgres fait au rollback."
        )
        assert sorted(resultats.values()) == [1, 2]
    finally:
        with tenant_context(ALIAS):
            Ordonnance.objects.filter(client=fiche).delete()
            fiche.delete()
            Magasin.objects.filter(pk=magasin.pk).delete()
