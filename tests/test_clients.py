"""CLIENT-01 — la fiche client sur l'API : la créer, la retrouver, et qui a le droit.

Les tests se lisent au niveau du **contrat** : une vraie requête traverse
`AccesMiddleware`, la vue DRF et le sérialiseur, exactement comme en production.

**Pourquoi `APIRequestFactory` plutôt qu'`APIClient`.** Un vrai client HTTP passe par
`TenantMiddleware`, qui enregistre un alias `tenant_<pk>` depuis la ligne `Client` du plan
de contrôle — donc une **autre connexion** que celle du fixture `tenant_a`, hors de la
transaction de test, avec des écritures à committer puis à nettoyer à la main (voir
`affaire_reelle` dans `conftest.py`). C'est le prix que `03-08` a payé pour prouver la
liaison de bout en bout ; il n'a pas à être payé une seconde fois ici. L'idiome retenu est
celui de `tests/test_projection.py` : la requête est jouée sans client HTTP, à travers le
middleware qui compte pour ce fichier, dans le locataire que le fixture a lié.

Ce que cet idiome ne couvre pas est donc écrit plutôt que sous-entendu : il ne prouve pas
que `TenantMiddleware` lie le bon client. C'est `tests/test_comptes_auth.py` qui le prouve,
une fois, pour toutes les routes.

**`force_authenticate` est obligatoire**, pour la raison détaillée dans
`tests/test_projection.py::_appeler` : le setter `Request.user` de DRF réécrit
`_request.user`, et sans lui l'accès résolu serait `Acces.ANONYME` — les deux moitiés du
test deviendraient anonymes et l'assertion de refus passerait pour une fausse raison.
"""

from __future__ import annotations

import pytest

#: Le chemin monté, écrit une fois. Un test qui recopie une URL reste vert le jour où la
#: route déménage : il vérifie alors une 404 bien formée.
CLIENTS = "/api/clients/"


def _gerant(affaire, magasins, codes):
    """Un gérant de `affaire`, ayant accès aux deux magasins et y détenant `codes`.

    **Les droits sont posés dans les DEUX magasins, et ce n'est pas du zèle.**
    `Acces.peut(code)` sans argument magasin est une **conjonction** (plan 03-05) : un
    droit accordé dans un seul des deux magasins n'autorise rien. Un helper qui n'en
    servirait qu'un produirait des 403 inexplicables dans un fichier qui ne parle pas de
    portée magasin.

    L'`AccesMagasin` est créé **avant** le `DroitAccorde` : `DroitAccorde.save` refuse un
    droit visant un magasin non accordé (menace T-03-18), et c'est aussi l'ordre dans
    lequel l'interface écrit.
    """
    from tests.factories import AccesMagasinFactory, DroitAccordeFactory, GerantFactory

    compte = GerantFactory(client=affaire)
    for magasin in magasins:
        AccesMagasinFactory(utilisateur=compte, magasin_code=magasin.code)
        for code in codes:
            DroitAccordeFactory(utilisateur=compte, magasin_code=magasin.code, code=code)
    return compte


def _appeler(utilisateur, methode, action, *, parametres=None, corps=None, **kwargs):
    """Une vraie requête : principal -> `AccesMiddleware` -> `VueClients` -> JSON rendu."""
    from rest_framework.test import APIRequestFactory, force_authenticate

    from domaine.clients.vues import VueClients
    from plateforme.comptes.middleware import AccesMiddleware

    vue = VueClients.as_view({methode: action})
    fabrique = APIRequestFactory()
    if methode == "get":
        requete = fabrique.get(CLIENTS, parametres or {})
    elif methode == "post":
        requete = fabrique.post(CLIENTS, corps or {}, format="json")
    else:
        requete = fabrique.patch(CLIENTS, corps or {}, format="json")
    requete.user = utilisateur
    force_authenticate(requete, user=utilisateur)
    reponse = AccesMiddleware(lambda recue: vue(recue, **kwargs))(requete)
    reponse.render()
    return reponse


def _noms(reponse) -> list[str]:
    return [ligne["nom"] for ligne in reponse.data]


# --------------------------------------------------------------------------------------
# CLIENT-01 — créer une fiche, la retrouver par nom et par téléphone
# --------------------------------------------------------------------------------------
def test_client01_une_fiche_se_cree_et_se_retrouve_par_nom_et_par_telephone(
    db_all, deux_magasins
):
    """CLIENT-01 — l'exigence entière, en une requête d'écriture et trois de lecture.

    La moitié qui compte est la **dernière** : `06 12 34 56 78`, avec des espaces, doit
    rendre la même fiche que `0612345678`. C'est ainsi qu'un numéro se lit sur l'écran
    d'un téléphone et se recopie au comptoir. Sans elle, on aurait écrit une recherche qui
    marche pour la machine et pas pour la personne — et elle serait passée pour correcte,
    parce que la moitié machine est verte.

    **Ce qu'il attrape :** une normalisation de téléphone appliquée à l'écriture et pas à
    la lecture. La colonne `telephone_normalise` est remplie par `save()` depuis le plan
    04-01 ; si la recherche compare le terme brut à cette colonne, la forme espacée ne
    rend rien et la forme compacte rend tout — vert à moitié, donc invisible.
    """
    from django.urls import reverse

    from plateforme.comptes.permissions_catalogue import Permission
    from tests.factories import ClientFactory

    assert reverse("client-list") == CLIENTS, (
        "La ressource client n'est pas montée sous /api/clients/. Le chemin est un "
        "contrat : le client TypeScript généré et la palette de recherche le portent."
    )

    affaire = ClientFactory()
    compte = _gerant(
        affaire, deux_magasins, (Permission.CLIENT_VOIR, Permission.CLIENT_MODIFIER)
    )

    creation = _appeler(
        compte,
        "post",
        "create",
        corps={"nom": "Mohammed Alaoui", "telephone": "0612345678"},
    )
    assert creation.status_code == 201, creation.data
    assert creation.data["nom"] == "Mohammed Alaoui"

    par_nom = _appeler(
        compte, "get", "list", parametres={"search": "Mohammed Alaoui"}
    )
    assert par_nom.status_code == 200, par_nom.data
    assert "Mohammed Alaoui" in _noms(par_nom)

    par_telephone = _appeler(compte, "get", "list", parametres={"search": "0612345678"})
    assert par_telephone.status_code == 200, par_telephone.data
    assert "Mohammed Alaoui" in _noms(par_telephone)

    avec_espaces = _appeler(
        compte, "get", "list", parametres={"search": "06 12 34 56 78"}
    )
    assert avec_espaces.status_code == 200, avec_espaces.data
    assert "Mohammed Alaoui" in _noms(avec_espaces), (
        "« 06 12 34 56 78 » ne rend pas la fiche que « 0612345678 » rend. Le terme de "
        "recherche doit passer par `normaliser_telephone` avant d'être comparé à "
        "`telephone_normalise` : c'est ainsi qu'un opticien recopie un numéro."
    )


def test_client01_la_liste_exige_client_voir_et_la_creation_client_modifier(
    db_all, deux_magasins
):
    """CLIENT-01 / T-04-14 — les deux droits, et la moitié que l'on oublie.

    Trois principals, trois réponses. Le gérant **sans** `client.voir` est refusé partout ;
    celui qui a `client.voir` **sans** `client.modifier` lit et n'écrit pas.

    **Ce qu'il attrape :** une classe de permission posée sur la vue mais pas sur l'action
    d'écriture. C'est la forme la plus courante de la faute : `permission_classes` porte
    bien un contrôle, la revue de code le voit, et il ne distingue pas la lecture de
    l'écriture — un gérant qui ne devait que consulter crée des fiches. Le POST à 403 est
    donc l'assertion porteuse ; les deux autres sont son décor.
    """
    from plateforme.comptes.permissions_catalogue import Permission
    from tests.factories import ClientFactory

    affaire = ClientFactory()

    sans_rien = _gerant(affaire, deux_magasins, ())
    refus_liste = _appeler(sans_rien, "get", "list")
    assert refus_liste.status_code == 403, refus_liste.data

    lecteur = _gerant(affaire, deux_magasins, (Permission.CLIENT_VOIR,))
    lecture = _appeler(lecteur, "get", "list")
    assert lecture.status_code == 200, lecture.data

    ecriture = _appeler(
        lecteur, "post", "create", corps={"nom": "Fatima Bennani", "telephone": ""}
    )
    assert ecriture.status_code == 403, (
        "Un gérant qui détient `client.voir` mais pas `client.modifier` a créé une fiche "
        f"({ecriture.status_code}). La classe de permission d'écriture manque, ou elle ne "
        "distingue pas les méthodes sûres des autres."
    )


def test_client01_aucune_route_ne_supprime_une_fiche():
    """CLIENT-01 — une fiche se désactive, elle ne se supprime pas.

    **Ce qu'il attrape :** un `DestroyModelMixin` ajouté « pour la symétrie ». L'article
    211 du CGI impose dix ans de conservation, et la phase 6 posera un `PROTECT` depuis la
    facture : une route de suppression serait soit une erreur au premier client ayant
    acheté, soit — pire — une perte de donnée fiscale sur un client qui n'a encore rien
    acheté. Le champ `actif` existe pour cela.

    Le contrôle porte sur la **table d'actions de la vue telle que le routeur l'a montée**,
    et non sur une classe de base : `SimpleRouter` ne mappe `delete` que si le viewset
    porte `destroy`, donc l'absence de l'entrée est exactement l'absence de la route.
    """
    from django.urls import resolve

    detail = resolve(f"{CLIENTS}42/")
    actions = getattr(detail.func, "actions", {})
    assert actions, (
        f"{CLIENTS}42/ n'est pas servi par un viewset — `actions` est vide. Le test ne "
        "vérifie alors rien : il passerait au-dessus d'une route de suppression montée "
        "à la main."
    )
    assert "delete" not in actions, (
        f"La route de détail mappe DELETE -> {actions.get('delete')!r}. Une fiche client "
        "se désactive (`actif = False`) : dix ans de conservation (art. 211 CGI) et un "
        "`PROTECT` depuis la facture en phase 6."
    )


@pytest.mark.parametrize("parametre", ["q", "telephone", "nom"])
def test_client01_tout_parametre_hors_liste_blanche_est_refuse(
    db_all, deux_magasins, parametre
):
    """T-04-16 — `search` est le seul nom accepté, et tout autre produit le refus unique.

    **Ce qu'il attrape :** un second nom de paramètre introduit sans entrer dans
    `PARAMETRES_RESERVES`. Trois noms plausibles sont essayés — `?q=`, `?telephone=` et
    `?nom=` — parce que ce sont exactement ceux qu'on écrit sans y penser, et que chacun
    serait alors un oracle : l'ensemble des paramètres acceptés dessine l'ensemble des
    colonnes qui existent (`03-RESEARCH.md` A-03-07).

    `ProjectedFieldFilter` est réutilisé tel quel et la vue ne déclare aucun
    `champs_filtrables`, donc la liste blanche est exactement `PARAMETRES_RESERVES`.
    """
    from plateforme.comptes.permissions_catalogue import Permission
    from tests.factories import ClientFactory

    affaire = ClientFactory()
    compte = _gerant(affaire, deux_magasins, (Permission.CLIENT_VOIR,))

    reponse = _appeler(compte, "get", "list", parametres={parametre: "mohamed"})
    assert reponse.status_code == 400, (
        f"`?{parametre}=` a été accepté ({reponse.status_code}). Un paramètre non déclaré "
        "doit produire le refus unique, sans quoi le code de statut énumère les colonnes "
        "qui existent."
    )
