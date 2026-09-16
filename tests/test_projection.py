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

#: Les rendus qui doivent s'accorder. La phase 9 en ajoutera un autre (le PDF A4 de
#: WeasyPrint) ; il rejoint cette liste, et les assertions apparaissent toutes seules.
#:
#: **`catalogue` est le quatrième, ajouté par le plan 03-09**, et `03-UI-SPEC.md` 7.7 le
#: demande en toutes lettres : « The same parametrized conformance test that covers field
#: projection covers this catalogue. » Il n'est pas un rendu de *champ* comme les trois
#: autres — il ne sert pas une ressource, il sert la liste des droits **offrables** — mais
#: il lit le même registre par l'autre bout : une clé de `CHAMPS_PROTEGES` nomme un code,
#: et un éditeur qui ne détient pas ce code ne doit pas le voir dans son catalogue. Une
#: ligne ajoutée au registre en phase 8 produit donc quatre assertions, et la
#: recommandation de fond du `03-UI-CHECK.md` cesse d'être une convention.
RENDUS = ["api", "export", "document", "catalogue"]


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

    elif rendu == "catalogue":
        import json

        from plateforme.comptes.serializers import catalogue_offrable

        # Le registre lu par l'autre bout : la clé nomme un champ, `code` nomme le droit
        # qui le garde. Un éditeur qui ne détient pas ce droit ne peut pas l'accorder,
        # donc il ne doit pas le lire dans son catalogue (`03-UI-SPEC.md` 7.7).
        #
        # L'assertion porte sur le **JSON sérialisé** et non sur le dictionnaire, pour la
        # même raison que les trois branches ci-dessus : « absent » se vérifie sur ce qui
        # part sur le fil.
        servi = json.dumps(catalogue_offrable(acces_gerant, []), ensure_ascii=False)
        assert code not in servi, (
            f"Le code {code!r} est dans le catalogue servi à un éditeur qui ne le "
            "détient pas. Le filtrer côté client laisserait la liste des codes cachés "
            "dans la réponse, ce qui est la recommandation de fond du 03-UI-CHECK.md."
        )

        temoin = json.dumps(
            catalogue_offrable(acces_proprietaire, []), ensure_ascii=False
        )
        assert code in temoin, (
            "Le propriétaire ne reçoit pas le code dans son catalogue : l'intersection "
            "ne sert rien à personne, et l'assertion d'absence ci-dessus ne prouve rien."
        )

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


def _mock_naif(method, path, view, original_request, **kwargs):
    """La faute que `requete_mock_schema` existe pour empêcher, écrite en trois lignes.

    `build_mock_request` recopie `request.user` de l'appelant (`plumbing.py:1288`) ; en
    résoudre l'accès est donc l'implémentation que quelqu'un écrit naturellement, et elle
    produit **un schéma par utilisateur**. Ce faux est le contrôle qui rend le test
    d'identité octet-pour-octet autre chose qu'une tautologie.
    """
    from drf_spectacular.plumbing import build_mock_request

    from plateforme.comptes.acces import acces_pour

    requete = build_mock_request(method, path, view, original_request, **kwargs)
    requete.acces = acces_pour(requete.user)
    return requete


def _schema_servi(utilisateur, reglages, *, vue=None):
    """Le document que `/api/schema/` rendrait à cet utilisateur, en octets."""
    from drf_spectacular.views import SpectacularAPIView
    from rest_framework.test import APIRequestFactory, force_authenticate

    reglages.ROOT_URLCONF = "tests.ressources_fixture"
    classe = vue or SpectacularAPIView
    requete = APIRequestFactory().get("/api/schema/")
    requete.user = utilisateur
    force_authenticate(requete, user=utilisateur)
    reponse = classe.as_view()(requete)
    reponse.render()
    return reponse.content


def test_perm06_le_schema_est_identique_pour_le_proprietaire_et_le_gerant(
    db_all, deux_magasins, registre_de_la_fixture, settings
):
    """PERM-06 / A-03-09 — le schéma ne doit pas être un document par utilisateur.

    `build_mock_request` de drf-spectacular recopie `request.user` (vérifié,
    `plumbing.py:1288`), donc un schéma généré à la volée varie selon l'appelant : le gérant
    reçoit un document d'où `prix_achat` est absent, et le comparer à celui du propriétaire
    **énumère** les champs protégés. La fuite n'est pas la valeur, c'est la liste.

    Elle est doublement coûteuse : le client TypeScript est généré depuis ce schéma, donc un
    schéma qui varie produit des types qui varient, et la SPA cesse d'avoir un contrat.
    Rouge, ce test dirait que `GET_MOCK_REQUEST` n'épingle plus `Acces.SCHEMA`.

    **Deux contrôles, parce que l'égalité seule est facile à satisfaire par accident.**

    1. Sans épinglage du tout (`build_mock_request` d'origine), la requête mock ne porte
       aucun `acces`, donc la projection retombe fail-closed sur `Acces.ANONYME` et le
       document perd le champ protégé **pour tout le monde**. Deux schémas égaux, et tous
       deux faux : c'est le committé qui cesserait de correspondre au servi.
    2. Avec l'épinglage naïf — résoudre l'accès de l'appelant, ce que la recopie de
       `request.user` invite à écrire — les deux documents **diffèrent**. C'est la fuite
       que A-03-09 décrit, reproduite ici pour que l'assertion d'égalité ait un contraire.
    """
    proprietaire, _ = acces_avec_le_droit(deux_magasins)
    gerant, acces_gerant = acces_sans_le_droit(deux_magasins)
    assert acces_gerant.peut(CODE_PROTEGE) is False

    nom = CLE_PROTEGEE.rsplit(".", 1)[-1].encode()

    du_proprietaire = _schema_servi(proprietaire, settings)
    du_gerant = _schema_servi(gerant, settings)

    assert du_proprietaire == du_gerant, (
        "Le schéma servi diffère selon l'appelant. Le client TypeScript est généré "
        "depuis ce document : un schéma par utilisateur n'est plus un contrat, et "
        "comparer les deux énumère les champs protégés."
    )
    assert nom in du_proprietaire, (
        "Le champ protégé est absent du schéma servi. « Identiques » voudrait alors dire "
        "« tous deux amputés », et le schéma commité ne décrirait plus l'API."
    )

    from drf_spectacular.views import SpectacularAPIView

    class _VueSansEpinglage(SpectacularAPIView):
        custom_settings = {
            "GET_MOCK_REQUEST": "drf_spectacular.plumbing.build_mock_request"
        }

    class _VueNaive(SpectacularAPIView):
        custom_settings = {"GET_MOCK_REQUEST": _mock_naif}

    sans_epinglage = _schema_servi(proprietaire, settings, vue=_VueSansEpinglage)
    assert nom not in sans_epinglage, (
        "Sans `GET_MOCK_REQUEST`, le champ protégé est quand même décrit : la projection "
        "ne s'applique donc pas au schéma, et ce test ne prouve rien."
    )

    naif_proprietaire = _schema_servi(proprietaire, settings, vue=_VueNaive)
    naif_gerant = _schema_servi(gerant, settings, vue=_VueNaive)
    assert naif_proprietaire != naif_gerant, (
        "Même en résolvant l'accès de l'appelant, les deux schémas sont identiques : le "
        "contrôle ne contrôle rien, et l'assertion d'égalité ci-dessus est vide."
    )


def test_perm06_un_champ_protege_est_optionnel_dans_le_schema(
    registre_de_la_fixture, settings
):
    """PERM-06 / P9 — un champ protégé marqué `required` ment au client TypeScript.

    Le schéma est le contrat du client généré. Un champ protégé déclaré `required` promet
    une clé qui, pour un gérant, ne sera pas là : le type dit `prix_achat: string`, la valeur
    est `undefined`, et le bug se manifeste en phase 8 dans un composant qui n'a rien à voir.
    Le champ doit sortir du tableau `required` de son composant — par le post-traitement, pas
    par le réglage global qui rendrait **tous** les champs en lecture seule optionnels,
    `id` compris — un mensonge bien pire, et l'instrument brutal là où le crochet est
    chirurgical.

    Rouge, ce test dirait que le hook de post-traitement a été retiré ou n'est plus branché.

    Trois assertions, et la troisième est celle qui distingue le crochet du réglage global :
    la propriété **est** décrite, elle n'est **pas** requise, et `id` — en lecture seule —
    l'est toujours.
    """
    from drf_spectacular.generators import SchemaGenerator
    from drf_spectacular.settings import patched_settings

    settings.ROOT_URLCONF = "tests.ressources_fixture"
    nom = CLE_PROTEGEE.rsplit(".", 1)[-1]

    resultat = SchemaGenerator().get_schema(request=None, public=True)
    composants = resultat["components"]["schemas"]

    porteurs = {
        titre: schema
        for titre, schema in composants.items()
        if nom in (schema.get("properties") or {})
    }
    assert porteurs, (
        f"Aucun composant ne décrit {nom!r}. Le schéma ne décrit donc pas l'API, et "
        "l'assertion sur `required` porterait sur rien."
    )
    for titre, schema in porteurs.items():
        assert nom not in schema.get("required", []), (
            f"Le composant {titre} déclare {nom!r} comme requis. Le TypeScript généré "
            f"promet alors une clé qui, pour un gérant, ne sera pas là."
        )

    avec_id = [t for t, s in porteurs.items() if "id" in s.get("required", [])]
    assert avec_id, (
        "Aucun composant ne requiert `id`. Le crochet n'est donc pas chirurgical — ou "
        "quelqu'un a basculé le réglage global qui rend tout champ en lecture seule "
        "optionnel, ce qui est le mensonge que ce test existe pour refuser."
    )

    # Le contrôle : sans le crochet, le champ protégé **est** requis. Sinon ce test
    # passerait aussi bien contre un post-traitement débranché.
    with patched_settings(
        {"POSTPROCESSING_HOOKS": ["drf_spectacular.hooks.postprocess_schema_enums"]}
    ):
        sans_crochet = SchemaGenerator().get_schema(request=None, public=True)
    requis_sans_crochet = [
        titre
        for titre, schema in sans_crochet["components"]["schemas"].items()
        if nom in schema.get("required", [])
    ]
    assert requis_sans_crochet, (
        "Sans le crochet de post-traitement, le champ protégé n'est déjà pas requis. Le "
        "crochet ne fait donc rien et l'assertion principale est vide."
    )


def test_perm06_le_reglage_global_de_required_reste_a_son_defaut(registre_de_la_fixture):
    """PERM-06 / P9 — le crochet est précis, l'interrupteur global ne l'est pas.

    `drf-spectacular` calcule `required = field.required or (readOnly and not <réglage>)`.
    Basculer ce réglage retirerait de `required` **tous** les champs en lecture seule,
    `id` le premier : le client TypeScript déclarerait alors `id?: number` sur chaque
    ressource, et chaque site d'appel devrait traiter l'absence d'une clé qui est toujours
    là. C'est un mensonge plus large que celui qu'on répare.

    Le nom du réglage est donc absent de `config/settings/` — un réglage qu'on ne nomme pas
    est un réglage que personne ne bascule « pour voir ».
    """
    from pathlib import Path

    from drf_spectacular.settings import spectacular_settings

    assert spectacular_settings.COMPONENT_NO_READ_ONLY_REQUIRED is False

    fautifs = [
        chemin.name
        for chemin in sorted(Path("config/settings").glob("*.py"))
        if "COMPONENT_NO_READ_ONLY_REQUIRED" in chemin.read_text(encoding="utf-8")
    ]
    assert not fautifs, (
        f"Le réglage global est nommé dans {fautifs}. Le retirer du fichier est la "
        "moitié du garde : ce qui n'est pas écrit ne se bascule pas par curiosité."
    )


def test_perm06_un_champ_protege_ne_peut_ni_trier_ni_filtrer(
    db_all, deux_magasins, ressource
):
    """PERM-06 / A-03-07 — le champ n'est dans aucune réponse, et il est entièrement divulgué.

    `?ordering=prix_achat` révèle l'ordre total d'un champ caché ; `?prix_achat__gt=1500` en
    récupère la valeur exacte par dichotomie, en une vingtaine de requêtes. Le paramètre de
    requête est un oracle, et il n'a besoin d'aucune fuite de champ pour fonctionner.

    Un refus **silencieux** est aussi un oracle — l'ordre du résultat change selon que le
    champ a été accepté ou ignoré — donc la réponse attendue est **400**, pas « ignoré ». Les
    allowlists de tri et de filtre sont dérivées de la projection, jamais écrites à la main :
    une liste maintenue à part se désynchronise du registre à la première phase qui ajoute
    une colonne.

    **Le contrôle positif est la moitié qui compte.** Un backend qui refuserait tout
    passerait les deux premières assertions. Le propriétaire, qui détient le droit, doit
    obtenir **200** sur exactement les mêmes requêtes — et le gérant doit obtenir 200 sur
    un champ public, sans quoi « 400 » ne voudrait dire que « ce point de terminaison est
    cassé ».
    """
    from tests.ressources_fixture import appeler_vue_filtrable

    gerant, acces_gerant = acces_sans_le_droit(deux_magasins)
    assert acces_gerant.peut(CODE_PROTEGE) is False

    trie = appeler_vue_filtrable(gerant, "?ordering=valeur_protegee")
    assert trie.status_code == 400, (
        f"`?ordering=valeur_protegee` a répondu {trie.status_code}. Un 200 divulgue "
        "l'ordre total d'un champ que ce gérant n'a pas le droit de lire — et il le fait "
        "sans que le champ apparaisse dans une seule réponse."
    )

    filtre = appeler_vue_filtrable(gerant, "?valeur_protegee__gt=1000")
    assert filtre.status_code == 400, (
        f"`?valeur_protegee__gt=1000` a répondu {filtre.status_code}. En une vingtaine de "
        "requêtes de cette forme, la valeur exacte se retrouve par dichotomie."
    )

    # Le contrôle positif, côté droit détenu : les **mêmes** requêtes, pour qui peut.
    proprietaire, acces_proprietaire = acces_avec_le_droit(deux_magasins)
    assert acces_proprietaire.peut(CODE_PROTEGE) is True
    for chaine in ("?ordering=valeur_protegee", "?valeur_protegee__gt=1000"):
        permis = appeler_vue_filtrable(proprietaire, chaine)
        assert permis.status_code == 200, (
            f"{chaine} a répondu {permis.status_code} au propriétaire : {permis.data}. "
            "Un backend qui refuse tout passerait les assertions de refus ci-dessus sans "
            "rien garantir."
        )

    # Le contrôle positif, côté champ public : le gérant trie et filtre ce qu'il peut voir.
    for chaine in ("?ordering=prix_vente", "?prix_vente__gt=1.00"):
        ouvert = appeler_vue_filtrable(gerant, chaine)
        assert ouvert.status_code == 200, (
            f"{chaine} a répondu {ouvert.status_code} : {ouvert.data}. Le champ est "
            "public et déclaré filtrable ; refuser ici ne protège rien et casse l'API."
        )


def test_perm06_le_400_de_tri_ne_nomme_pas_le_champ_protege(
    db_all, deux_magasins, ressource
):
    """PERM-06 / A-03-13 — un 400 dont les clés nomment le champ est la même fuite, en deux temps.

    Refuser sans dire pourquoi paraît désobligeant, et c'est pourtant la seule réponse
    correcte : « le champ `valeur_protegee` n'est pas triable » confirme que le champ
    existe, ce que la projection passe tout son temps à ne pas dire.

    L'assertion forte n'est pas « le nom est absent » — elle est **l'indiscernabilité**.
    Un champ protégé, un champ public non déclaré filtrable et un nom qui n'existe nulle
    part doivent produire **exactement** la même réponse. Sinon le code de statut, la
    forme du corps ou la longueur du message redeviennent l'oracle, et l'attaque coûte une
    requête de plus au lieu d'être impossible.
    """
    import json

    from tests.ressources_fixture import appeler_vue_filtrable

    gerant, _ = acces_sans_le_droit(deux_magasins)

    protege = appeler_vue_filtrable(gerant, "?ordering=valeur_protegee")
    corps = json.dumps(protege.data, default=str)
    assert "valeur_protegee" not in corps, (
        f"Le corps du 400 nomme le champ protégé : {corps}. Le refus confirme alors "
        "l'existence du champ, ce qui est la fuite avec une étape de plus (A-03-13)."
    )

    inexistant = appeler_vue_filtrable(gerant, "?ordering=champ_qui_n_existe_pas")
    public_non_declare = appeler_vue_filtrable(gerant, "?libelle__gt=a")

    assert inexistant.status_code == protege.status_code == 400
    assert inexistant.data == protege.data, (
        "Le refus d'un champ protégé se distingue du refus d'un nom inexistant. La "
        "différence *est* l'oracle : elle répond « ce champ existe » en une requête."
    )
    assert public_non_declare.status_code == 400
    assert public_non_declare.data == protege.data


def test_perm06_un_champ_protege_ne_peut_pas_etre_ecrit_par_un_gerant(
    db_all, deux_magasins, ressource
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

    Le **contrôle positif** est le champ public modifié dans la même requête : sans lui, une
    vue qui ignorerait complètement le corps de la requête passerait ce test.
    """
    gerant, acces_gerant = acces_sans_le_droit(deux_magasins)
    assert acces_gerant.peut(CODE_PROTEGE) is False

    avant = ressource.valeur_protegee

    reponse = _appeler(
        gerant,
        ressource,
        methode="patch",
        corps={"libelle": "Monture Maârif", "valeur_protegee": "1.00"},
    )

    assert reponse.status_code == 200, (
        f"Le PATCH a répondu {reponse.status_code} : {reponse.data}. DRF ignore une clé "
        "inconnue, donc la réponse attendue est un succès — un test qui attendrait 400 "
        "serait rouge au-dessus d'un code correct, et quelqu'un le « réparerait » en "
        "rendant le champ inscriptible."
    )

    relu = RessourceFixture.objects.get(pk=ressource.pk)
    assert relu.valeur_protegee == avant, (
        "Un gérant sans le droit de **lire** la valeur protégée vient de l'écrire. Il "
        "peut donc fausser une marge qu'il n'a pas le droit de voir."
    )
    assert relu.libelle == "Monture Maârif", (
        "Le champ public n'a pas été écrit non plus : la requête n'a rien fait du tout, "
        "et l'assertion d'invariance ci-dessus ne prouve rien."
    )


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

    **Le contrôle négatif est obligatoire ici**, et plus qu'ailleurs : un détecteur de
    source qui ne détecterait rien passerait ce test pour toujours, et il passerait aussi
    le jour où la phase 8 écrit la ligne fautive. Le cas synthétique ci-dessous est donc
    passé au même détecteur, par le même chemin.
    """
    import textwrap

    from plateforme.projection.checks import (
        modules_de_vues,
        retours_values_queryset,
    )

    modules = modules_de_vues()
    assert modules, (
        "Aucun module de vues trouvé. Le test est vacant : il passerait tout aussi bien "
        "au-dessus d'une vue qui sert un values queryset."
    )

    fautifs = retours_values_queryset(modules)
    assert not fautifs, (
        f"Des vues renvoient un values queryset : {fautifs}. Ce chemin ne touche aucun "
        "sérialiseur, donc la projection n'y est pas contournée — elle est absente. "
        "Passez par un sérialiseur, ou par une méthode de queryset qui prend l'accès."
    )

    # Le contrôle négatif : quatre formes de la même faute, et le détecteur doit voir les
    # quatre. Écrites ici plutôt que dans un fichier de fixture pour qu'elles se lisent
    # à côté de l'assertion qu'elles justifient.
    fautif = textwrap.dedent(
        """
        from rest_framework.response import Response

        class Vue:
            def direct(self, requete):
                return Response(Article.objects.values("prix_achat"))

            def chaine(self, requete):
                return Response(self.get_queryset().filter(x=1).values_list("marge"))

            def par_variable(self, requete):
                lignes = Article.objects.values("prix_achat")
                return Response(lignes)

            def enveloppe(self, requete):
                return Response(list(Article.objects.values("prix_achat")))
        """
    )
    detectes = retours_values_queryset([("synthetique.py", fautif)])
    assert len(detectes) == 4, (
        f"Le détecteur a vu {len(detectes)} fautes sur quatre : {detectes}. Un détecteur "
        "qui ne détecte pas est un test vert et vide — exactement la forme de garantie "
        "que ce plan existe pour refuser."
    )


def test_perm06_enumeration_tout_serializer_exposant_un_champ_protege_est_projete(
    registre_de_la_fixture,
):
    """PERM-06 / A-03-08 — le jumeau, côté champs : un champ du registre exige la projection.

    `test_perm06_tout_champ_de_modele_expose_est_classe` exige qu'un champ soit **classé**.
    Celui-ci exige, du champ déjà classé protégé, qu'il soit servi par un sérialiseur qui
    lit le registre. Les deux ensemble ferment A-03-08 : la phase 6 imbriquera
    `ArticleSerializer` dans `LigneVenteSerializer`, et un `ModelSerializer` ordinaire y
    ressusciterait `prix_achat` sans que rien ne change ni dans le registre, ni dans les
    tests existants.

    Le garde est **une fonction pure prenant une liste**, pas une boucle écrite dans le
    test : c'est ce qui permet de lui passer le cas fautif ci-dessous sans le déclarer au
    niveau du module, où il polluerait `__subclasses__()` pour toute la session.
    """
    from rest_framework import serializers

    from plateforme.projection.checks import (
        serializers_sans_projection,
        tous_les_serializers,
    )

    examines = tous_les_serializers()
    assert examines, "Aucun ModelSerializer chargé : le garde n'examinerait rien."

    fautifs = serializers_sans_projection(examines)
    assert not fautifs, (
        f"Des sérialiseurs exposent un champ du registre sans lire le registre : "
        f"{fautifs}. Héritez de `SerializerProjete` — ou, si le champ ne doit plus être "
        "protégé, retirez sa ligne du registre. Les deux sont des décisions ; l'oubli "
        "n'en est pas une."
    )

    # Le contrôle négatif : exactement la faute que la phase 6 commettra.
    class SerializerNonProjete(serializers.ModelSerializer):
        class Meta:
            model = RessourceFixture
            fields = ["id", "valeur_protegee"]

    detectes = serializers_sans_projection([SerializerNonProjete])
    assert len(detectes) == 1, (
        f"Le garde n'a pas vu le sérialiseur non projeté : {detectes}. Sans ce contrôle "
        "il serait vert au-dessus de l'exacte régression qu'il surveille."
    )


def test_perm06_le_renderer_html_est_absent_hors_developpement():
    """PERM-06 / A-03-06 — l'API navigable énumère des objets que l'appelant ne peut pas voir.

    Le renderer HTML de DRF dessine ses formulaires depuis `get_fields()`, qui **est**
    projeté — donc moins grave qu'il n'y paraît. Mais il rend aussi le `__str__` des objets
    liés dans les listes déroulantes, et une liste déroulante énumère des lignes. Un gérant
    d'un seul magasin y lit les noms des clients des autres.

    `DEFAULT_RENDERER_CLASSES` ne contient donc que le renderer JSON en base, et
    `BrowsableAPIRenderer` n'est ajouté que dans `local.py`. Rouge, ce test dirait qu'un
    réglage de confort posé pour déboguer est parti en production.

    L'assertion porte sur le **source** des modules de configuration, pas sur leur import :
    importer `config/settings/production.py` poserait `sslmode=require` dans le `DATABASES`
    partagé avec les réglages de test — le module y mute le dictionnaire de `base`, qui est
    le même objet — et casserait toutes les connexions des tests suivants. Un test qui
    casse la suite pour vérifier une chaîne de caractères n'est pas un bon marché.
    """
    from pathlib import Path

    from rest_framework.settings import api_settings

    modules = sorted(Path("config/settings").glob("*.py"))
    avec_navigable = [
        chemin.name
        for chemin in modules
        if "BrowsableAPIRenderer" in chemin.read_text(encoding="utf-8")
    ]
    assert avec_navigable == ["local.py"], (
        f"`BrowsableAPIRenderer` apparaît dans {avec_navigable}. Il n'a sa place que dans "
        "`local.py` : ses listes déroulantes énumèrent les objets liés, donc les lignes "
        "d'autres magasins et les clients d'autres gérants."
    )

    # Et le réglage effectif de la suite — qui hérite de `base` — ne le porte pas.
    effectifs = [classe.__name__ for classe in api_settings.DEFAULT_RENDERER_CLASSES]
    assert effectifs == ["JSONRenderer"], (
        f"Les renderers effectifs sont {effectifs}. La base ne doit servir que du JSON."
    )


#: Les trois portes d'entrée de la projection hors HTTP. Une fonction qui appelle l'une
#: d'elles **produit un artefact destiné au client**, par définition : c'est ce qui rend la
#: détection ci-dessous énumérable plutôt que nominative. Une tâche de la phase 9 qui
#: rendrait un PDF par ces fonctions est attrapée sans qu'on ait à la connaître.
POINTS_DE_RENDU = ("exporter_csv", "contexte_document", "rendre_html")


def _appelle_un_point_de_rendu(fonction) -> bool:
    """Vrai si le source de `fonction` appelle l'un des `POINTS_DE_RENDU`.

    Lecture de l'AST plutôt qu'exécution, même idiome que
    `tests/test_migration_conventions.py` : le chemin fautif ne s'exécute jamais dans la
    suite, puisque personne n'écrit un test pour la tâche qu'il vient d'ajouter sans
    projection.
    """
    import ast
    import inspect
    import textwrap

    try:
        source = textwrap.dedent(inspect.getsource(fonction))
    except (OSError, TypeError):  # une tâche built-in de Celery, sans source lisible
        return False
    try:
        arbre = ast.parse(source)
    except SyntaxError:  # pragma: no cover
        return False
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        nom = getattr(noeud.func, "id", None) or getattr(noeud.func, "attr", None)
        if nom in POINTS_DE_RENDU:
            return True
    return False


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

    **« Tâche de rendu » est défini par ce qu'elle appelle, pas par son nom.** Une
    convention de nommage se contourne sans le vouloir ; « appelle `exporter_csv`,
    `contexte_document` ou `rendre_html` » est vérifiable et c'est exactement la propriété
    qui compte. La limite est nommée dans le résumé du plan : une tâche de phase 9 qui
    appellerait WeasyPrint sans passer par ces trois portes échapperait à ce garde — c'est
    la liste `RENDUS` du test porteur qui couvre ce cas-là, et les deux règles doivent être
    tenues ensemble.
    """
    import inspect

    from config.celery import app as application_celery

    def _sans_le_parametre(fonction) -> bool:
        return "acting_utilisateur_id" not in inspect.signature(fonction).parameters

    # Le contrôle négatif d'abord : une tâche fautive **doit** être détectée, sinon tout
    # ce qui suit est une boucle qui ne voit rien.
    def _tache_fautive(*, client_id, **kwargs):
        from plateforme.projection.export import exporter_csv

        return exporter_csv(None, None, acces=None)

    assert _appelle_un_point_de_rendu(_tache_fautive), (
        "Le détecteur ne reconnaît pas une tâche qui appelle `exporter_csv`. Il ne "
        "détecterait donc rien du tout, et ce test serait vert pour toujours."
    )
    assert _sans_le_parametre(_tache_fautive)

    taches_de_rendu = {}
    for nom, tache in application_celery.tasks.items():
        fonction = getattr(tache, "run", tache)
        if _appelle_un_point_de_rendu(fonction):
            taches_de_rendu[nom] = fonction

    assert taches_de_rendu, (
        "Aucune tâche de rendu n'est enregistrée. Ce test est vacant : il passerait tout "
        "aussi bien le jour où la phase 9 en ajoute une sans `acting_utilisateur_id`. "
        "`tests.exporter_ressources_fixture` est là pour l'empêcher — si elle a disparu "
        "du registre, c'est ce qu'il faut réparer, pas cette assertion."
    )

    fautives = sorted(nom for nom, f in taches_de_rendu.items() if _sans_le_parametre(f))
    assert not fautives, (
        f"Ces tâches produisent un artefact destiné au client sans savoir pour qui : "
        f"{fautives}. La signature est `(*, client_id, acting_utilisateur_id, ...)` et la "
        "tâche recalcule `acces_pour(...)` dans le contexte lié — jamais un `Acces` reçu "
        "en argument."
    )


def test_perm06_len_tete_csv_est_derive_des_champs_deja_projetes(
    db_all, deux_magasins, ressource
):
    """PERM-06 — la colonne n'existe pas, elle n'est pas vide. C'est tout l'export.

    Une liste de colonnes écrite à la main produirait une **colonne vide** : « absent d'un
    export » échouerait dans l'esprit, et le gérant apprendrait l'existence et la position
    du champ. Dériver l'en-tête de `serializer.child.fields` — donc des champs **déjà**
    projetés — est la seule forme où cette erreur n'est pas exprimable.

    Le test le vérifie deux fois : sur la valeur (l'en-tête est exactement la liste des
    champs projetés) et sur le source (`child.fields` y figure), parce qu'un en-tête
    correct peut être obtenu par une coïncidence que la phase suivante défera.
    """
    import inspect

    from plateforme.comptes.acces import _PorteurAcces
    from plateforme.projection.export import BOM_UTF8, SEPARATEUR, exporter_csv

    _gerant, acces_gerant = acces_sans_le_droit(deux_magasins)
    contenu = exporter_csv(
        SerializerRessourceFixture, RessourceFixture.objects.all(), acces=acces_gerant
    )

    assert contenu.startswith(BOM_UTF8), (
        "L'export ne commence pas par un BOM UTF-8. Excel en français ouvre alors les "
        "accents en mojibake."
    )
    lignes = contenu[len(BOM_UTF8) :].splitlines()
    colonnes = lignes[0].split(SEPARATEUR)

    attendues = list(
        SerializerRessourceFixture(
            context={"request": _PorteurAcces(acces=acces_gerant)}
        ).fields
    )
    assert colonnes == attendues, (
        f"L'en-tête CSV {colonnes} ne correspond pas aux champs projetés {attendues}."
    )
    assert len(lignes[1].split(SEPARATEUR)) == len(colonnes), (
        "La ligne de données n'a pas le même nombre de champs que l'en-tête : une "
        "colonne a été écrite d'un côté et pas de l'autre."
    )
    assert "child.fields" in inspect.getsource(exporter_csv), (
        "`exporter_csv` ne dérive plus ses colonnes de `serializer.child.fields`. "
        "Une liste écrite à la main rend une colonne vide au lieu de rien."
    )


def test_perm06_le_gabarit_de_document_itere_une_liste_projetee():
    """PERM-06 / P10 — un gabarit qui nomme un champ le rend, ou rend le vide, en silence.

    Une clé absente d'un contexte de gabarit rend `string_if_invalid`, qui vaut `""` par
    défaut : un champ **caché** et un champ **mal orthographié** ont donc exactement la
    même apparence correcte. Corriger cela en changeant `string_if_invalid` globalement est
    refusé — la documentation de Django avertit que cela casse `{% if %}` sur les valeurs
    optionnelles, et le réglage est absent de tous les modules de configuration.

    La correction est structurelle : les gabarits de documents **itèrent** une liste de
    colonnes déjà projetée et ne nomment aucun champ en ligne. Ce test l'exige sur le
    source de chaque gabarit de `plateforme/projection/templates/`, parce qu'un gabarit
    correct aujourd'hui et fautif en phase 9 ne se verrait nulle part ailleurs.
    """
    import re
    from pathlib import Path

    racine = Path("plateforme/projection/templates")
    gabarits = sorted(racine.rglob("*.html"))
    assert gabarits, f"Aucun gabarit trouvé sous {racine} — le test est vacant."

    nomme_un_champ = re.compile(r"\{\{\s*[a-z_]+\.[a-z_]+\s*\}\}")
    fautifs = []
    for gabarit in gabarits:
        contenu = gabarit.read_text(encoding="utf-8")
        for occurrence in nomme_un_champ.findall(contenu):
            fautifs.append(f"{gabarit}: {occurrence}")
        assert "{% for" in contenu, (
            f"{gabarit} n'itère rien. Un gabarit de document rend une liste de colonnes "
            "projetée ; s'il n'itère pas, c'est qu'il nomme."
        )

    assert not fautifs, (
        f"Des gabarits nomment un champ en ligne : {fautifs}. Un champ retiré par la "
        "projection y rendrait une chaîne vide, indiscernable d'une faute de frappe."
    )


def test_perm06_le_document_rend_exactement_les_colonnes_projetees(
    db_all, deux_magasins, ressource
):
    """La moitié comportementale du test précédent : la liste itérée est bien la projetée.

    Un gabarit peut parfaitement itérer une liste **non** projetée. Le compte des cellules
    rendues contre le compte des champs du sérialiseur est ce qui distingue les deux, et
    c'est une assertion que ni l'absence de la valeur ni l'absence du nom ne couvrent.
    """
    from plateforme.comptes.acces import _PorteurAcces
    from plateforme.projection.documents import contexte_document, rendre_html

    _gerant, acces_gerant = acces_sans_le_droit(deux_magasins)
    contexte = contexte_document(
        SerializerRessourceFixture, ressource, acces=acces_gerant
    )
    html = rendre_html(NOM_TEMPLATE, contexte)

    projetes = list(
        SerializerRessourceFixture(
            context={"request": _PorteurAcces(acces=acces_gerant)}
        ).fields
    )
    assert [nom for nom, _valeur in contexte["colonnes"]] == projetes
    assert html.count("</td>") == len(projetes), (
        "Le document ne rend pas une cellule par champ projeté. Il itère donc autre "
        "chose que la liste de colonnes que la projection lui a donnée."
    )


def _catalogue_rendu(utilisateur):
    """`GET /api/comptes/catalogue/`, joué sans client HTTP, et **rendu**.

    Même idiome que `_appeler` plus haut, et pour la même raison : un vrai client HTTP
    passerait par `TenantMiddleware`, qui exige une base client provisionnée. La requête
    traverse en revanche `AccesMiddleware`, donc l'accès est résolu par le chemin de
    production et non posé à la main.

    La réponse est **rendue** avant d'être retournée, parce que ce que ce test affirme
    porte sur le JSON qui part sur le fil — `reponse.data` est une structure Python, et
    un filtrage appliqué après sérialisation y serait invisible.
    """
    from rest_framework.test import APIRequestFactory, force_authenticate

    from plateforme.comptes.middleware import AccesMiddleware
    from plateforme.comptes.views import VueCatalogue

    vue = VueCatalogue.as_view()
    requete = APIRequestFactory().get("/api/comptes/catalogue/")
    requete.user = utilisateur
    force_authenticate(requete, user=utilisateur)
    reponse = AccesMiddleware(lambda recue: vue(recue))(requete)
    reponse.render()
    return reponse


def _gerant_gestionnaire_dun_seul_magasin(magasin, codes):
    """Un gérant détenant `compte.gerer` et `codes` dans **un seul** des deux magasins."""
    from plateforme.comptes.acces import acces_pour
    from plateforme.comptes.permissions_catalogue import Permission
    from tests.factories import AccesMagasinFactory, DroitAccordeFactory, GerantFactory

    gerant = GerantFactory()
    AccesMagasinFactory(utilisateur=gerant, magasin_code=magasin.code)
    for code in (Permission.COMPTE_GERER, *codes):
        DroitAccordeFactory(utilisateur=gerant, magasin_code=magasin.code, code=code)
    return gerant, acces_pour(gerant)


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

    **L'assertion porte sur `rendered_content`**, c'est-à-dire sur les octets. Une
    assertion sur `reponse.data` laisserait passer un filtrage appliqué au rendu, qui est
    précisément le mode de fuite que cette recommandation existe pour fermer.
    """
    from plateforme.comptes.permissions_catalogue import (
        EXPLICATIONS,
        PREREQUIS,
        Permission,
    )
    from tests.factories import ProprietaireFactory

    anfa, maarif = deux_magasins
    gerant, acces = _gerant_gestionnaire_dun_seul_magasin(
        anfa, [Permission.STOCK_VOIR, Permission.CAISSE_VOIR, Permission.CAISSE_SAISIR]
    )
    assert acces.peut(Permission.COMPTE_GERER) is True, (
        "Le gérant du test n'administre pas les comptes : le catalogue lui répondrait "
        "403 et le test vérifierait une permission, pas une intersection."
    )

    reponse = _catalogue_rendu(gerant)
    assert reponse.status_code == 200, reponse.data
    octets = reponse.rendered_content

    assert Permission.ARTICLE_VOIR_PRIX_ACHAT.value.encode() not in octets, (
        "Le code `article.voir_prix_achat` est dans le JSON servi à un gérant qui ne le "
        "détient pas. Même si l'interface ne l'affiche pas, il est lisible dans les "
        "outils de développement, dans une réponse en cache, et dans le prochain "
        "refactor — c'est-à-dire qu'il n'est pas absent, il est caché."
    )
    assert maarif.code.encode() not in octets, (
        "Le magasin Maârif est dans le catalogue d'un gérant d'Anfa. C'est une "
        "énumération des magasins qu'il ne détient pas."
    )

    codes_servis = {
        droit["code"]
        for section in reponse.data["sections"]
        for droit in section["droits"]
    }
    assert codes_servis == {
        Permission.COMPTE_GERER.value,
        Permission.STOCK_VOIR.value,
        Permission.CAISSE_VOIR.value,
        Permission.CAISSE_SAISIR.value,
    }, f"Le catalogue intersecté ne correspond pas aux droits détenus : {sorted(codes_servis)}"
    assert [m["code"] for m in reponse.data["magasins"]] == [anfa.code]

    # La carte des prérequis est restreinte aux codes visibles : une entrée nommant un
    # code absent réintroduirait par la porte de service ce que l'intersection retire.
    prerequis = reponse.data["prerequis"]
    assert prerequis == {Permission.CAISSE_SAISIR.value: [Permission.CAISSE_VOIR.value]}
    for dependant, requis in prerequis.items():
        assert dependant in codes_servis
        assert set(requis) <= codes_servis

    # ----------------------------------------------------------------------------------
    # Le contrôle positif. **Sans lui, un catalogue toujours vide passerait tout ce qui
    # précède** — et c'est exactement le genre d'implémentation qu'un test d'absence
    # encourage.
    # ----------------------------------------------------------------------------------
    proprietaire = ProprietaireFactory()
    temoin = _catalogue_rendu(proprietaire)
    assert temoin.status_code == 200, temoin.data

    tous = {
        droit["code"]
        for section in temoin.data["sections"]
        for droit in section["droits"]
    }
    assert tous == set(Permission.values)
    assert len(tous) == 21
    assert {m["code"] for m in temoin.data["magasins"]} == {anfa.code, maarif.code}
    assert Permission.ARTICLE_VOIR_PRIX_ACHAT.value.encode() in temoin.rendered_content

    # Les libellés et les explications viennent du serveur, jamais de la SPA
    # (`03-UI-SPEC.md` 7.4) : un code ajouté en phase 8 apparaît à l'écran sans qu'une
    # ligne change côté client, et un libellé ne peut pas dériver de son code.
    par_code = {
        droit["code"]: droit
        for section in temoin.data["sections"]
        for droit in section["droits"]
    }
    for code in Permission.values:
        assert par_code[code]["libelle"] == Permission(code).label
        assert par_code[code]["explication"] == EXPLICATIONS[code]
    assert [section["titre"] for section in temoin.data["sections"]] == [
        "Clients et ordonnances",
        "Stock",
        "Ventes et factures",
        "Caisse",
        "Fournisseurs et achats",
        "Rappels et tableau de bord",
        "Comptes",
    ]
    assert temoin.data["prerequis"] == {
        str(code): [str(requis) for requis in valeurs]
        for code, valeurs in PREREQUIS.items()
    }
