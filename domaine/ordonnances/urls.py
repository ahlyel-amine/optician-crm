"""Les routes de l'ordonnance, **imbriquées sous la fiche client**.

Montées par `config/urls.py` sous le même préfixe que `domaine/clients/urls.py`, et
**avant** lui : les motifs du routeur des clients sont ancrés (`^$` et `^(?P<pk>…)/$`),
donc aucun ne pourrait absorber `<id>/ordonnances/` — mais l'ordre explicite épargne au
prochain lecteur d'avoir à le vérifier.

**Pas de `SimpleRouter` ici, et ce n'est pas de la paresse.** Un routeur imbriqué exige
soit une dépendance de plus (`drf-nested-routers`), soit un `lookup` composé ; deux
`path()` écrits à la main disent la même chose en six lignes, sans rien ajouter au
`pyproject.toml` d'un produit qui pèse déjà quatre services. Le prix — deux noms de route
à tenir à jour — est payé par
`tests/test_schema_contrat.py::test_perm06_le_contrat_porte_les_routes_montees_et_aucune_route_de_test`,
qui refuse un contrat qui ne les décrirait pas.

**Aucune route de modification ni de retrait**, et ce n'est pas seulement que personne
n'en a monté : `VueOrdonnances` n'hérite d'aucune base qui les servirait et son
`http_method_names` ne porte ni `put`, ni `patch`, ni `delete`. Un `PATCH` sur la route de
détail ci-dessous rend donc **405** — pas 403, qui dirait qu'une route existe derrière un
droit (CLIENT-06, menace T-04-29).
"""

from __future__ import annotations

from django.urls import path

from domaine.ordonnances.vues import VueOrdonnances, VuePhotoOrdonnance

urlpatterns = [
    path(
        "<int:client_id>/ordonnances/",
        VueOrdonnances.as_view({"get": "list", "post": "create"}),
        name="ordonnance-liste",
    ),
    path(
        "<int:client_id>/ordonnances/<int:pk>/",
        VueOrdonnances.as_view({"get": "retrieve"}),
        name="ordonnance-detail",
    ),
]

#: La route de la photo, **plate** et non imbriquée sous la fiche. Montée sous un préfixe
#: distinct par `config/urls.py`, donc dans une seconde liste nommée plutôt que dans
#: `urlpatterns` — même forme que `plateforme/comptes/urls.py::urlpatterns_gestion`, et
#: pour la même raison : `include()` prendrait la première liste du module.
#:
#: **Pourquoi plate.** Une ordonnance n'est pas scopée au magasin (D-4a) et son
#: identifiant est déjà borné par la base du locataire : le segment `client` n'ajouterait
#: aucune borne, seulement un second identifiant à tenir cohérent et un 404 de plus à
#: distinguer. L'imbrication de l'historique, elle, existe pour éviter un `?client=` dans
#: `PARAMETRES_RESERVES` — une raison qui ne s'applique pas ici.
#:
#: **Aucune route de retrait.** `VuePhotoOrdonnance.http_method_names` ne porte pas
#: `delete`, donc un `DELETE` rend **405** — pas 403, qui dirait qu'une route existe
#: derrière un droit (`04-UI-SPEC.md` §22.3).
urlpatterns_photo = [
    path(
        "<int:pk>/photo/",
        VuePhotoOrdonnance.as_view(),
        name="ordonnance-photo",
    ),
]
