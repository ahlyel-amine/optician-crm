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

**Aucun import du code en construction au niveau du module** — la règle du plan 03-02,
tenue tant que la couche n'existait pas. Depuis le plan 03-07 il y a une exception, et une
seule : la **fixture pytest** `table_ressource_magasin`, qui doit être un nom du module de
test pour que pytest la résolve. Elle est importée pour son effet de bord d'enregistrement,
pas pour être appelée ; tout le reste est importé dans le corps des tests, comme avant.
"""

from __future__ import annotations

import pytest

from tests.ressources_fixture import (  # noqa: F401 — fixture pytest, importée pour être disponible
    table_ressource_magasin,
)


# --------------------------------------------------------------------------------------
# PERM-04 — les lignes
# --------------------------------------------------------------------------------------
def test_perm04_un_gerant_ne_voit_que_les_magasins_accordes_en_liste_et_en_detail(
    db_all, deux_magasins, table_ressource_magasin
):
    """PERM-04 — **et en détail**, ce qui est la moitié qu'on oublie.

    Filtrer la liste est le réflexe ; `/api/magasins/<id>/` sur un identifiant deviné ne
    passe pas par le même chemin si la portée a été écrite dans `list()` plutôt que dans
    `get_queryset()`. Rouge, ce test dirait exactement cela : la liste est propre, le
    détail est ouvert, et l'identifiant est un petit entier.

    Il porte donc **deux** assertions, pas une : la liste ne contient que Anfa, et le
    détail de Maârif répond 404.

    **Et un contrôle positif, qui est la troisième.** « Maârif répond 404 » est vrai d'une
    vue en panne. Le détail d'**Anfa** doit répondre 200 dans le même test, sans quoi une
    portée qui ne rendrait jamais rien passerait pour une portée correcte.
    """
    from tests.ressources_fixture import (
        acces_sur_un_seul_magasin,
        appeler_vue_magasin,
        semer_ressources_magasin,
    )

    anfa, maarif = deux_magasins
    lignes_anfa, lignes_maarif = semer_ressources_magasin(anfa, maarif)
    gerant, acces = acces_sur_un_seul_magasin(anfa)
    assert acces.magasins_ids == frozenset({anfa.pk})

    liste = appeler_vue_magasin(gerant, "get", "list")
    assert liste.status_code == 200, liste.data
    magasins_servis = {ligne["magasin"] for ligne in liste.data}
    assert magasins_servis == {anfa.pk}, (
        f"La liste a servi les magasins {magasins_servis}, dont un que le gérant n'a pas. "
        "La portée n'est pas appliquée, ou elle l'est après la pagination."
    )
    assert len(liste.data) == len(lignes_anfa)

    # Le contrôle positif : la route de détail **fonctionne** pour une ligne accordée.
    permis = appeler_vue_magasin(
        gerant,
        "get",
        "retrieve",
        chemin=f"/api/ressources-magasin/{lignes_anfa[0].pk}/",
        pk=lignes_anfa[0].pk,
    )
    assert permis.status_code == 200, permis.data

    # Et l'IDOR classique : le même chemin, un identifiant d'un magasin non accordé.
    interdit = appeler_vue_magasin(
        gerant,
        "get",
        "retrieve",
        chemin=f"/api/ressources-magasin/{lignes_maarif[0].pk}/",
        pk=lignes_maarif[0].pk,
    )
    assert interdit.status_code == 404, (
        f"La route de détail a répondu {interdit.status_code} sur une ligne de Maârif. "
        "C'est l'IDOR que P4 décrit : la portée a été posée dans `list()`, que "
        "`get_object()` ne traverse pas. Elle appartient à `get_queryset()`."
    )


def test_perm04_un_gerant_ne_peut_pas_ecrire_dans_un_magasin_non_accorde(
    db_all, deux_magasins, table_ressource_magasin
):
    """PERM-04 — la lecture filtrée ne dit rien de l'écriture.

    Une vue qui restreint `get_queryset()` protège la lecture, la modification et la
    suppression, mais **pas la création** : un POST qui nomme `magasin: <Maârif>` ne
    consulte aucun queryset. Rouge, ce test dirait qu'un gérant écrit dans un magasin qu'il
    ne voit même pas — une vente, un mouvement de stock ou une ligne de caisse chez un
    collègue, donc une balance qui ne tombe plus juste sans que personne sache pourquoi.

    La portée en écriture est une contrainte sur le **queryset du champ lié**, pas une
    validation ajoutée après coup.

    **400 et non 403**, et ce n'est pas un détail de forme : DRF valide la clé primaire
    contre le queryset du champ, donc restreindre ce queryset transforme l'écriture
    inter-magasins en erreur de validation, sans code de permission à écrire ni à oublier.
    """
    from decimal import Decimal

    from tests.ressources_fixture import (
        RessourceMagasin,
        acces_sur_un_seul_magasin,
        appeler_vue_magasin,
    )

    anfa, maarif = deux_magasins
    gerant, _ = acces_sur_un_seul_magasin(anfa)

    refuse = appeler_vue_magasin(
        gerant,
        "post",
        "create",
        corps={"magasin": maarif.pk, "libelle": "Chez le voisin", "montant": "99.00"},
    )
    assert refuse.status_code == 400, (
        f"Le POST vers Maârif a répondu {refuse.status_code} : {refuse.data}. Un 201 est "
        "l'IDOR d'écriture de P5 — `PrimaryKeyRelatedField(queryset=Magasin.objects.all())` "
        "accepte n'importe quelle clé, et la lecture filtrée n'y peut rien."
    )
    assert "magasin" in refuse.data, refuse.data
    assert not RessourceMagasin.objects.filter(magasin=maarif, libelle="Chez le voisin")

    # Le contrôle positif : la même requête vers le magasin **accordé** réussit. Sans
    # elle, un champ lié dont le queryset serait toujours vide passerait ce test.
    accepte = appeler_vue_magasin(
        gerant,
        "post",
        "create",
        corps={"magasin": anfa.pk, "libelle": "Chez moi", "montant": "99.00"},
    )
    assert accepte.status_code == 201, accepte.data
    ecrite = RessourceMagasin.objects.get(libelle="Chez moi")
    assert ecrite.magasin_id == anfa.pk
    assert ecrite.montant == Decimal("99.00")


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
def test_perm05_un_agregat_est_calcule_sur_le_queryset_deja_filtre(
    db_all, deux_magasins, table_ressource_magasin
):
    """PERM-05 — le total est le trou que la projection de champs ne bouche pas.

    `Model.objects.aggregate(Sum(...))` repart du manager par défaut et ignore le queryset
    filtré que la vue vient de construire. Rouge, ce test dirait qu'un gérant d'un seul
    magasin reçoit le chiffre d'affaires de toute l'affaire dans une carte de tableau de
    bord — un nombre unique, sans champ protégé, sans ligne interdite, et pourtant
    exactement l'information que PERM-05 interdit.

    Avec un seul magasin ce test est vide de sens : la somme filtrée et la somme globale
    sont le même nombre. D'où `deux_magasins`, avec des montants différents des deux côtés.

    **Il échoue sur un calcul-puis-masquage**, et c'est la seule forme d'échec qui compte :
    on ne peut pas ne pas voir un scalaire déjà calculé, donc la seule implémentation qui
    rende ce nombre est celle qui n'a jamais additionné Maârif. Les assertions sont en
    `Decimal` — CLAUDE.md #7, et `assert total == 1800.0` passerait pendant que l'argent
    est faux.
    """
    from decimal import Decimal

    from django.db.models import Sum

    from tests.ressources_fixture import (
        TOTAL_ANFA,
        TOTAL_ENTREPRISE,
        RessourceMagasin,
        acces_sur_un_seul_magasin,
        appeler_vue_magasin,
        semer_ressources_magasin,
    )

    anfa, maarif = deux_magasins
    semer_ressources_magasin(anfa, maarif)
    gerant, acces = acces_sur_un_seul_magasin(anfa)

    # Le contrôle qui donne un sens au test : les deux nombres sont différents, et le
    # global est bien ce que la base contient.
    assert TOTAL_ANFA != TOTAL_ENTREPRISE
    assert RessourceMagasin.objects.aggregate(t=Sum("montant"))["t"] == TOTAL_ENTREPRISE

    reponse = appeler_vue_magasin(
        gerant, "get", "total", chemin="/api/ressources-magasin/total/"
    )
    assert reponse.status_code == 200, reponse.data
    servi = Decimal(reponse.data["total"])

    assert servi == TOTAL_ANFA, (
        f"L'agrégat servi vaut {servi} ; la somme des seuls magasins accordés vaut "
        f"{TOTAL_ANFA} et celle de toute l'affaire {TOTAL_ENTREPRISE}. Servir le second "
        "est le chiffre d'affaires global que PERM-05 interdit, et aucun caviardage ne "
        "peut le reprendre : le scalaire est déjà calculé."
    )
    assert servi != TOTAL_ENTREPRISE

    # Et l'aide elle-même, sans passer par la vue : elle **prend l'accès** et restreint.
    # Sans cette assertion, une vue qui filtrerait à la main passerait le test tout en
    # laissant l'aide ouverte pour la phase 10.
    from plateforme.projection.vues import agreger_dans_la_portee

    direct = agreger_dans_la_portee(
        RessourceMagasin.objects.all(), acces, total=Sum("montant")
    )
    assert direct["total"] == TOTAL_ANFA


def test_perm05_la_generation_du_schema_ne_subit_pas_la_portee_magasin(
    db_all, deux_magasins, table_ressource_magasin
):
    """PERM-05 / T-03-32 — le schéma voit tout, parce qu'un contrat ne varie pas par lecteur.

    `Acces.SCHEMA.magasins_ids` est **vide** (plan 03-05, décision assumée) : le générateur
    OpenAPI n'appartient à aucune affaire et à aucun magasin. Appliquée telle quelle, la
    portée des lignes lui rendrait zéro ligne — ce qui est sans effet sur un schéma, mais
    fait du drapeau `pour_le_schema` la seule chose qui distingue « le générateur » de « un
    gérant sans magasin ». C'est `acces.py` qui le dit en toutes lettres : la portée
    court-circuite sur `pour_le_schema`, **à l'endroit où elle est écrite**, et `peut()`
    ne l'apprend pas.

    Rouge, ce test dirait que le schéma servi dépend de l'appelant — et un client
    TypeScript généré depuis un document qui dépend de l'appelant n'est pas un contrat.
    """
    from plateforme.comptes.acces import Acces, _PorteurAcces
    from tests.ressources_fixture import (
        RessourceMagasin,
        VueRessourceMagasin,
        semer_ressources_magasin,
    )

    anfa, maarif = deux_magasins
    semer_ressources_magasin(anfa, maarif)
    attendu = RessourceMagasin.objects.count()
    assert attendu > 0  # contrôle positif : la base n'est pas vide

    vue = VueRessourceMagasin()
    vue.request = _PorteurAcces(acces=Acces.SCHEMA)
    assert vue.get_queryset().count() == attendu, (
        "La portée s'est appliquée à la génération du schéma. `Acces.SCHEMA` ne porte "
        "aucun magasin, donc le document deviendrait celui d'un gérant sans magasin — "
        "et il cesserait de décrire l'API."
    )

    # Le contraire, dans le même test : un accès ordinaire **subit** la portée. Sans lui,
    # un `get_queryset` qui ne filtrerait jamais passerait l'assertion ci-dessus.
    vue_gerant = VueRessourceMagasin()
    vue_gerant.request = _PorteurAcces(acces=Acces.ANONYME)
    assert vue_gerant.get_queryset().count() == 0


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


# --------------------------------------------------------------------------------------
# PERM-04 / T-03-26 / T-03-27 — AccesMiddleware (plan 03-05, tâche 2)
# --------------------------------------------------------------------------------------
def test_perm04_accesmiddleware_est_installe_strictement_apres_tenantmiddleware():
    """L'ordre n'est pas cosmétique : avant `TenantMiddleware`, la résolution ne peut pas lire.

    Résoudre à quels magasins un octroi se réfère demande une requête dans la base **du
    client** — `Magasin.objects.filter(actif=True, code__in=...)`. Cette requête passe par
    le routeur, qui lit l'alias lié, et qui **lève** `NoTenantBound` quand il n'y en a pas.
    Placé avant `TenantMiddleware`, `AccesMiddleware` ne se plaindrait pourtant de rien à
    l'installation : l'objet est paresseux, donc l'erreur n'apparaîtrait qu'au premier point
    de terminaison qui touche `request.acces`, en production, sur la requête d'un opticien.

    L'assertion porte sur les **index** dans `settings.MIDDLEWARE` et non sur le texte du
    fichier : un `grep` verrait « AccesMiddleware après TenantMiddleware » dans un
    commentaire aussi bien que dans la liste.
    """
    from django.conf import settings

    chemins = list(settings.MIDDLEWARE)
    attendus = (
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "plateforme.tenancy.middleware.TenantMiddleware",
        "plateforme.comptes.middleware.AccesMiddleware",
    )
    for chemin in attendus:
        assert chemin in chemins, f"{chemin} a disparu de MIDDLEWARE"

    index = [chemins.index(chemin) for chemin in attendus]
    assert index == sorted(index), (
        f"L'ordre est {[chemins[i] for i in sorted(index)]}. Il doit être "
        f"Authentication → Tenant → Acces : l'identité d'abord, l'alias du client "
        f"ensuite, et seulement alors la résolution qui a besoin des deux."
    )


def test_perm04_accesmiddleware_ne_pose_rien_dans_un_contextvar():
    """T-03-26 — l'accès vit sur la requête, dont la durée de vie le borne. Rien à nettoyer.

    Le `reset(token)` banni dans `plateforme/tenancy/` l'est aussi ici, et pour une raison
    plus forte : dans `comptes`, il n'y a **rien** à nettoyer, donc il n'y a aucune raison
    d'introduire ce qui demanderait un nettoyage. Le risque réel est le mimétisme — quelqu'un
    lit le middleware de locataire, voit un `contextvar` et un `finally`, et reproduit la
    forme sans la raison. Un `contextvar` sur un thread de travail réutilisé qu'on oublie de
    vider rend l'accès d'une requête visible dans la suivante.

    Le test lit le **source** parce que c'est la seule façon de rougir sur une forme qui
    n'est pas encore un bug : un `contextvar` correctement nettoyé passerait tous les tests
    de comportement, et resterait une porte ouverte pour le prochain `finally` oublié.
    """
    import pathlib

    source = pathlib.Path(
        pathlib.Path(__file__).resolve().parent.parent
        / "plateforme"
        / "comptes"
        / "middleware.py"
    ).read_text(encoding="utf-8")

    # Les lignes de l'interdiction elle-même sont évidemment exemptées : elles nomment ce
    # qu'elles interdisent, c'est leur travail. Ce qui est traqué est du **code**.
    code = [
        ligne
        for ligne in source.splitlines()
        if ligne.strip() and not ligne.lstrip().startswith("#")
    ]
    # Retirer la docstring de module, qui porte l'interdiction en toutes lettres.
    dans_docstring = False
    effectif = []
    for ligne in code:
        marques = ligne.count('"""')
        if dans_docstring:
            if marques:
                dans_docstring = False
            continue
        if marques == 1:
            dans_docstring = True
            continue
        if marques >= 2:
            continue
        effectif.append(ligne)

    fautifs = [
        ligne
        for ligne in effectif
        if "contextvar" in ligne.lower() or "reset(" in ligne.replace(" ", "")
    ]
    assert not fautifs, (
        f"`plateforme/comptes/middleware.py` porte du code de contexte : {fautifs}. "
        "L'accès se pose sur la requête ; il n'y a rien à nettoyer, donc rien à oublier."
    )


def test_perm04_request_acces_est_paresseux_et_ne_coute_rien_sil_nest_pas_touche(
    db_all, deux_magasins
):
    """T-03-27 — un point de terminaison qui ne lit pas `request.acces` ne paie rien.

    Sans paresse, chaque requête — la sonde de santé, le service d'un fichier statique, la
    page de connexion — paierait deux requêtes SQL de droits sur deux bases, dont une dans
    la base du client. Ce n'est pas seulement du gaspillage : c'est une connexion au
    locataire ouverte sur des chemins qui n'ont aucune raison d'en avoir une.

    Le compte de requêtes est la seule preuve possible. `SimpleLazyObject` se comporte
    exactement comme l'objet enveloppé dès qu'on le touche, donc aucune assertion sur la
    valeur ne saurait distinguer « paresseux » de « résolu à l'entrée ».

    Les deux moitiés sont nécessaires : zéro requête pour la vue qui n'y touche pas, et
    **plus de zéro** pour celle qui y touche. La première seule serait verte si
    `acces_pour` ne faisait jamais rien.
    """
    from django.db import connections
    from django.test import RequestFactory
    from django.test.utils import CaptureQueriesContext

    from plateforme.comptes.middleware import AccesMiddleware
    from plateforme.comptes.permissions_catalogue import Permission
    from tests.factories import AccesMagasinFactory, DroitAccordeFactory, GerantFactory

    anfa, _maarif = deux_magasins
    gerant = GerantFactory()
    AccesMagasinFactory(utilisateur=gerant, magasin_code=anfa.code)
    DroitAccordeFactory(
        utilisateur=gerant, magasin_code=anfa.code, code=Permission.STOCK_VOIR
    )

    fabrique = RequestFactory()

    def _requete():
        requete = fabrique.get("/sante/")
        requete.user = gerant
        return requete

    def _compter(vue):
        """Les requêtes SQL sur les **deux** bases : le plan de contrôle et le client."""
        middleware = AccesMiddleware(vue)
        with CaptureQueriesContext(connections["default"]) as controle:
            with CaptureQueriesContext(connections["tenant_a"]) as locataire:
                middleware(_requete())
        return len(controle) + len(locataire)

    indifferente = _compter(lambda requete: "aucun droit consulté")
    assert indifferente == 0, (
        f"Une vue qui ne touche jamais `request.acces` a coûté {indifferente} requête(s). "
        "L'accès doit être paresseux : la sonde de santé n'a pas à interroger la base d'un "
        "opticien."
    )

    curieuse = _compter(
        lambda requete: requete.acces.peut(Permission.STOCK_VOIR, magasin_id=anfa.pk)
    )
    assert curieuse > 0, (
        "Une vue qui lit `request.acces` n'a déclenché aucune requête. Soit la résolution "
        "est mise en cache — ce que la révocation sans reconnexion interdit — soit elle ne "
        "lit rien du tout."
    )


def test_perm06_sur_un_chemin_anonyme_request_acces_vaut_anonyme(db_all):
    """Le défaut est une **valeur**, y compris là où le middleware s'exécute bel et bien.

    Sur la page de connexion, sur une sonde de santé, sur tout ce qui précède
    l'authentification, `request.acces` existe et vaut `Acces.ANONYME`. Il n'est ni absent
    — ce qui inviterait au `getattr(request, "acces", None)` puis au « si None, tout
    montrer » de `03-RESEARCH.md` P2 — ni `None`.

    Et aucune requête métier n'est tentée : un chemin anonyme n'a pas de locataire lié, donc
    la moindre requête sur `Magasin` y lèverait `NoTenantBound`. La résolution doit sortir
    avant, sur les trois conditions d'entrée, et pas après avoir interrogé quoi que ce soit.
    """
    from django.contrib.auth.models import AnonymousUser
    from django.db import connections
    from django.test import RequestFactory
    from django.test.utils import CaptureQueriesContext

    from plateforme.comptes.acces import Acces
    from plateforme.comptes.middleware import AccesMiddleware
    from plateforme.comptes.permissions_catalogue import Permission

    vu = {}

    def vue(requete):
        vu["acces"] = requete.acces
        # On le touche pour de bon : la paresse ne doit pas cacher le comportement.
        vu["peut"] = requete.acces.peut(Permission.STOCK_VOIR)
        vu["magasins"] = requete.acces.magasins_ids
        return "ok"

    requete = RequestFactory().get("/api/auth/connexion/")
    requete.user = AnonymousUser()

    with CaptureQueriesContext(connections["default"]) as requetes:
        AccesMiddleware(vue)(requete)

    assert vu["acces"] == Acces.ANONYME
    assert vu["peut"] is False
    assert vu["magasins"] == frozenset()
    assert len(requetes) == 0, (
        f"Un chemin anonyme a déclenché {len(requetes)} requête(s) : {requetes.captured_queries}. "
        "Aucun locataire n'y est lié ; la résolution doit sortir sur `ANONYME` avant de "
        "consulter quoi que ce soit."
    )


def test_perm04_lacces_ne_fuit_pas_entre_deux_requetes_sur_un_thread_reutilise():
    """T-03-26 — un seul thread, trois requêtes, trois accès distincts.

    Même forme que `test_tenant04_context_does_not_leak_between_requests_on_one_thread` de
    la phase 2, et pour la même raison : un thread neuf démarre avec un contexte vide et
    masquerait le bug pour toujours. Le pool à **un** travailleur est ce que fait le
    travailleur gthread de gunicorn, et l'identité du thread est asserée pour qu'un
    refactor qui en lancerait un par requête rougisse ici plutôt que de rendre le test
    décoratif.

    **Le résolveur est remplacé par un compteur, délibérément.** Ce qui est sous test est la
    *discipline de rangement* du middleware — attribut de requête contre état partagé — et
    non la résolution, qui a ses propres tests avec une vraie base. Passer par la base ici
    obligerait à écrire des lignes depuis le thread du pool, hors de la transaction que
    pytest-django annule, donc à laisser des comptes derrière soi dans la base de test. Le
    faux résolveur rend en outre la fuite *observable* : deux accès aux identifiants
    distincts, là où deux résolutions réelles du même compte seraient indiscernables.
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from django.test import RequestFactory

    from plateforme.comptes import middleware as module_middleware
    from plateforme.comptes.acces import Acces
    from plateforme.comptes.middleware import AccesMiddleware

    class _Principal:
        """Ce que `AuthenticationMiddleware` aurait posé : une identité, rien de plus."""

        def __init__(self, identifiant):
            self.pk = identifiant
            self.is_authenticated = identifiant is not None

    def _faux_acces(identifiant):
        return Acces(
            utilisateur_id=identifiant,
            client_id=1,
            est_proprietaire=False,
            droits_par_magasin={identifiant: frozenset({f"code.{identifiant}"})},
            magasins_ids=frozenset({identifiant}),
        )

    appels = []

    def _resolveur(utilisateur):
        appels.append(getattr(utilisateur, "pk", None))
        if not getattr(utilisateur, "is_authenticated", False):
            return Acces.ANONYME
        return _faux_acces(utilisateur.pk)

    threads_vus = []
    fabrique = RequestFactory()

    def _identite_du_thread():
        # `Thread.name`, jamais `get_ident()` : l'identifiant système est recyclé dès qu'un
        # thread se termine, donc une version de ce test qui lancerait un thread par
        # requête rapporterait une seule identité et passerait contre du code qui fuit.
        return threading.current_thread().name

    def servir(identifiant):
        threads_vus.append(_identite_du_thread())
        requete = fabrique.get("/api/stock/")
        requete.user = _Principal(identifiant)
        vu = {}

        def vue(requete_recue):
            vu["utilisateur_id"] = requete_recue.acces.utilisateur_id
            vu["magasins"] = frozenset(requete_recue.acces.magasins_ids)
            return "ok"

        AccesMiddleware(vue)(requete)
        return vu

    def sonder():
        """La quatrième requête : celle qui n'installe rien et ne doit donc rien voir."""
        threads_vus.append(_identite_du_thread())
        requete = fabrique.get("/api/stock/")
        requete.user = _Principal(None)
        return hasattr(requete, "acces")

    original = module_middleware.acces_pour
    module_middleware.acces_pour = _resolveur
    try:
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            premier = pool.submit(servir, 11).result()
            second = pool.submit(servir, 22).result()
            anonyme = pool.submit(servir, None).result()
            residu = pool.submit(sonder).result()
        finally:
            pool.shutdown(wait=True)
    finally:
        module_middleware.acces_pour = original

    assert len(set(threads_vus)) == 1, (
        f"Les soumissions ont tourné sur {len(set(threads_vus))} threads différents. Un "
        "thread neuf démarre vierge et cacherait la fuite pour toujours ; le pool doit en "
        "réutiliser un seul, exactement comme le travailleur gthread de gunicorn."
    )

    assert premier == {"utilisateur_id": 11, "magasins": frozenset({11})}
    assert second == {"utilisateur_id": 22, "magasins": frozenset({22})}, (
        f"La deuxième requête sur le thread réutilisé a vu {second}. Elle doit voir "
        "l'accès de son propre principal ; voir celui du premier signifie que l'accès est "
        "rangé ailleurs que sur la requête."
    )
    assert anonyme == {"utilisateur_id": None, "magasins": frozenset()}, (
        f"La requête anonyme sur le thread réutilisé a vu {anonyme} — elle a hérité de "
        "l'accès d'un compte précédent, ce qui est l'élévation de privilèges la plus "
        "directe que cette couche puisse produire."
    )
    assert residu is False, (
        "Une requête qui n'est pas passée par le middleware porte quand même un attribut "
        "`acces`. Il vient donc d'ailleurs que de la requête."
    )

    # Trois résolutions pour trois requêtes : aucune mise en cache par utilisateur ni par
    # thread ne s'est glissée entre le middleware et le résolveur.
    assert appels == [11, 22, None]


def test_perm04_le_middleware_pose_le_vrai_acces_resolu(db_all, deux_magasins):
    """Le contrôle positif du test précédent : le middleware est branché sur `acces_pour`.

    Le test de fuite remplace le résolveur, donc il passerait contre un middleware branché
    sur n'importe quoi. Celui-ci ferme la boucle avec une vraie base, un vrai gérant et un
    vrai octroi : ce que la vue reçoit est exactement ce que `acces_pour` rend.
    """
    from django.test import RequestFactory

    from plateforme.comptes.acces import acces_pour
    from plateforme.comptes.middleware import AccesMiddleware
    from plateforme.comptes.permissions_catalogue import Permission
    from tests.factories import AccesMagasinFactory, DroitAccordeFactory, GerantFactory

    anfa, maarif = deux_magasins
    gerant = GerantFactory()
    for magasin in (anfa, maarif):
        AccesMagasinFactory(utilisateur=gerant, magasin_code=magasin.code)
    DroitAccordeFactory(
        utilisateur=gerant, magasin_code=anfa.code, code=Permission.STOCK_VOIR
    )

    vu = {}

    def vue(requete):
        vu["acces"] = requete.acces.peut(Permission.STOCK_VOIR, magasin_id=anfa.pk)
        vu["ailleurs"] = requete.acces.peut(Permission.STOCK_VOIR, magasin_id=maarif.pk)
        vu["objet"] = requete.acces.droits_par_magasin
        return "ok"

    requete = RequestFactory().get("/api/stock/")
    requete.user = gerant
    AccesMiddleware(vue)(requete)

    assert vu["acces"] is True
    assert vu["ailleurs"] is False
    assert dict(vu["objet"]) == dict(acces_pour(gerant).droits_par_magasin)
