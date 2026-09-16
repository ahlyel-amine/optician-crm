"""Consommateur 1 du registre : l'API JSON.

Une seule méthode, et deux propriétés qu'elle achète.

**Le défaut est `Acces.ANONYME`, jamais `None`.** `getattr(request, "acces", None)` suivi
d'un `if acces is None: return champs` rendrait tous les champs protégés sur **tout**
chemin où `AccesMiddleware` n'a pas tourné : une vue montée hors de la pile habituelle,
une commande de gestion, une tâche, un test. C'est `03-RESEARCH.md` P2 et la menace
T-03-30 ; c'est aussi CLAUDE.md #8 appliqué un étage plus haut que le contexte de
locataire. Un défaut permissif produit une fuite silencieuse, un défaut fermé produit une
page vide qu'on remarque.

**Retirer depuis `get_fields()` ferme le côté écriture gratuitement.** Un champ retiré
n'atteint jamais `validated_data`, donc un gérant qui POSTe `prix_achat` est ignoré plutôt
qu'obéi (menace T-03-34). Le test correspondant affirme la valeur **inchangée**, pas un
400 : DRF ne lève pas pour une clé inconnue, et un test qui attendrait 400 serait rouge
au-dessus d'un code parfaitement correct — après quoi quelqu'un le « réparerait » en
rendant le champ inscriptible.

**Ce que cette classe ne garantit pas, et qui doit être dit.** Elle projette des *champs*.
Elle ne peut rien contre une ligne qu'il ne fallait pas servir (plan 03-07), contre un
agrégat déjà calculé (PERM-05), ni contre un `.values()` ou un `.annotate()` qui ne touche
aucun sérialiseur (A-03-04). Ce sont des faiblesses structurelles d'une projection par
sérialiseur, énoncées ici plutôt que dissimulées, et fermées ailleurs.

Et elle n'est pas, à elle seule, ce qui rend PERM-06 vrai : le registre l'est, et le test
paramétré qui l'itère. Un sérialiseur qui lit le registre sans hériter d'ici passe les
mêmes assertions. L'héritage est du confort ; l'énumérabilité est la garantie.
"""

from __future__ import annotations

from rest_framework import serializers

from plateforme.comptes.acces import Acces
from plateforme.projection.registre import champs_interdits


def acces_du_contexte(contexte) -> Acces:
    """L'`Acces` porté par le contexte d'un sérialiseur, ou `Acces.ANONYME`.

    Fonction nommée plutôt qu'expression en ligne, pour que les quatre consommateurs
    partagent littéralement le même défaut. Le jour où quelqu'un écrit un cinquième rendu,
    la question « et si le contexte est vide ? » a déjà une réponse écrite.
    """
    requete = (contexte or {}).get("request")
    acces = getattr(requete, "acces", None)
    return Acces.ANONYME if acces is None else acces


class SerializerProjete(serializers.ModelSerializer):
    """Un `ModelSerializer` dont les champs interdits sont retirés avant tout usage.

    `Meta.model` est obligatoire : le registre est clé par champ de **modèle**, jamais par
    classe de sérialiseur, précisément pour qu'un champ protégé le reste quand la phase 6
    l'imbriquera dans la ressource d'un autre (menace T-03-31).
    """

    def get_fields(self):
        champs = super().get_fields()
        acces = acces_du_contexte(self.context)
        for nom in champs_interdits(self.Meta.model, acces):
            champs.pop(nom, None)
        return champs
