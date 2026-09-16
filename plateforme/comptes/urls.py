"""Les routes d'authentification, montées sous `/api/auth/` par `config/urls.py`.

Les chemins sont en français, comme le reste du vocabulaire du produit
(`03-UI-SPEC.md` 9.3) : l'API est lue par une seule équipe et par un client TypeScript
généré, donc la cohérence du lexique vaut plus que la convention anglophone.

Les noms de route sont préfixés `auth-` pour que `reverse("auth-moi")` reste sans
ambiguïté quand les phases 4 à 10 monteront leurs propres routes.
"""

from __future__ import annotations

from django.urls import path

from plateforme.comptes import views

urlpatterns = [
    path("csrf/", views.VueCsrf.as_view(), name="auth-csrf"),
    path("connexion/", views.VueConnexion.as_view(), name="auth-connexion"),
    path("deconnexion/", views.VueDeconnexion.as_view(), name="auth-deconnexion"),
    path("moi/", views.VueMoi.as_view(), name="auth-moi"),
    path("mot-de-passe/", views.VueMotDePasse.as_view(), name="auth-mot-de-passe"),
]
