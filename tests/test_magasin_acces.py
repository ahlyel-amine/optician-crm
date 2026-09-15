"""PERM-04 et PERM-05 — la portée magasin : des **lignes** et des **agrégats**, pas des champs.

**Ces tests ne sont pas encore implémentés.** Marqueur `pending`, corps volontairement
rouge ; les plans **03-05** (résolution de l'accès) et **03-07** (portée des querysets et
des agrégats) les implémentent et retirent le marqueur.

La distinction que ce fichier existe pour tenir, et qui est la raison pour laquelle il
n'est pas fusionné avec `test_projection.py` : la couche de projection caviarde des
**champs**. Elle ne peut caviarder ni une **ligne**, ni un **agrégat**. Un gérant qui n'a
accès qu'à un magasin mais qui reçoit encore un `SUM(montant)` sur toute l'affaire s'est
fait dire le chiffre d'affaires global que PERM-05 interdit, alors même que chaque champ
individuel était correctement masqué. Le total n'est le champ de personne.

Le magasin est une **colonne**, jamais une base : `tests/test_magasin_scoping.py`
(TENANT-07) pinne déjà l'asymétrie et l'absence délibérée de contextvar magasin. Il n'y a
donc pas de filtre implicite à hériter — la portée est écrite dans `get_queryset()` **et
dans chaque queryset de champ lié**, et c'est ce que ces tests vérifient.

Presque tous demandent `deux_magasins`. Ce n'est pas du confort : avec un seul magasin,
une vue qui ignore complètement la portée renvoie la même chose qu'une vue correcte, et
chaque assertion passe (`03-RESEARCH.md` P16).

**Aucun import du code en construction au niveau du module.**
"""

from __future__ import annotations

import pytest


# --------------------------------------------------------------------------------------
# PERM-04 — les lignes
# --------------------------------------------------------------------------------------
@pytest.mark.pending
def test_perm04_un_gerant_ne_voit_que_les_magasins_accordes_en_liste_et_en_detail(
    db_all, deux_magasins
):
    """PERM-04 — **et en détail**, ce qui est la moitié qu'on oublie.

    Filtrer la liste est le réflexe ; `/api/magasins/<id>/` sur un identifiant deviné ne
    passe pas par le même chemin si la portée a été écrite dans `list()` plutôt que dans
    `get_queryset()`. Rouge, ce test dirait exactement cela : la liste est propre, le
    détail est ouvert, et l'identifiant est un petit entier.

    Il porte donc **deux** assertions, pas une : la liste ne contient que Anfa, et le
    détail de Maârif répond 404.
    """
    pytest.fail("non implémenté : plan 03-07")


@pytest.mark.pending
def test_perm04_un_gerant_ne_peut_pas_ecrire_dans_un_magasin_non_accorde(
    db_all, deux_magasins
):
    """PERM-04 — la lecture filtrée ne dit rien de l'écriture.

    Une vue qui restreint `get_queryset()` protège la lecture, la modification et la
    suppression, mais **pas la création** : un POST qui nomme `magasin: <Maârif>` ne
    consulte aucun queryset. Rouge, ce test dirait qu'un gérant écrit dans un magasin qu'il
    ne voit même pas — une vente, un mouvement de stock ou une ligne de caisse chez un
    collègue, donc une balance qui ne tombe plus juste sans que personne sache pourquoi.

    La portée en écriture est une contrainte sur le **queryset du champ lié**, pas une
    validation ajoutée après coup.
    """
    pytest.fail("non implémenté : plan 03-07")


def test_perm04_un_droit_obsolete_sur_un_magasin_inactif_n_accorde_rien(
    db_all, deux_magasins
):
    """PERM-04 — l'accès effectif est une **intersection**, pas une liste stockée.

    Les magasins se désactivent (`actif = False`), ils ne se suppriment pas : CLAUDE.md #4
    et dix ans de conservation fiscale l'imposent. Les lignes `AccesMagasin` qui les visent
    survivent donc indéfiniment. Rouge, ce test dirait que l'accès est lu tel quel dans la
    table, donc qu'un magasin fermé l'an dernier reste dans la portée de quelqu'un — et le
    jour où son code est réutilisé pour une nouvelle boutique, l'accès s'y rouvre tout seul.

    L'accès effectif se calcule : droits stockés ∩ magasins actifs.

    **Le contrôle positif est ici la moitié qui compte.** « Maârif n'est pas dans la
    portée » est vrai d'un `acces_pour` qui ne résoudrait jamais rien ; ce test l'affirme
    donc d'abord *avec* Maârif actif, puis le désactive et réaffirme qu'Anfa tient
    toujours. Sans ces deux bornes, une résolution cassée passerait pour une résolution
    correcte.
    """
    from plateforme.comptes.acces import acces_pour
    from plateforme.comptes.permissions_catalogue import Permission
    from tests.factories import AccesMagasinFactory, DroitAccordeFactory, GerantFactory

    anfa, maarif = deux_magasins
    gerant = GerantFactory()
    for magasin in (anfa, maarif):
        AccesMagasinFactory(utilisateur=gerant, magasin_code=magasin.code)
        DroitAccordeFactory(
            utilisateur=gerant,
            magasin_code=magasin.code,
            code=Permission.CAISSE_SAISIR,
        )

    avant = acces_pour(gerant)
    assert avant.magasins_ids == frozenset({anfa.pk, maarif.pk})
    assert avant.peut(Permission.CAISSE_SAISIR, magasin_id=maarif.pk) is True

    # Le magasin ferme. La ligne AccesMagasin et la ligne DroitAccorde survivent — elles
    # ne sont pas supprimées, et c'est le cas nominal, pas un accident.
    maarif.actif = False
    maarif.save()

    apres = acces_pour(gerant)
    assert apres.magasins_ids == frozenset({anfa.pk})
    assert maarif.pk not in apres.droits_par_magasin
    assert apres.peut(Permission.CAISSE_SAISIR, magasin_id=maarif.pk) is False
    assert apres.magasins_pour(Permission.CAISSE_SAISIR) == frozenset({anfa.pk})

    # Le contrôle positif : Anfa, lui, n'a rien perdu. Sans cette ligne, une résolution
    # qui renverrait ANONYME à la moindre difficulté passerait ce test.
    assert apres.peut(Permission.CAISSE_SAISIR, magasin_id=anfa.pk) is True


def test_perm04_lacces_du_proprietaire_est_lensemble_complet_et_non_un_filtre_saute(
    db_all, deux_magasins
):
    """PERM-04 — « le propriétaire voit tout » doit être une valeur, pas un `if` qui saute.

    Les deux implémentations rendent la même réponse ici et divergent partout ailleurs. Si
    `est_proprietaire` fait sortir du chemin de portée par un retour anticipé, alors il
    existe un chemin de code où aucun filtre ne s'applique — et la phase 8 y branchera un
    agrégat, ou la phase 9 un rendu, en croyant que la portée est acquise. Si au contraire
    l'accès du propriétaire est l'**ensemble de tous les magasins actifs**, il n'y a qu'un
    seul chemin, et il est filtré.

    Rouge, ce test dirait que la branche existe. Il l'affirme sur l'objet `Acces`
    lui-même — un test qui ne regarderait que la réponse HTTP ne saurait pas distinguer.

    Deux assertions de nature différente, et il faut les deux : la **valeur** (les 21
    codes, pour chacun des deux magasins actifs) et la **propriété** (le corps de `peut`
    ne mentionne pas `est_proprietaire`). La valeur seule laisserait passer une
    implémentation qui matérialise *et* court-circuite ; la propriété seule laisserait
    passer un propriétaire qui ne peut rien.
    """
    import inspect

    from plateforme.comptes import acces as module_acces
    from plateforme.comptes.acces import acces_pour
    from plateforme.comptes.permissions_catalogue import Permission
    from tests.factories import ProprietaireFactory

    anfa, maarif = deux_magasins
    proprietaire = ProprietaireFactory()
    acces = acces_pour(proprietaire)

    assert acces.est_proprietaire is True
    assert acces.magasins_ids == frozenset({anfa.pk, maarif.pk})

    catalogue = frozenset(Permission.values)
    assert len(catalogue) == 21
    for magasin in (anfa, maarif):
        # Littéralement l'ensemble complet, magasin par magasin : matérialisé, pas déduit.
        assert acces.droits_par_magasin[magasin.pk] == catalogue
        for code in catalogue:
            assert acces.peut(code, magasin_id=magasin.pk) is True

    # Et donc, la conjonction sans magasin est vraie elle aussi — sans branche.
    for code in catalogue:
        assert acces.peut(code) is True

    source_peut = inspect.getsource(module_acces.Acces.peut)
    assert "est_proprietaire" not in source_peut, (
        "Le corps de `peut` mentionne `est_proprietaire`. C'est le raccourci que "
        "03-RESEARCH.md P3 décrit : un second chemin de code, sans filtre, qu'un bug "
        "peut atteindre pour un non-propriétaire. L'accès du propriétaire se matérialise "
        "dans `acces_pour`, une fois, à la résolution."
    )
    assert "pour_le_schema" not in source_peut, (
        "Même raison, autre porte : un court-circuit `if pour_le_schema` dans `peut` "
        "rouvrirait le second chemin de code que ce test existe pour fermer. L'accès du "
        "générateur OpenAPI est matérialisé lui aussi."
    )


# --------------------------------------------------------------------------------------
# PERM-05 — les agrégats
# --------------------------------------------------------------------------------------
@pytest.mark.pending
def test_perm05_un_agregat_est_calcule_sur_le_queryset_deja_filtre(db_all, deux_magasins):
    """PERM-05 — le total est le trou que la projection de champs ne bouche pas.

    `Model.objects.aggregate(Sum(...))` repart du manager par défaut et ignore le queryset
    filtré que la vue vient de construire. Rouge, ce test dirait qu'un gérant d'un seul
    magasin reçoit le chiffre d'affaires de toute l'affaire dans une carte de tableau de
    bord — un nombre unique, sans champ protégé, sans ligne interdite, et pourtant
    exactement l'information que PERM-05 interdit.

    Avec un seul magasin ce test est vide de sens : la somme filtrée et la somme globale
    sont le même nombre. D'où `deux_magasins`, avec des montants différents des deux côtés.
    """
    pytest.fail("non implémenté : plan 03-07")


def test_perm05_le_catalogue_declare_prix_achat_marge_et_ca_global():
    """PERM-05 — la phase 3 livre le **mécanisme** ; les champs arrivent en phases 8 et 10.

    `prix_achat`, `marge` et le chiffre d'affaires global n'existent pas encore comme
    colonnes — `03-VALIDATION.md` § « Known Deferral » le dit, et la vérification vivante
    appartient à la phase 8. Ce que la phase 3 peut prouver, et que ce test prouve, c'est
    que les **codes** de permission correspondants sont déclarés dès maintenant, donc que
    la phase 8 n'aura qu'une ligne de registre à ajouter au lieu d'un modèle de droits à
    inventer sous pression.

    Rouge, il dirait que le catalogue a été écrit pour ce qui existe aujourd'hui, ce qui est
    la façon dont une garantie architecturale se perd : non par renversement, par omission.
    """
    from plateforme.comptes.permissions_catalogue import (
        EXPLICATIONS,
        PREREQUIS,
        SECTIONS,
        Permission,
    )

    differes = (
        "article.voir_prix_achat",  # phase 8
        "vente.voir_marge",  # phase 8
        "dashboard.voir_ca_global",  # phase 10
    )
    for code in differes:
        assert code in Permission.values, code
        # Déclaré ne suffit pas : il doit être **accordable**, donc porté par une section
        # de l'écran et pourvu de son explication. Un code présent dans l'énumération mais
        # absent des sections est invisible, et la phase 8 le redécouvrirait sous pression.
        assert any(code in section.codes for section in SECTIONS), code
        assert EXPLICATIONS[code].strip().endswith("."), code

    # La dépendance que `03-UI-SPEC.md` 7.6 impose entre les deux codes de phase 8 : voir
    # la marge sans voir le prix d'achat rendrait le prix d'achat calculable à la main.
    assert PREREQUIS["vente.voir_marge"] == ("article.voir_prix_achat",)

    # Et le contrôle positif : aucun des trois n'a de colonne derrière lui en phase 3.
    # Si l'un en acquiert une ici, ce n'est plus un mécanisme, c'est une fonctionnalité
    # arrivée en avance et non testée.
    from django.apps import apps

    champs_metier = {
        f"{modele._meta.label}.{champ.name}"
        for config in apps.get_app_configs()
        if config.name.startswith("domaine.")
        for modele in config.get_models()
        for champ in modele._meta.get_fields()
    }
    assert not {nom for nom in champs_metier if nom.endswith((".prix_achat", ".marge"))}


# --------------------------------------------------------------------------------------
# PERM-03 / PERM-06 — la forme de l'accès résolu (plan 03-05)
# --------------------------------------------------------------------------------------
def test_perm06_lacces_absent_vaut_aucun_droit():
    """CLAUDE.md #8 appliqué à la couche de permissions : l'absence vaut zéro, pas « tout ».

    `03-RESEARCH.md` P2 décrit le fail-open exactement : `getattr(request, "acces", None)`
    suivi de « si None, tout montrer ». Le contre-poison n'est pas une convention d'appel,
    c'est qu'il existe une **valeur** à mettre par défaut. `Acces.ANONYME` est cette
    valeur, et ce test la pinne sur les 21 codes plutôt que sur un échantillon : un
    catalogue qui grandit en phase 8 est couvert sans qu'on y pense.

    Aucune base de données. Si ce test venait à en demander une, c'est que l'accès anonyme
    a cessé d'être une constante — et une constante est précisément ce qu'il doit être pour
    servir de défaut partout.
    """
    from django.contrib.auth.models import AnonymousUser

    from plateforme.comptes.acces import Acces, acces_pour
    from plateforme.comptes.permissions_catalogue import Permission

    for code in Permission.values:
        assert Acces.ANONYME.peut(code) is False, code
        # Y compris nommément : « je ne sais pas quel magasin » ne doit pas devenir « oui ».
        assert Acces.ANONYME.peut(code, magasin_id=1) is False, code
        assert Acces.ANONYME.peut_quelque_part(code) is False, code
        assert Acces.ANONYME.magasins_pour(code) == frozenset(), code

    assert Acces.ANONYME.magasins_ids == frozenset()
    assert dict(Acces.ANONYME.droits_par_magasin) == {}

    # Les portes d'entrée de la résolution, fermées : pas d'utilisateur du tout, et
    # l'utilisateur non authentifié de Django.
    assert acces_pour(None) is Acces.ANONYME
    assert acces_pour(AnonymousUser()) is Acces.ANONYME


def test_perm03_peut_sans_magasin_est_une_conjonction_pas_une_union(db_all, deux_magasins):
    """PERM-03 / CLAUDE.md #13 — « détenu partout », jamais « détenu quelque part ».

    C'est la décision que les phases 5 à 10 hériteront sans la relire, donc elle est pinnée
    ici plutôt que laissée à une docstring. La projection de champs s'applique à un
    **serializer**, pas à une ligne : au moment où elle décide de garder ou d'ôter
    `prix_achat`, elle ne sait pas encore de quel magasin sera la ligne rendue. Si
    `peut(code)` répondait « oui, quelque part », le gérant qui détient le droit à Anfa
    recevrait le prix d'achat des articles de Maârif.

    L'union existe — `peut_quelque_part` — et ce test la sépare de l'autorisation en les
    affirmant **contradictoires sur le même accès**. Un `peut()` implémenté par une union
    rendrait ces deux assertions identiques, et ce fichier ne pourrait plus voir la
    différence.

    Deux magasins obligatoires : avec un seul, conjonction et union sont la même fonction.
    """
    from plateforme.comptes.acces import acces_pour
    from plateforme.comptes.permissions_catalogue import Permission
    from tests.factories import AccesMagasinFactory, DroitAccordeFactory, GerantFactory

    anfa, maarif = deux_magasins
    gerant = GerantFactory()
    # Les **deux** magasins sont accordés : ce que ce test mesure est le droit, pas l'accès.
    for magasin in (anfa, maarif):
        AccesMagasinFactory(utilisateur=gerant, magasin_code=magasin.code)
    DroitAccordeFactory(
        utilisateur=gerant, magasin_code=anfa.code, code=Permission.CAISSE_SAISIR
    )

    acces = acces_pour(gerant)
    assert acces.magasins_ids == frozenset({anfa.pk, maarif.pk})
    assert acces.peut(Permission.CAISSE_SAISIR, magasin_id=anfa.pk) is True
    assert acces.peut(Permission.CAISSE_SAISIR, magasin_id=maarif.pk) is False

    assert acces.peut(Permission.CAISSE_SAISIR) is False, (
        "Sans argument magasin, `peut` a répondu oui pour un code détenu dans un seul des "
        "deux magasins accordés. C'est une union, donc une fuite : la projection de champs "
        "livrerait les données de Maârif sur la foi d'un droit accordé à Anfa."
    )
    assert acces.peut_quelque_part(Permission.CAISSE_SAISIR) is True
    assert acces.magasins_pour(Permission.CAISSE_SAISIR) == frozenset({anfa.pk})

    # Et l'état que la quasi-totalité des entreprises verra (03-UI-SPEC 7.5) : une ligne
    # **uniforme**, où tous les magasins accordés sont d'accord. La conjonction devient
    # vraie, sans que `peut` ait changé de règle.
    DroitAccordeFactory(
        utilisateur=gerant, magasin_code=maarif.code, code=Permission.CAISSE_SAISIR
    )
    uniforme = acces_pour(gerant)
    assert uniforme.peut(Permission.CAISSE_SAISIR) is True
    assert uniforme.magasins_pour(Permission.CAISSE_SAISIR) == frozenset(
        {anfa.pk, maarif.pk}
    )


def test_perm04_un_operateur_sans_client_resout_vers_anonyme(db_all):
    """PERM-04 — un opérateur de plateforme n'a aucun accès métier, par conception.

    `client_id is None` veut dire « n'appartient à aucune affaire ». C'est le compte qui
    provisionne, migre et dépanne ; il n'est le gérant de personne. `resolve_client` le
    traite déjà ainsi (aucun locataire lié), et ce test dit que la couche de permissions
    ne le rattrape pas par une autre porte : un opérateur qui hériterait d'un accès métier
    serait un compte d'administration avec vue sur les données de santé de toute la flotte.

    Rouge, il dirait que `acces_pour` est parti de `est_proprietaire` ou des lignes de
    droits sans d'abord demander à quelle affaire ce compte appartient.
    """
    from plateforme.comptes.acces import Acces, acces_pour
    from tests.factories import UtilisateurFactory

    operateur = UtilisateurFactory()
    assert operateur.client_id is None
    assert operateur.is_authenticated is True  # le contrôle positif : il est bien connecté

    assert acces_pour(operateur) is Acces.ANONYME


#: Les **deux** usages sanctionnés de `peut_quelque_part`, et il n'y en a pas de troisième.
#: Chaque site d'appel dans `plateforme/` doit porter le marqueur
#: `# usage-sanctionne: peut_quelque_part <étiquette>` sur sa propre ligne ou sur l'une des
#: deux qui la précèdent. Ajouter une étiquette ici est un acte délibéré qui se relit en
#: revue ; c'est exactement ce que le test veut forcer.
USAGES_SANCTIONNES_PEUT_QUELQUE_PART = {
    #: Le champ `navigation` de `/api/auth/moi/` (plan 03-08) — masquer une entrée de menu
    #: n'autorise rien ; l'écran derrière est protégé par `peut(code, magasin_id)`.
    "navigation",
    #: Le catalogue pré-intersecté servi à un gérant-gestionnaire (plan 03-09) — il décide
    #: quelles cases sont *offrables*, pas ce qui est permis.
    "catalogue",
}


def test_perm04_peut_quelque_part_n_est_appele_que_depuis_ses_deux_usages_sanctionnes():
    """PERM-04 — l'échappatoire à l'union est gardée par un test, pas par une docstring.

    `peut_quelque_part` est une **union** là où `peut` est une conjonction. Ce n'est jamais
    une autorisation : elle répond « quelque part », et « quelque part » ne dit pas *ici*.
    Deux usages en ont légitimement besoin, tous deux au sujet de ce qu'on *propose* à
    l'écran et non de ce qu'on *sert*.

    Partout ailleurs, cette phase contraint ses échappatoires par une énumération
    (`tenancy.E001`, `projection.E001`, l'énumération des `MagasinScopedViewSet`, le garde
    source sur `.values()`). Celle-ci le mérite d'autant plus que son mode de défaillance
    est **silencieux dans le bon sens** : un troisième appelant ne casse rien visiblement,
    il autorise trop, discrètement, et personne n'ouvre de ticket.

    **Ce que ce test affirme aujourd'hui, et ce qu'il affirmera plus tard.** Les deux
    appelants sanctionnés n'existent pas encore — ils arrivent aux plans 03-08 et 03-09.
    Le test n'est pas `pending` pour autant : il affirme dès maintenant (a) que l'ensemble
    sanctionné compte **exactement deux** entrées, (b) que tout site d'appel existant porte
    l'une d'elles, et (c) qu'aucune étiquette ne sert deux fois. Le nombre d'appelants monte
    donc de 0 à 2 au fil des deux plans, sans qu'aucune assertion ne bouge, et un troisième
    appelant est rouge à la seconde où il est écrit — non parce qu'il déborde un compteur,
    mais parce qu'il n'a pas d'étiquette libre à prendre.
    """
    import ast
    import pathlib

    assert len(USAGES_SANCTIONNES_PEUT_QUELQUE_PART) == 2, (
        "L'ensemble des usages sanctionnés n'en compte plus deux. Élargir cet ensemble "
        "est la façon dont l'union redevient une autorisation ; si un troisième usage est "
        "vraiment légitime, il se justifie dans un plan, pas dans un import."
    )

    racine = pathlib.Path(__file__).resolve().parent.parent / "plateforme"
    definition = racine / "comptes" / "acces.py"
    assert definition.exists(), "acces.py a disparu — le garde ne garde plus rien."

    appelants = []
    for fichier in sorted(racine.rglob("*.py")):
        if fichier == definition:
            continue  # la définition et sa docstring ne sont pas des appels
        lignes = fichier.read_text(encoding="utf-8").splitlines()
        arbre = ast.parse("\n".join(lignes), filename=str(fichier))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            nom = getattr(noeud.func, "attr", None) or getattr(noeud.func, "id", None)
            if nom != "peut_quelque_part":
                continue
            # Le marqueur est accepté sur la ligne de l'appel ou sur les deux qui la
            # précèdent, parce qu'un appel formaté par black tient rarement sur une ligne.
            etiquette = None
            for ligne in lignes[max(0, noeud.lineno - 3) : noeud.lineno]:
                _, separateur, reste = ligne.partition(
                    "# usage-sanctionne: peut_quelque_part "
                )
                if separateur:
                    etiquette = reste.strip()
            appelants.append(
                (str(fichier.relative_to(racine.parent)), noeud.lineno, etiquette)
            )

    sans_marqueur = [a for a in appelants if a[2] is None]
    assert not sans_marqueur, (
        f"Appel(s) non sanctionné(s) de `peut_quelque_part` : {sans_marqueur}. "
        "`peut_quelque_part` est une union et n'autorise rien. Si c'est une décision "
        "d'autorisation, c'est `peut(code, magasin_id=...)` qu'il faut ; si c'est bien un "
        "des deux usages d'affichage, marquer la ligne "
        "`# usage-sanctionne: peut_quelque_part <étiquette>`."
    )

    inconnues = {a[2] for a in appelants} - USAGES_SANCTIONNES_PEUT_QUELQUE_PART
    assert not inconnues, (
        f"Étiquette(s) hors de l'ensemble sanctionné : {sorted(inconnues)}. "
        f"Les deux seules sont {sorted(USAGES_SANCTIONNES_PEUT_QUELQUE_PART)}."
    )

    etiquettes = [a[2] for a in appelants]
    doublons = {e for e in etiquettes if etiquettes.count(e) > 1}
    assert not doublons, (
        f"Étiquette(s) réutilisée(s) : {sorted(doublons)}. Une étiquette désigne **un** "
        "site d'appel ; la réutiliser est la façon la plus simple de faire passer un "
        "troisième appelant pour l'un des deux."
    )

    assert len(appelants) == len(set(etiquettes)) <= 2
