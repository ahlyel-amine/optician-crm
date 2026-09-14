"""PERM-01 — la connexion par session, et les quatre propriétés qui vont avec.

**Ces tests ne sont pas encore implémentés.** Ils portent le marqueur `pending` et
échouent volontairement ; le plan **03-08** les implémente et retire le marqueur, un par
un. Ils existent maintenant, avant le code, parce que `.planning/TESTING.md` §1 le
demande : un test écrit après l'implémentation est écrit pour passer, et une exigence
dont le test naît en même temps que le code n'a jamais été rouge, donc n'a jamais rien
prouvé.

Pourquoi une session et non un jeton, rappelé ici parce que c'est ce que ces tests
pinnent : `TenantMiddleware.resolve_client` lit `request.user.client_id` **au moment du
middleware**. `AuthenticationMiddleware` peuple `request.user` depuis la session, donc
avant ; DRF authentifie dans `APIView.initial()`, donc après **tous** les middlewares.
Sous jeton, `request.user` est `AnonymousUser` à l'instant où le locataire devrait se
lier, rien ne se lie, et la première requête métier lève `NoTenantBound`
(`03-RESEARCH.md` § « Where CLAUDE.md is wrong », point 1).

Convention de ce fichier, et de tous les stubs de ce plan : **aucun import du code en
construction au niveau du module.** Un `from plateforme.comptes.vues import ...` en tête
de fichier casserait la **collecte** de la suite entière tant que le module n'existe pas,
ce qui rend rouge tout ce qui n'a rien à voir et rend la boucle rapide inutilisable pour
les vagues suivantes. Les imports descendent dans le corps des fonctions.
"""

from __future__ import annotations

import pytest


@pytest.mark.pending
def test_perm01_la_connexion_etablit_une_session_et_lie_le_client(db_all):
    """PERM-01 — se connecter doit produire une session *et* lier le locataire.

    Rouge, ce test prouverait que l'identité et la tenancy sont deux choses distinctes
    dans le code : un propriétaire authentifié dont `request.user.client_id` ne remonte
    pas jusqu'au routeur obtient une session parfaitement valide au-dessus d'une couche
    métier qui refuse de tourner — ou pire, qui tombe sur `default`. C'est la couture
    exacte que la phase 2 a laissée ouverte et que la phase 3 referme.
    """
    pytest.fail("non implémenté : plan 03-08")


@pytest.mark.pending
def test_perm01_le_cookie_de_session_survit_a_la_fermeture_du_navigateur():
    """PERM-01 — « reste connecté » est une propriété du cookie, pas une intention.

    L'exigence dit *stays signed in across sessions*. Rouge, ce test dirait que
    `SESSION_EXPIRE_AT_BROWSER_CLOSE` a repris sa valeur par défaut, ou que
    `SESSION_COOKIE_AGE` a été laissé aux deux semaines de Django sans décision. Un
    opticien qui doit retaper son mot de passe chaque matin est une régression
    silencieuse : rien ne casse, l'usage se dégrade.
    """
    pytest.fail("non implémenté : plan 03-08")


@pytest.mark.pending
def test_perm01_la_deconnexion_invalide_la_session_immediatement(db_all):
    """PERM-01 — se déconnecter doit détruire la session côté serveur, pas le cookie.

    Rouge, ce test signalerait une déconnexion qui se contente de supprimer le cookie du
    navigateur : la clé de session reste valide côté serveur, donc quiconque l'a captée
    reste authentifié. Le test rejoue la clé après la déconnexion et exige un refus.
    """
    pytest.fail("non implémenté : plan 03-08")


@pytest.mark.pending
def test_perm01_la_connexion_est_limitee_en_debit(db_all):
    """PERM-01 — une adresse de connexion unique pour toute la flotte se brute-force.

    CLAUDE.md #11 : il y a **une** adresse de connexion partagée par tous les opticiens.
    C'est donc un point unique où essayer des mots de passe contre n'importe quel compte
    de n'importe quelle affaire. Rouge, ce test dirait que ce point est ouvert sans
    limite. Argon2 rend chaque essai coûteux, ce qui est aussi une raison de limiter :
    sans plafond, l'essai coûteux devient un déni de service contre notre propre CPU.
    """
    pytest.fail("non implémenté : plan 03-08")


@pytest.mark.pending
def test_perm01_une_requete_api_sans_jeton_csrf_est_refusee(db_all):
    """PERM-01 — le prix du cookie de session est le CSRF, et il se paie explicitement.

    L'authentification par cookie signifie que le navigateur joint la preuve
    d'authentification à **toute** requête vers notre origine, y compris celle qu'un autre
    site déclenche. Rouge, ce test dirait qu'une écriture passe sans jeton — donc qu'une
    page tierce peut créer un compte gérant ou accorder un droit au nom d'un propriétaire
    connecté. `SessionAuthentication` de DRF impose le CSRF ; ce test constate qu'on ne
    l'a pas contourné avec un `csrf_exempt` posé pour débloquer un test.
    """
    pytest.fail("non implémenté : plan 03-08")
