"""Les routes de la fiche client, montées sous `/api/clients/` par `config/urls.py`.

Les chemins sont en français, comme le reste du vocabulaire du produit ; les noms de
route sont `client-list` et `client-detail`, dérivés du `basename` ci-dessous.

`SimpleRouter` et non `DefaultRouter` : ce dernier monte en plus une vue racine d'API qui
**énumère les routes**, c'est-à-dire un inventaire servi à tout appelant authentifié.
Même choix qu'au plan 03-09, pour la même raison.
"""

from __future__ import annotations

from rest_framework.routers import SimpleRouter

from domaine.clients import vues

_routeur = SimpleRouter(trailing_slash=True)
_routeur.register("", vues.VueClients, basename="client")

#: Il n'y a aucune route de retrait : `VueClients` n'hérite pas de `DestroyModelMixin` et
#: `http_method_names` n'inclut ni `delete` ni `put`. Une fiche se désactive.
urlpatterns = _routeur.urls
