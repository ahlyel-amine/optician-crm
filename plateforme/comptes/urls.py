"""Les routes d'authentification, montées sous `/api/auth/` par `config/urls.py`.

Les chemins sont en français, comme le reste du vocabulaire du produit
(`03-UI-SPEC.md` 9.3) : l'API est lue par une seule équipe et par un client TypeScript
généré, donc la cohérence du lexique vaut plus que la convention anglophone.

Les noms de route sont préfixés `auth-` pour que `reverse("auth-moi")` reste sans
ambiguïté quand les phases 4 à 10 monteront leurs propres routes.
"""

from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from plateforme.comptes import views

urlpatterns = [
    path("csrf/", views.VueCsrf.as_view(), name="auth-csrf"),
    path("connexion/", views.VueConnexion.as_view(), name="auth-connexion"),
    path("deconnexion/", views.VueDeconnexion.as_view(), name="auth-deconnexion"),
    path("moi/", views.VueMoi.as_view(), name="auth-moi"),
    path("mot-de-passe/", views.VueMotDePasse.as_view(), name="auth-mot-de-passe"),
]


#: `SimpleRouter` et non `DefaultRouter` : ce dernier monte en plus une vue racine d'API
#: qui énumère les routes, ce qui est un inventaire servi à tout appelant authentifié.
_routeur = SimpleRouter(trailing_slash=True)
_routeur.register("", views.VueComptes, basename="compte")

#: Les routes de gestion, montées sous `/api/comptes/` par `config/urls.py`.
#:
#: **L'ordre compte.** Le routeur capture `/<pk>/` avec un motif qui accepterait aussi
#: bien un mot, donc toute route littérale de ce préfixe doit être déclarée **avant** lui,
#: sans quoi elle serait lue comme un identifiant et répondrait 404.
#:
#: Il n'y a aucune route de retrait : `VueComptes` n'hérite pas de `DestroyModelMixin` et
#: `http_method_names` n'inclut pas `delete`. Un compte se désactive (`03-UI-SPEC.md` 7.8).
urlpatterns_gestion = [
    path("catalogue/", views.VueCatalogue.as_view(), name="comptes-catalogue"),
    path("", include(_routeur.urls)),
]
