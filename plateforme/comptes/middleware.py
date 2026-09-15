"""`AccesMiddleware` — poser l'accès résolu sur la requête, et rien d'autre.

Une ligne de code et trois décisions.

**1. Après `TenantMiddleware`, strictement.** Résoudre à quels magasins un octroi se réfère
demande une requête dans la base **du client** — `Magasin.objects.filter(actif=True,
code__in=...)`. Cette requête passe par le routeur, qui lit l'alias lié et **lève** quand il
n'y en a pas. Placé plus haut, ce middleware ne se plaindrait de rien à l'installation :
l'objet est paresseux, donc l'échec n'apparaîtrait qu'au premier point de terminaison qui
touche `request.acces`, en production. L'ordre est donc pinné par un test sur les index de
`settings.MIDDLEWARE`, pas par ce paragraphe.

**2. Sur l'objet requête, jamais dans un contexte partagé.** `03-RESEARCH.md` P15 le dit et
la raison est celle de la phase 2 : la durée de vie de la requête borne l'attribut. Un état
partagé par thread, lui, survit à la requête qui l'a posé et doit être vidé dans un
`finally` — et c'est cet oubli-là qui fait qu'une requête lit l'accès de la précédente sur un
travailleur réutilisé (menace T-03-26). **L'interdiction du `reset(token)` qui pèse sur
`plateforme/tenancy/` s'étend explicitement à `plateforme/comptes/` :** rendu un jeton, une
variable de contexte restaure la valeur *précédente*, donc réinstalle fidèlement la fuite
qu'un thread portait déjà. Un test au niveau du source refuse cette forme dans ce fichier.

**3. Rien dans un `finally`, et c'est dit pour que personne n'en ajoute.** Il n'y a rien à
nettoyer — c'est précisément l'intérêt de poser l'accès sur la requête. Le risque réel ici
est le mimétisme : quelqu'un lit `plateforme/tenancy/middleware.py`, y voit un `finally` qui
nettoie, et reproduit la forme sans la raison. Ce middleware n'a pas de contrepartie à
nettoyer parce qu'il n'installe rien de partagé.

`SimpleLazyObject` signifie qu'un point de terminaison qui ne touche jamais `request.acces`
ne paie rien : ni requête sur `AccesMagasin`, ni sur `DroitAccorde`, ni sur `Magasin`. La
sonde de santé et la page de connexion n'ouvrent donc aucune connexion vers la base d'un
opticien (menace T-03-27), et le compte de requêtes le vérifie.
"""

from __future__ import annotations

from django.utils.functional import SimpleLazyObject

from plateforme.comptes.acces import acces_pour


class AccesMiddleware:
    """DOIT être installé après `TenantMiddleware`, et avant toute vue.

    Après `TenantMiddleware` parce que la résolution lit la base du client ; avant toute vue
    parce que `request.acces` est le seul objet que le reste du code a le droit de consulter
    pour savoir ce qu'un principal peut faire. Rien ne lit `request.user.droits` ni
    `request.user.client_id` — cette couture est ce qui rend le stockage des droits
    remplaçable en une fonction.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Résolu à la première lecture, une fois par requête, jamais mis en cache au-delà.
        # C'est ce qui rend vraie la phrase que 03-UI-SPEC 7.8 affiche sous la liste des
        # droits : une révocation prend effet sans reconnexion.
        request.acces = SimpleLazyObject(lambda: acces_pour(request.user))
        return self.get_response(request)
