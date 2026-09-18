"""La traduction des exceptions de service en réponses HTTP. Un seul endroit.

Les services de ce dépôt lèvent les exceptions de **Django** —
`django.core.exceptions.ValidationError`, `PermissionDenied` — et non celles de DRF. Ce
n'est pas une inattention : un service doit rester appelable depuis une commande de
gestion, depuis une tâche Celery et depuis l'inscription en libre service de la phase 12,
qui n'ont aucune requête HTTP. Lever une exception de DRF hors requête produit un objet
qui prétend porter un code de statut que personne ne lira.

Le prix est que **DRF ne convertit pas** `django.core.exceptions.ValidationError` : sans
la traduction ci-dessous, un refus métier parfaitement prévu — un magasin non accordé, une
correction sans motif — sort en **500 avec sa trace** au lieu d'un 400 lisible.

Le plan 03-08 a écrit cette fonction pour `plateforme/comptes/views.py`. Le plan 04-05 en
a eu besoin pour `domaine/ordonnances/vues.py`, et l'a **déplacée ici plutôt que recopiée**
— deux traductions d'exceptions finissent par différer sur la forme du corps d'erreur, et
la SPA verrait alors deux formats de 400 selon la route, sans qu'aucun test ne compare les
deux.
"""

from __future__ import annotations

from contextlib import contextmanager

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import exceptions


@contextmanager
def erreurs_de_service():
    """Traduire les exceptions du service en réponses, et nulle part ailleurs.

    `message_dict` quand l'erreur nomme ses champs — ce qui rend un 400 exploitable par un
    formulaire, champ par champ — et la liste des messages sinon.
    """
    try:
        yield
    except DjangoValidationError as erreur:
        detail = (
            erreur.message_dict
            if hasattr(erreur, "message_dict")
            else list(erreur.messages)
        )
        raise exceptions.ValidationError(detail) from erreur
