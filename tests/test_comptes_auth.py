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


#: Trente jours, en secondes. La valeur que PERM-01 exige, écrite une fois ici et
#: comparée au réglage — un test qui recopierait `60 * 60 * 24 * 30` des deux côtés
#: passerait tout aussi bien contre un réglage remis à quatorze jours et un test édité
#: dans le même commit.
TRENTE_JOURS_EN_SECONDES = 2_592_000


def test_perm01_le_cookie_de_session_survit_a_la_fermeture_du_navigateur():
    """PERM-01 — « reste connecté » est une propriété du cookie, pas une intention.

    L'exigence dit *stays signed in across sessions*. Rouge, ce test dirait que
    `SESSION_EXPIRE_AT_BROWSER_CLOSE` a repris sa valeur par défaut, ou que
    `SESSION_COOKIE_AGE` a été laissé aux deux semaines de Django sans décision. Un
    opticien qui doit retaper son mot de passe chaque matin est une régression
    silencieuse : rien ne casse, l'usage se dégrade.

    La moitié bout en bout — le cookie réellement émis porte bien un `Max-Age` de trente
    jours — est dans
    `test_perm01_la_reponse_de_connexion_pose_un_cookie_de_trente_jours`, qui a besoin du
    point de terminaison de connexion. Les deux existent parce que le réglage et l'en-tête
    peuvent diverger : `SESSION_EXPIRE_AT_BROWSER_CLOSE = True` produit un cookie de
    session **sans** `Max-Age` alors que `SESSION_COOKIE_AGE` reste parfaitement à trente
    jours.
    """
    from django.conf import settings

    assert settings.SESSION_EXPIRE_AT_BROWSER_CLOSE is False, (
        "SESSION_EXPIRE_AT_BROWSER_CLOSE est vrai : le cookie meurt à la fermeture du "
        "navigateur, ce qui est exactement la régression que PERM-01 interdit."
    )
    assert settings.SESSION_COOKIE_AGE >= TRENTE_JOURS_EN_SECONDES, (
        f"SESSION_COOKIE_AGE vaut {settings.SESSION_COOKIE_AGE} s, soit moins de trente "
        "jours. Le défaut de Django est de quatorze jours : un opticien retaperait son "
        "mot de passe deux fois par mois."
    )


def test_perm01_la_session_n_est_pas_reecrite_a_chaque_requete():
    """T-03-53 — une expiration glissante écrit sur la table la plus chaude de la flotte.

    `SESSION_SAVE_EVERY_REQUEST = True` produit un `UPDATE django_session` **par
    requête**, sur la base du plan de contrôle, c'est-à-dire sur une table unique partagée
    par chaque opticien de la flotte. PERM-01 demande « toujours connecté au retour », pas
    une fenêtre glissante : trente jours fixes le donnent avec **une** écriture, à la
    connexion.

    Rouge, ce test dirait que quelqu'un a activé l'expiration glissante pour régler une
    plainte d'ergonomie — ce qui est le bon problème et la mauvaise solution. Le chemin
    d'évolution est écrit dans `config/settings/base.py`, à côté du réglage.
    """
    from django.conf import settings

    assert settings.SESSION_SAVE_EVERY_REQUEST is False, (
        "SESSION_SAVE_EVERY_REQUEST est vrai : chaque requête de chaque opticien écrit "
        "une ligne sur `django_session`, la table la plus chaude du plan de contrôle."
    )


def test_perm01_les_reglages_drf_pinnent_session_permission_et_renderer():
    """PERM-01 — la pile DRF est la moitié configuration de l'authentification.

    Quatre réglages, quatre propriétés distinctes, et chacun se désactive en une ligne :

    * `SessionAuthentication` **seule** — c'est elle qui appelle `enforce_csrf` par
      requête (`rest_framework/authentication.py:112-133`), donc en retirer la classe
      retire aussi le CSRF de toute l'API sans qu'aucun test de CSRF ne le dise, s'ils
      passent par un autre chemin ;
    * `IsAuthenticated` par défaut — un point de terminaison de phase 6 qui oublierait sa
      classe de permission serait public, et « oublier » est le mode de défaillance qu'un
      défaut fermé supprime ;
    * `JSONRenderer` seul — A-03-06, les listes déroulantes de l'API navigable énumèrent
      des lignes (le source des modules de réglages est vérifié séparément par
      `test_perm06_le_renderer_html_est_absent_hors_developpement`, plan 03-06) ;
    * `ScopedRateThrottle` — sans classe déclarée, `throttle_scope` sur une vue est un
      attribut que **personne ne lit**, et la limitation de débit devient décorative.

    L'assertion porte sur `api_settings`, donc sur ce que DRF utilisera réellement, et non
    sur le dictionnaire écrit dans `base.py` — un réglage écrit sous une mauvaise clé est
    silencieux, et c'est précisément le genre d'erreur qu'un test doit voir.
    """
    from rest_framework.settings import api_settings

    authentification = [c.__name__ for c in api_settings.DEFAULT_AUTHENTICATION_CLASSES]
    assert authentification == ["SessionAuthentication"], (
        f"Les classes d'authentification effectives sont {authentification}. La phase 3 "
        "authentifie par session ; la phase 11 ajoutera une classe de jeton à cette "
        "liste, ce qui sera un changement additif et se relira ici."
    )

    permissions = [c.__name__ for c in api_settings.DEFAULT_PERMISSION_CLASSES]
    assert permissions == ["IsAuthenticated"], (
        f"Les classes de permission par défaut sont {permissions}. Le défaut doit être "
        "fermé : une vue qui oublie sa permission doit refuser, pas servir."
    )

    renderers = [c.__name__ for c in api_settings.DEFAULT_RENDERER_CLASSES]
    assert renderers == ["JSONRenderer"], (
        f"Les renderers effectifs sont {renderers}. Hors développement, l'API ne rend "
        "que du JSON (A-03-06)."
    )

    throttles = [c.__name__ for c in api_settings.DEFAULT_THROTTLE_CLASSES]
    assert "ScopedRateThrottle" in throttles, (
        f"Les classes de limitation sont {throttles}. Sans `ScopedRateThrottle`, "
        "`throttle_scope = \"connexion\"` sur la vue de connexion n'est lu par personne."
    )
    assert api_settings.DEFAULT_THROTTLE_RATES.get("connexion") == "10/min", (
        "La portée `connexion` n'est pas tarifée à 10/min. Une portée sans taux lève "
        "`ImproperlyConfigured` au premier appel — mais seulement si la vue est atteinte."
    )


def test_perm01_la_limitation_ne_fait_pas_confiance_a_un_en_tete_du_client():
    """T-03-47 — `NUM_PROXIES = 0`, sinon la limitation se contourne avec un en-tête.

    `SimpleRateThrottle.get_ident` (vérifié dans le DRF 3.18.1 installé) lit
    `HTTP_X_FORWARDED_FOR` **quand `NUM_PROXIES` vaut `None`**, qui est le défaut. Un
    attaquant qui change cet en-tête à chaque requête obtient donc une clé de cache
    différente à chaque tentative, et la limitation de débit ne limite plus rien du tout —
    en étant parfaitement verte dans un test qui n'envoie pas l'en-tête.

    Zéro plutôt qu'un nombre plausible : la jurisdiction d'hébergement est une décision de
    phase 1 encore ouverte, donc le nombre de proxys de confiance n'est pas connu. Zéro
    fait retomber la clé sur `REMOTE_ADDR`, ce qui, derrière un reverse proxy, rend la
    limitation **globale** plutôt que contournable — trop stricte est le bon côté pour se
    tromper. Le jour où un proxy entre en production, ce réglage est à revoir avec lui, et
    ce test est l'endroit qui le rappellera.
    """
    from rest_framework.settings import api_settings

    assert api_settings.NUM_PROXIES == 0, (
        f"NUM_PROXIES vaut {api_settings.NUM_PROXIES!r}. Avec `None` (le défaut), DRF "
        "dérive l'identité du client depuis `X-Forwarded-For`, un en-tête que l'appelant "
        "choisit — donc la limitation de débit se contourne en le faisant tourner."
    )


def test_app03_le_montant_traverse_le_json_en_chaine_est_epingle():
    """APP-03 / CLAUDE.md #7 — `COERCE_DECIMAL_TO_STRING` est une garantie, pas un défaut.

    C'est le **défaut** de DRF (`rest_framework/settings.py:119`), et c'est exactement la
    raison de l'épingler : un défaut ne se relit pas en revue et se renverse en une ligne,
    typiquement pour faire taire un composant de graphique qui voulait des nombres. Le
    composant a tort — un `DecimalField` rendu en nombre JSON devient un double IEEE-754
    dans le navigateur, et l'écart d'un centime réapparaît des mois plus tard dans une
    réconciliation, sans trace de sa cause.

    Deux assertions, parce qu'elles disent deux choses : la valeur effective est vraie, et
    le nom est **écrit** dans `base.py`. Un réglage qui n'est nulle part dans le source
    est un réglage que personne ne peut décider de garder.
    """
    from pathlib import Path

    from rest_framework.settings import api_settings

    assert api_settings.COERCE_DECIMAL_TO_STRING is True, (
        "COERCE_DECIMAL_TO_STRING est faux : tout montant traverse le JSON en flottant "
        "binaire, ce que CLAUDE.md #7 interdit."
    )
    source = Path("config/settings/base.py").read_text(encoding="utf-8")
    assert "COERCE_DECIMAL_TO_STRING" in source, (
        "Le réglage n'est pas écrit dans `config/settings/base.py`. Reposer sur le défaut "
        "de DRF pour une garantie fiscale est une dépendance invisible."
    )


def test_claude15_aucun_module_de_reglages_ne_pose_atomic_requests():
    """CLAUDE.md #15 — le réglage interdit doit être absent, y compris à `False`.

    `BaseHandler.make_view_atomic()` itère **chaque** alias de `connections.settings` et
    enveloppe la vue dans un `transaction.atomic(using=alias)` pour chacun : avec trois
    cents clients enregistrés, c'est trois cents transactions par requête.

    Le test refuse aussi la forme `ATOMIC_REQUESTS = False`, et ce n'est pas du zèle :
    posée explicitement, elle invite la question « pourquoi est-ce faux ? » et donc
    l'édition d'une seule ligne qui coûte la production. Ce que personne ne lit, personne
    ne bascule. Les alias runtime, eux, sont vérifiés côté registre
    (`tests/test_tenancy_registry.py`), parce qu'ils sont construits en Python et non
    écrits dans un module.
    """
    from pathlib import Path

    fautifs = [
        chemin.name
        for chemin in sorted(Path("config/settings").glob("*.py"))
        if "ATOMIC_REQUESTS" in chemin.read_text(encoding="utf-8")
    ]
    assert not fautifs, (
        f"`ATOMIC_REQUESTS` apparaît dans {fautifs}. CLAUDE.md #15 : le réglage doit être "
        "absent de tous les modules de réglages, même à `False`."
    )


def test_perm01_clearsessions_est_planifie_et_purge_reellement(db):
    """T-03-52 — sans purge, `django_session` grossit sans limite sur la base partagée.

    C'est un déni de service par croissance **et** une responsabilité forensique : une
    ligne de session par connexion de chaque opticien de la flotte, conservée pour
    toujours, sur la base du plan de contrôle. Le contenu, lui, est inoffensif — une clé
    primaire d'utilisateur et un hachage, aucune donnée inter-client — mais le dire
    explicitement vaut mieux que le supposer, parce que la décision de rétention en dépend
    (art. 211 CGI porte sur les **écritures**, pas sur les sessions).

    Deux assertions, et la seconde est celle qui compte. La planification seule passerait
    au-dessus d'une tâche qui ne fait rien : le test crée donc une session **expirée**,
    exécute la tâche, et exige qu'elle ait disparu pendant qu'une session vivante reste.
    """
    from django.conf import settings
    from django.contrib.sessions.backends.db import SessionStore
    from django.contrib.sessions.models import Session
    from django.utils import timezone

    from plateforme.control_plane import tasks

    planifie = [
        entree
        for entree in settings.CELERY_BEAT_SCHEDULE.values()
        if entree["task"] == tasks.clear_expired_sessions.name
    ]
    assert len(planifie) == 1, (
        f"La tâche {tasks.clear_expired_sessions.name!r} apparaît {len(planifie)} fois "
        "dans CELERY_BEAT_SCHEDULE. Sans entrée Beat, elle existe et ne tourne jamais — "
        "la forme d'oubli la plus courante, parce que rien ne la signale."
    )

    expiree = SessionStore()
    expiree["utilisateur"] = 1
    expiree.set_expiry(timezone.now() - timezone.timedelta(days=1))
    expiree.save()
    vivante = SessionStore()
    vivante["utilisateur"] = 2
    vivante.save()

    tasks.clear_expired_sessions()

    assert not Session.objects.filter(pk=expiree.session_key).exists(), (
        "La session expirée est toujours là : la tâche est planifiée mais ne purge rien."
    )
    assert Session.objects.filter(pk=vivante.session_key).exists(), (
        "La tâche a supprimé une session encore valide — elle déconnecterait la flotte."
    )


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
