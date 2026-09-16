"""PERM-06 — un registre, quatre consommateurs, un test paramétré.

Le problème à concevoir contre n'est pas « où vit le filtrage ». C'est « qu'est-ce qui
empêche trois rendus de diverger d'ici la phase 9 ». Une classe de base partagée ne
l'empêche pas : la phase 9 écrira un gabarit de facture contenant `{{ ligne.prix_achat }}`,
Django rendra une chaîne vide, et **rien ne le signalera** — ni exception, ni
avertissement, ni test. Le lien doit être énumérable, et le test doit itérer dessus.

D'où la forme du premier test, qui est le test porteur de toute la phase : il est
paramétré `CHAMPS_PROTEGES` × `{api, export, document}`. Ajouter une ligne au registre en
phase 8 produit **automatiquement** trois assertions, une par rendu. Ajouter un quatrième
rendu en phase 9 sans lui faire lire le registre le fait échouer dès qu'il rejoint la
liste `rendu`. C'est le test, et non l'abstraction, qui rend PERM-06 vrai.

`CHAMPS_PROTEGES` est **vide** en phase 3 et doit le rester : `prix_achat`, `marge` et le
chiffre d'affaires global naissent aux phases 8 et 10. La paramétrisation retombe donc sur
la **ressource de test** de `tests/ressources_fixture.py`, dont la docstring dit pourquoi
elle vit dans `tests/`. Un test paramétré sur zéro cas est vert et ne vaut rien.

**Ce que la phase 9 doit savoir, et c'est la seule chose qui empêche la dérive :** tout
nouveau rendu — le PDF A4 de WeasyPrint en tête — est ajouté à la liste `RENDUS`
ci-dessous, **dans le plan qui le crée**, et `_assertions_par_rendu` reçoit sa branche. Un
rendu qui n'y figure pas n'est vérifié par rien.

`test_perm06_aucun_modele_metier_n_est_enregistre_dans_ladmin` — le douzième nom de la
liste PERM-06 de `03-VALIDATION.md` — **n'est pas ici** : il est déjà implémenté et vert
dans `tests/test_comptes_socle.py`, depuis le plan 03-01, avec son contrôle positif.
"""

from __future__ import annotations

import pytest

from tests.ressources_fixture import (  # noqa: F401 — fixtures pytest, importées pour être disponibles
    CHAMPS_PUBLICS_DE_LA_FIXTURE,
    CLE_PROTEGEE,
    CODE_PROTEGE,
    NOM_TEMPLATE,
    PRIX_VENTE,
    VALEUR_PROTEGEE,
    RessourceFixture,
    SerializerRessourceFixture,
    VueRessourceFixture,
    acces_avec_le_droit,
    acces_sans_le_droit,
    registre_de_la_fixture,
    ressource,
    table_ressource_fixture,
)

#: La clé de repli de la paramétrisation, et la ressource de test qu'elle nomme.
#:
#: **Dérivée** des constantes de `tests/ressources_fixture.py` plutôt que recopiée : le
#: plan 03-02 l'avait écrite en dur (`"tests.RessourceFixture.valeur_protegee"`), ce qui
#: aurait laissé un renommage du champ transformer le test porteur de la phase en test
#: paramétré sur une clé que plus personne ne protège — donc vert, donc sans valeur.
CHAMP_DE_REPLI = (CLE_PROTEGEE, CODE_PROTEGE)

#: Les trois rendus qui doivent s'accorder. La phase 9 en ajoutera un quatrième (le PDF A4
#: de WeasyPrint) ; il rejoint cette liste, et les assertions apparaissent toutes seules.
RENDUS = ["api", "export", "document"]


def champs_proteges_parametres():
    """Les cas `(clé, code)` de la paramétrisation, avec repli tant que le registre est vide.

    Import **local et gardé**, délibérément : les arguments de `parametrize` sont évalués à
    l'import du module de test, donc un import au niveau du module transformerait l'absence
    du registre en erreur de collecte pour toute la suite.
    """
    try:
        from plateforme.projection.registre import CHAMPS_PROTEGES
    except ImportError:  # pragma: no cover — avant le plan 03-06
        return [CHAMP_DE_REPLI]
    return sorted(CHAMPS_PROTEGES.items()) or [CHAMP_DE_REPLI]


# --------------------------------------------------------------------------------------
# Les sujets : ce qu'il faut interroger pour une clé de registre donnée
# --------------------------------------------------------------------------------------
#: Une clé de registre ne dit ni quel sérialiseur l'expose, ni quelle ligne l'illustre. La
#: table ci-dessous fait ce lien, et c'est **la seule chose** qu'un plan de phase 8 ou 9 a
#: à ajouter pour que ses champs rejoignent le test porteur. Une clé sans sujet échoue avec
#: un message qui dit quoi écrire — un rouge précis plutôt qu'un silence.
def _sujet_pour(cle, instance_de_la_fixture):
    if cle == CLE_PROTEGEE:
        return SerializerRessourceFixture, instance_de_la_fixture
    pytest.fail(
        f"Le registre protège {cle!r} mais aucun sujet de test ne lui correspond. "
        "Ajoutez son sérialiseur et une instance à `_sujet_pour` dans le plan qui a "
        "ajouté la ligne de registre : sans cela, le champ est déclaré protégé et "
        "personne ne vérifie qu'il l'est."
    )


def _appeler(utilisateur, instance, *, methode="get", corps=None):
    """Une vraie requête : principal -> `AccesMiddleware` -> vue DRF -> JSON rendu.

    Passer par le middleware plutôt que de poser `request.acces` à la main est ce qui rend
    ce test *de bout en bout* : il échouerait si le middleware cessait de résoudre, comme
    il échoue si la projection cesse de projeter. La requête est jouée sans client HTTP —
    même idiome qu'au plan 03-05 — parce qu'un vrai client passerait par
    `TenantMiddleware`, qui exige une base client provisionnée.

    **`force_authenticate` est obligatoire ici, et la raison mérite d'être sue.** Le
    setter `Request.user` de DRF réécrit `self._request.user` ; une vue sans classe
    d'authentification y pose donc `AnonymousUser`, *après* le middleware. Comme
    `request.acces` est paresseux, il se résout plus tard et verrait cet
    `AnonymousUser` — donc `Acces.ANONYME`. En production la classe de session repose le
    même compte et rien ne bouge ; et le sens de l'erreur, le jour où DRF refuserait
    d'authentifier, est **fail-closed**. Mais un test qui ne force pas l'authentification
    verrait ses deux moitiés — gérant et propriétaire — devenir anonymes, donc son
    assertion d'absence passerait pour une raison fausse.
    """
    from rest_framework.test import APIRequestFactory, force_authenticate

    from plateforme.comptes.middleware import AccesMiddleware

    actions = {"get": "retrieve", "patch": "partial_update"}
    vue = VueRessourceFixture.as_view({methode: actions[methode]})
    fabrique = APIRequestFactory()
    chemin = f"/api/ressources-fixture/{instance.pk}/"
    requete = (
        fabrique.get(chemin)
        if methode == "get"
        else fabrique.patch(chemin, corps or {}, format="json")
    )
    requete.user = utilisateur
    force_authenticate(requete, user=utilisateur)
    reponse = AccesMiddleware(lambda recue: vue(recue, pk=instance.pk))(requete)
    reponse.render()
    return reponse


def _reponse_detail(utilisateur, instance):
    return _appeler(utilisateur, instance)


# --------------------------------------------------------------------------------------
# Le test porteur de la phase
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("rendu", RENDUS)
@pytest.mark.parametrize("cle,code", champs_proteges_parametres())
def test_perm06_champ_protege_absent_de_lapi_de_lexport_et_du_document(
    rendu, cle, code, db_all, deux_magasins, ressource
):
    """PERM-06 — le même champ, le même gérant, les trois rendus, une seule réponse.

    **Absent**, et non vide, et non nul, et non masqué à l'affichage : la clé n'est pas dans
    le JSON, la colonne n'est pas dans le CSV, le gabarit du document ne reçoit pas la
    valeur. Une valeur présente mais non affichée est disponible dans les outils de
    développement, dans une réponse en cache et dans le prochain refactor.

    Rouge sur un seul `rendu`, ce test nomme exactement celui qui a divergé — ce qui est
    toute la différence entre « la projection est cassée quelque part » et « l'export CSV de
    la phase 8 ne passe pas par le registre ».

    **Chaque branche porte son contrôle positif.** Un rendu qui n'imprimerait jamais rien
    satisfait « absent » trois fois sur trois ; les assertions sur le propriétaire sont ce
    qui distingue une projection d'une panne.

    Ce que ce test garantit pour la suite : une ligne ajoutée à `CHAMPS_PROTEGES` en phase 8
    devient trois assertions ici, sans qu'aucun développeur n'y pense. Il lui reste
    exactement une chose à écrire — l'entrée correspondante dans `_sujet_pour`, faute de
    quoi le test devient rouge en le disant.
    """
    classe_serializer, instance = _sujet_pour(cle, ressource)
    nom_du_champ = cle.rsplit(".", 1)[-1]
    valeur_rendue = str(VALEUR_PROTEGEE)

    _gerant, acces_gerant = acces_sans_le_droit(deux_magasins)
    proprietaire, acces_proprietaire = acces_avec_le_droit(deux_magasins)

    assert acces_gerant.peut(code) is False, (
        "Le gérant du test détient le code protégé : le test ne vérifierait rien."
    )
    assert acces_proprietaire.peut(code) is True, (
        "Le propriétaire du test ne détient pas le code protégé : le contrôle positif "
        "ne vaudrait rien."
    )

    if rendu == "api":
        reponse = _reponse_detail(_gerant, instance)
        assert reponse.status_code == 200
        assert nom_du_champ not in reponse.data, (
            f"La clé {nom_du_champ!r} est dans la charge utile servie à un gérant qui n'a "
            "pas le droit correspondant."
        )
        assert nom_du_champ.encode() not in reponse.rendered_content
        assert valeur_rendue.encode() not in reponse.rendered_content

        temoin = _reponse_detail(proprietaire, instance)
        assert nom_du_champ in temoin.data, (
            "Le propriétaire ne reçoit pas le champ protégé : la projection ne projette "
            "pas, elle supprime."
        )
        assert valeur_rendue.encode() in temoin.rendered_content

    elif rendu == "export":
        from plateforme.projection.export import exporter_csv

        lignes = RessourceFixture.objects.all()
        csv_gerant = exporter_csv(classe_serializer, lignes, acces=acces_gerant)
        entete = csv_gerant.splitlines()[0]
        assert nom_du_champ not in entete, (
            f"L'en-tête CSV porte la colonne {nom_du_champ!r}. Une colonne vide livre "
            "l'existence et la position du champ ; l'en-tête doit être dérivé des champs "
            "déjà projetés."
        )
        assert valeur_rendue not in csv_gerant

        temoin = exporter_csv(classe_serializer, lignes, acces=acces_proprietaire)
        assert nom_du_champ in temoin.splitlines()[0]
        assert valeur_rendue in temoin

    elif rendu == "document":
        from plateforme.projection.documents import contexte_document, rendre_html

        html_gerant = rendre_html(
            NOM_TEMPLATE,
            contexte_document(classe_serializer, instance, acces=acces_gerant),
        )
        assert nom_du_champ not in html_gerant
        assert valeur_rendue not in html_gerant, (
            "La valeur protégée apparaît dans le HTML rendu. C'est le mode de fuite que "
            "`string_if_invalid` cache : un champ absent et un champ mal orthographié se "
            "ressemblent, mais une valeur imprimée est imprimée."
        )
        # Le contrôle positif porte sur le prix public : le document rend bien quelque
        # chose, donc « absent » n'est pas « vide ».
        assert str(PRIX_VENTE) in html_gerant

        temoin = rendre_html(
            NOM_TEMPLATE,
            contexte_document(classe_serializer, instance, acces=acces_proprietaire),
        )
        assert valeur_rendue in temoin

    else:  # pragma: no cover — un rendu ajouté sans sa branche
        pytest.fail(
            f"Le rendu {rendu!r} est déclaré dans RENDUS mais n'a aucune assertion. "
            "Le plan qui ajoute un rendu ajoute sa branche ici, sinon la liste ment."
        )


# --------------------------------------------------------------------------------------
# Les échappatoires, une par attaque de la recherche
# --------------------------------------------------------------------------------------
def _sous_classes(classe):
    for fille in classe.__subclasses__():
        yield fille
        yield from _sous_classes(fille)


def test_perm06_tout_champ_de_modele_expose_est_classe(registre_de_la_fixture):
    """PERM-06 / A-03-08 — un champ non classé est un champ que personne n'a examiné.

    Le registre ne protège que ce qu'on y a inscrit, donc son mode de défaillance n'est pas
    la mauvaise entrée, c'est l'entrée **manquante**. La phase 6 imbriquera
    `ArticleSerializer` dans `LigneVenteSerializer` avec un `ModelSerializer` ordinaire et
    `prix_achat` réapparaîtra, sans que rien ne change dans le registre ni dans les tests
    existants.

    Ce test parcourt les sous-classes de `ModelSerializer` et exige que chaque champ exposé
    soit dans `CHAMPS_PROTEGES` ou dans `CHAMPS_PUBLICS`. « Public » est alors une décision
    écrite, datée et relisible, au lieu d'un silence. Rouge, il nomme le champ et le
    sérialiseur qui l'a introduit, le jour où il est introduit.

    L'énumération se fait sous `Acces.SCHEMA` : un sérialiseur interrogé sous un accès
    ordinaire aurait déjà perdu ses champs protégés, et le test passerait en n'examinant
    que la moitié publique — vert, et aveugle exactement là où il doit voir.
    """
    from rest_framework import serializers

    from plateforme.comptes.acces import Acces, _PorteurAcces
    from plateforme.projection import registre

    contexte = {"request": _PorteurAcces(acces=Acces.SCHEMA)}
    non_classes = []
    examines = 0

    for classe in _sous_classes(serializers.ModelSerializer):
        if classe.__module__.startswith("rest_framework"):
            continue
        modele = getattr(getattr(classe, "Meta", None), "model", None)
        if modele is None:
            continue
        champs = classe(context=contexte).fields
        for nom, champ in champs.items():
            source = champ.source or nom
            if "." in source or source == "*":
                continue
            try:
                modele._meta.get_field(source)
            except Exception:
                continue  # une propriété ou une méthode, pas une colonne
            examines += 1
            cle = registre.cle_de_champ(modele, source)
            if registre.est_classe(cle):
                continue
            non_classes.append(f"{classe.__name__}.{nom} -> {cle}")

    assert examines > 0, (
        "Aucun champ de modèle n'a été examiné. Le test est vacant — il passerait tout "
        "aussi bien contre une classification cassée."
    )
    assert not non_classes, (
        "Des champs de modèle sont exposés sans avoir été classés : "
        f"{sorted(non_classes)}. Inscrivez-les dans CHAMPS_PROTEGES ou dans "
        "CHAMPS_PUBLICS de plateforme/projection/registre.py — « public » est une "
        "décision, pas un défaut."
    )


def test_perm06_lacces_absent_vaut_aucun_droit(registre_de_la_fixture):
    """PERM-06 / P2 — la projection doit échouer **fermée**, comme le routeur (CLAUDE.md #8).

    `getattr(request, "acces", None)` suivi de `if acces is None: return fields` rend tous
    les champs protégés sur **tout** chemin où le middleware n'a pas tourné : une vue montée
    hors de la pile habituelle, une commande de gestion, un test, une tâche. Le défaut doit
    être `Acces.ANONYME` — ensemble de permissions vide — jamais `None`, et jamais « on
    laisse passer ».

    C'est le même raisonnement que le routeur qui lève au lieu de renvoyer `None` : un défaut
    permissif produit une fuite silencieuse, un défaut fermé produit une page vide qu'on
    remarque. Rouge, ce test dirait qu'un sérialiseur sans `request` dans son contexte rend
    les champs protégés.

    Les quatre formes d'absence sont éprouvées séparément, parce qu'elles empruntent quatre
    chemins différents dans `getattr` : pas de contexte du tout, un contexte vide, un
    contexte dont le `request` ne porte pas d'`acces`, et un `acces` explicitement `None`.
    """
    from plateforme.comptes.acces import Acces, _PorteurAcces

    nom = CLE_PROTEGEE.rsplit(".", 1)[-1]

    class _RequeteSansAcces:
        """Ce qu'est une requête sur un chemin où `AccesMiddleware` n'a pas tourné."""

    class _RequeteAvecAccesNul:
        acces = None

    for etiquette, contexte in (
        ("aucun contexte", None),
        ("contexte vide", {}),
        ("requête sans attribut acces", {"request": _RequeteSansAcces()}),
        ("acces explicitement None", {"request": _RequeteAvecAccesNul()}),
    ):
        serializer = (
            SerializerRessourceFixture()
            if contexte is None
            else SerializerRessourceFixture(context=contexte)
        )
        assert nom not in serializer.fields, (
            f"Avec {etiquette}, le champ protégé {nom!r} est exposé. Le défaut doit être "
            "`Acces.ANONYME`, jamais `None` et jamais « laisser passer »."
        )

    # Le contrôle positif : la projection retire le champ parce que le droit manque, pas
    # parce qu'elle retire tout.
    complet = SerializerRessourceFixture(
        context={"request": _PorteurAcces(acces=Acces.SCHEMA)}
    )
    assert nom in complet.fields


@pytest.mark.pending
def test_perm06_le_schema_est_identique_pour_le_proprietaire_et_le_gerant(db_all):
    """PERM-06 / A-03-09 — le schéma ne doit pas être un document par utilisateur.

    `build_mock_request` de drf-spectacular recopie `request.user` (vérifié,
    `plumbing.py:1288`), donc un schéma généré à la volée varie selon l'appelant : le gérant
    reçoit un document d'où `prix_achat` est absent, et le comparer à celui du propriétaire
    **énumère** les champs protégés. La fuite n'est pas la valeur, c'est la liste.

    Elle est doublement coûteuse : le client TypeScript est généré depuis ce schéma, donc un
    schéma qui varie produit des types qui varient, et la SPA cesse d'avoir un contrat.
    Rouge, ce test dirait que `GET_MOCK_REQUEST` n'épingle plus `Acces.SCHEMA`.
    """
    pytest.fail("non implémenté : plan 03-06")


@pytest.mark.pending
def test_perm06_un_champ_protege_est_optionnel_dans_le_schema():
    """PERM-06 / P9 — un champ protégé marqué `required` ment au client TypeScript.

    Le schéma est le contrat du client généré. Un champ protégé déclaré `required` promet
    une clé qui, pour un gérant, ne sera pas là : le type dit `prix_achat: string`, la valeur
    est `undefined`, et le bug se manifeste en phase 8 dans un composant qui n'a rien à voir.
    Le champ doit sortir du tableau `required` de son composant — par le post-traitement, pas
    par `COMPONENT_NO_READ_ONLY_REQUIRED = True`, qui est l'instrument brutal qui rendrait
    `id` optionnel du même coup.

    Rouge, ce test dirait que le hook de post-traitement a été retiré ou n'est plus branché.
    """
    pytest.fail("non implémenté : plan 03-06")


@pytest.mark.pending
def test_perm06_un_champ_protege_ne_peut_ni_trier_ni_filtrer(db_all, deux_magasins):
    """PERM-06 / A-03-07 — le champ n'est dans aucune réponse, et il est entièrement divulgué.

    `?ordering=prix_achat` révèle l'ordre total d'un champ caché ; `?prix_achat__gt=1500` en
    récupère la valeur exacte par dichotomie, en une vingtaine de requêtes. Le paramètre de
    requête est un oracle, et il n'a besoin d'aucune fuite de champ pour fonctionner.

    Un refus **silencieux** est aussi un oracle — l'ordre du résultat change selon que le
    champ a été accepté ou ignoré — donc la réponse attendue est **400**, pas « ignoré ». Les
    allowlists de tri et de filtre sont dérivées de la projection, jamais écrites à la main :
    une liste maintenue à part se désynchronise du registre à la première phase qui ajoute
    une colonne.
    """
    pytest.fail("non implémenté : plan 03-07")


@pytest.mark.pending
def test_perm06_un_champ_protege_ne_peut_pas_etre_ecrit_par_un_gerant(
    db_all, deux_magasins
):
    """PERM-06 — affirmer que la valeur est **inchangée**, jamais qu'un 400 survient.

    C'est la nuance qui décide si ce test vaut quelque chose. DRF ignore silencieusement une
    clé inconnue dans un corps de requête : si le champ est correctement retiré de la
    projection, un PATCH qui le nomme renvoie **200** et n'écrit rien. Un test qui attendrait
    400 serait donc rouge au-dessus d'un code parfaitement correct, et quelqu'un le
    « réparerait » en rendant le champ inscriptible.

    L'assertion est donc : la valeur relue depuis la base est celle d'avant. Rouge, elle dit
    qu'un gérant sans droit sur `prix_achat` peut le réécrire — donc fausser une marge que
    lui-même n'a pas le droit de lire.
    """
    pytest.fail("non implémenté : plan 03-06")


@pytest.mark.pending
def test_perm06_aucune_vue_ne_renvoie_un_values_queryset():
    """PERM-06 / A-03-04 — la faiblesse structurelle d'une projection par sérialiseur, énoncée.

    `Response(qs.values("prix_achat"))` et `qs.annotate(marge=F("pv") - F("pa"))` ne touchent
    **aucun** sérialiseur : la projection n'est pas contournée, elle est absente. Aucune
    classe de base ne peut rattraper cela, donc la garantie est un test au niveau du
    **source** — le même idiome que `tests/test_migration_conventions.py`, qui lit l'AST
    plutôt que d'exécuter.

    Un test au niveau du source est le bon outil ici précisément parce que le chemin fautif
    ne s'exécute jamais dans la suite : personne n'écrit un test pour la vue qu'il vient
    d'ajouter sans projection.
    """
    pytest.fail("non implémenté : plan 03-07")


@pytest.mark.pending
def test_perm06_le_renderer_html_est_absent_hors_developpement():
    """PERM-06 / A-03-06 — l'API navigable énumère des objets que l'appelant ne peut pas voir.

    Le renderer HTML de DRF dessine ses formulaires depuis `get_fields()`, qui **est**
    projeté — donc moins grave qu'il n'y paraît. Mais il rend aussi le `__str__` des objets
    liés dans les listes déroulantes, et une liste déroulante énumère des lignes. Un gérant
    d'un seul magasin y lit les noms des clients des autres.

    `DEFAULT_RENDERER_CLASSES` ne contient donc que le renderer JSON en base, et
    `BrowsableAPIRenderer` n'est ajouté que dans `local.py`. Rouge, ce test dirait qu'un
    réglage de confort posé pour déboguer est parti en production.
    """
    pytest.fail("non implémenté : plan 03-06")


@pytest.mark.pending
def test_perm06_toute_tache_de_rendu_exige_acting_utilisateur_id():
    """PERM-06 / A-03-03 — une tâche Celery sait de quel client, pas de qui.

    `TenantTask` reçoit `client_id` et relie le contexte : la tenancy est sauve. Mais un PDF
    ou un export rendus depuis une tâche n'ont **aucun** `request`, donc aucun `Acces`, donc
    rien qui distingue le propriétaire d'un gérant. Le rendu se fait par défaut — et le
    défaut, si personne ne le décide, est la vue complète, envoyée par e-mail au gérant qui
    l'a demandée.

    La signature est donc `(*, client_id, acting_utilisateur_id, ...)` et la tâche recalcule
    `acces_pour(...)` dans le contexte lié. Jamais un `Acces` ni une instance de modèle en
    argument — déjà interdit par la docstring de `TenantTask`. Ce test parcourt le registre
    des tâches et affirme sur les signatures : rouge, il nomme la tâche ajoutée sans le
    paramètre, à la phase où elle est ajoutée.
    """
    pytest.fail("non implémenté : plan 03-06")


@pytest.mark.pending
def test_perm06_le_catalogue_servi_a_un_gerant_manager_est_deja_intersecte(
    db_all, deux_magasins
):
    """PERM-06 / `03-UI-SPEC.md` §7.7 — « absent, pas désactivé », au niveau du fil.

    Un gérant qui détient `compte.gerer` administre ses collègues, et ne doit pas pouvoir
    accorder un droit qu'il ne détient pas lui-même, ni un accès à un magasin qu'il n'a pas.
    La tentation est de rendre ces lignes grisées — ce qui lui apprend que la permission
    existe et qu'elle lui manque — ou de les filtrer dans le navigateur, ce qui les laisse
    dans la réponse.

    Le point de terminaison du catalogue sert donc à chaque appelant un catalogue **déjà
    intersecté** avec ses propres droits et magasins : un code qu'il ne détient pas est
    absent du JSON, exactement comme un champ non autorisé est absent d'une ligne. Le client
    rend ce qu'il reçoit et n'a aucune branche de filtrage à lui, donc rien à faire fuir par
    un cache, un outil de développement ou un refactor à venir (`03-UI-CHECK.md`,
    recommandation sur §7.7).
    """
    pytest.fail("non implémenté : plan 03-09")
