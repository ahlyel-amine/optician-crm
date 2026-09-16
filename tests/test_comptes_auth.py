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


#: Les chemins, écrits une fois. Un test qui recopie une URL passe le jour où la route
#: change de place, parce qu'il teste alors une 404 bien formée.
CSRF = "/api/auth/csrf/"
CONNEXION = "/api/auth/connexion/"
DECONNEXION = "/api/auth/deconnexion/"
MOI = "/api/auth/moi/"
MOT_DE_PASSE = "/api/auth/mot-de-passe/"

#: L'origine que la SPA presente en developpement : Vite sert sur ce port et le
#: navigateur joint cet en-tete `Origin` a toute ecriture. Ecrite ici parce que deux
#: tests la liront le jour ou un second point de terminaison sera couvert.
ORIGINE_NAVIGATEUR = "http://localhost:5173"


def _client_api(csrf=False):
    from rest_framework.test import APIClient

    return APIClient(enforce_csrf_checks=csrf)


def _connecter(api, utilisateur, mot_de_passe=None):
    from tests.factories import MOT_DE_PASSE_DE_TEST

    return api.post(
        CONNEXION,
        {"email": utilisateur.email, "mot_de_passe": mot_de_passe or MOT_DE_PASSE_DE_TEST},
        format="json",
    )


def test_perm01_la_connexion_etablit_une_session_et_lie_le_client(affaire_reelle):
    """PERM-01 — se connecter doit produire une session *et* lier le locataire.

    Rouge, ce test prouverait que l'identité et la tenancy sont deux choses distinctes
    dans le code : un propriétaire authentifié dont `request.user.client_id` ne remonte
    pas jusqu'au routeur obtient une session parfaitement valide au-dessus d'une couche
    métier qui refuse de tourner — ou pire, qui tombe sur `default`. C'est la couture
    exacte que la phase 2 a laissée ouverte et que la phase 3 referme.

    **La preuve de liaison est la donnée, pas l'alias.** Les deux magasins n'existent que
    dans la base de cet opticien ; aucun ne peut être lu depuis le plan de contrôle. Les
    voir dans la réponse signifie que `TenantMiddleware` a enregistré `tenant_<pk>`, que
    le routeur l'a choisi, et que la requête a traversé les deux. Asserter le nom de
    l'alias aurait passé au-dessus d'un routeur qui lie correctement et lit ailleurs.

    La charge utile de **la réponse de connexion elle-même** est vérifiée, et pas
    seulement celle de la requête suivante : au moment où la vue de connexion s'exécute,
    `TenantMiddleware` a **déjà** tourné avec un utilisateur anonyme, donc rien n'est lié.
    Une vue qui se contenterait d'appeler `login()` et de sérialiser `moi` lèverait
    `NoTenantBound`. C'est la seule subtilité réelle de ce point de terminaison.
    """
    from tests.factories import ProprietaireFactory

    proprietaire = ProprietaireFactory(client=affaire_reelle.client)
    api = _client_api()

    reponse = _connecter(api, proprietaire)
    assert reponse.status_code == 200, reponse.data
    assert "sessionid" in api.cookies, (
        "Aucun cookie de session n'a été posé : la réponse est peut-être correcte, mais "
        "rien n'a été établi."
    )
    assert reponse.data["client"]["raison_sociale"] == "Optique Bennani SARL"
    assert {m["code"] for m in reponse.data["magasins"]} == {"AUTHANFA", "AUTHMAARIF"}, (
        "La réponse de connexion ne porte pas les magasins de l'affaire. La vue doit lier "
        "le locataire elle-même : `TenantMiddleware` a tourné avant `login()`, donc avec "
        "un utilisateur anonyme."
    )

    suivante = api.get(MOI)
    assert suivante.status_code == 200, suivante.data
    assert {m["code"] for m in suivante.data["magasins"]} == {"AUTHANFA", "AUTHMAARIF"}, (
        "La requête suivante ne lit pas la base du client. La session est valide et la "
        "couche métier ne l'est pas — exactement la moitié de couture que PERM-01 ferme."
    )


def test_perm01_la_reponse_de_connexion_pose_un_cookie_de_trente_jours(affaire_reelle):
    """PERM-01 — la moitié bout en bout de « reste connecté ».

    Le réglage et l'en-tête peuvent diverger : `SESSION_EXPIRE_AT_BROWSER_CLOSE = True`
    produit un cookie **sans** `Max-Age` alors que `SESSION_COOKIE_AGE` reste parfaitement
    à trente jours, et un test qui ne lit que les réglages resterait vert. Ce test lit
    l'en-tête réellement émis.
    """
    from tests.factories import ProprietaireFactory

    proprietaire = ProprietaireFactory(client=affaire_reelle.client)
    reponse = _connecter(_client_api(), proprietaire)

    cookie = reponse.cookies["sessionid"]
    assert cookie["max-age"], (
        "Le cookie de session ne porte aucun `Max-Age` : c'est un cookie de session au "
        "sens du navigateur, qui meurt à la fermeture de l'onglet."
    )
    assert int(cookie["max-age"]) >= TRENTE_JOURS_EN_SECONDES


def test_perm01_lechec_de_connexion_ne_distingue_jamais_les_motifs(affaire_reelle):
    """T-03-48 — trois causes, une seule réponse, au caractère près.

    Un compte inconnu, un mot de passe faux et un compte **désactivé** doivent produire
    exactement la même réponse. La troisième est celle qu'on oublie, et c'est la plus
    coûteuse : un gérant congédié ne doit pas l'apprendre de l'écran de connexion, c'est
    le propriétaire qui le lui dit. Une réponse distincte transforme aussi l'écran en
    oracle d'énumération de comptes pour toute la flotte, puisqu'il n'y a qu'une adresse
    de connexion (CLAUDE.md #11).

    L'assertion porte sur le **corps entier** et pas seulement sur le code de statut :
    c'est un champ, un mot ou une clé en plus qui fait la différence, et un test qui ne
    compare que `status_code` laisserait passer `{"detail": ..., "compte_desactive": true}`.
    """
    from tests.factories import MOT_DE_PASSE_DE_TEST, GerantFactory

    gerant = GerantFactory(client=affaire_reelle.client)
    desactive = GerantFactory(client=affaire_reelle.client, is_active=False)

    inconnu = _client_api().post(
        CONNEXION,
        {"email": "personne@nulle-part.test", "mot_de_passe": MOT_DE_PASSE_DE_TEST},
        format="json",
    )
    faux = _connecter(_client_api(), gerant, mot_de_passe="ce-n-est-pas-le-bon")
    ferme = _connecter(_client_api(), desactive)

    reponses = [inconnu, faux, ferme]
    assert {r.status_code for r in reponses} == {400}, (
        f"Les statuts sont {[r.status_code for r in reponses]}. Ils doivent être "
        "identiques, et 400 plutôt que 401 : l'interface réserve 401 à la session expirée "
        "et y branche une redirection globale vers `/connexion` (UI 8.6)."
    )
    corps = [r.json() for r in reponses]
    assert corps[0] == corps[1] == corps[2], (
        f"Les corps diffèrent : {corps}. Compte inconnu, mot de passe faux et compte "
        "désactivé doivent être indiscernables."
    )
    assert corps[0] == {"detail": "Identifiant ou mot de passe incorrect."}


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


def test_perm01_la_deconnexion_invalide_la_session_immediatement(affaire_reelle):
    """PERM-01 — se déconnecter doit détruire la session côté serveur, pas le cookie.

    Rouge, ce test signalerait une déconnexion qui se contente de supprimer le cookie du
    navigateur : la clé de session reste valide côté serveur, donc quiconque l'a captée
    reste authentifié. Le test **rejoue la clé** après la déconnexion et exige un refus —
    sans cela il ne vérifierait que le comportement du bocal à cookies du client de test,
    qui n'est la garantie de personne.

    C'est aussi la moitié « révocation » de l'argument session-contre-jeton : il n'y a
    aucune fenêtre d'expiration à attendre, parce qu'il n'y a rien à expirer. La ligne
    n'existe plus.
    """
    from django.contrib.sessions.models import Session

    from tests.factories import ProprietaireFactory

    proprietaire = ProprietaireFactory(client=affaire_reelle.client)
    api = _client_api()
    _connecter(api, proprietaire)
    cle = api.cookies["sessionid"].value
    assert Session.objects.filter(pk=cle).exists()

    assert api.post(DECONNEXION).status_code == 204

    assert not Session.objects.filter(pk=cle).exists(), (
        "La ligne de session existe encore : la déconnexion a vidé le cookie et laissé "
        "la session valide côté serveur."
    )
    api.cookies["sessionid"] = cle
    assert api.get(MOI).status_code == 401, (
        "La clé rejouée est encore acceptée. Une déconnexion qui ne révoque pas n'est pas "
        "une déconnexion."
    )


def test_perm01_la_connexion_est_limitee_en_debit(affaire_reelle):
    """PERM-01 — une adresse de connexion unique pour toute la flotte se brute-force.

    CLAUDE.md #11 : il y a **une** adresse de connexion partagée par tous les opticiens.
    C'est donc un point unique où essayer des mots de passe contre n'importe quel compte
    de n'importe quelle affaire. Rouge, ce test dirait que ce point est ouvert sans
    limite. Argon2 rend chaque essai coûteux, ce qui est aussi une raison de limiter :
    sans plafond, l'essai coûteux devient un déni de service contre notre propre CPU.

    Le compteur vit dans le cache, que `conftest.py` vide avant chaque test — sans quoi
    les onze tentatives d'ici feraient échouer le **test suivant** qui se connecte, dans
    un autre fichier, pour une cause invisible depuis lui. Observé, pas supposé.

    Le onzième essai est fait avec les **bons** identifiants, délibérément : la limitation
    doit s'appliquer avant l'authentification, sinon un attaquant qui trouve le mot de
    passe à la onzième tentative entre quand même.
    """
    from tests.factories import MOT_DE_PASSE_DE_TEST, ProprietaireFactory

    proprietaire = ProprietaireFactory(client=affaire_reelle.client)
    api = _client_api()

    for essai in range(10):
        reponse = _connecter(api, proprietaire, mot_de_passe="faux")
        assert reponse.status_code == 400, (
            f"L'essai {essai + 1} a reçu {reponse.status_code} au lieu de 400 : la "
            "fenêtre est plus étroite que dix, ou le compteur a fuité d'un autre test."
        )

    onzieme = _connecter(api, proprietaire, mot_de_passe=MOT_DE_PASSE_DE_TEST)
    assert onzieme.status_code == 429, (
        f"La onzième tentative a reçu {onzieme.status_code}. Avec les bons identifiants, "
        "cela signifie que la limitation s'applique après l'authentification — donc pas "
        "du tout, pour qui cherche un mot de passe."
    )


def test_perm01_le_429_porte_la_copie_francaise_et_un_delai_exploitable(affaire_reelle):
    """`03-UI-SPEC.md` 6 — l'écran affiche un compte à rebours vivant, il lui faut un nombre.

    Deux exigences distinctes, et la seconde est celle qu'on oublie. La copie doit être
    **exactement** celle de la spécification — `Throttled` de DRF y concatène sinon
    « Disponible dans N secondes. », une phrase que l'interface devrait analyser pour en
    extraire sa durée. Et le délai doit arriver dans un **champ**, pas dans la phrase :
    la ligne d'aide décompte et le bouton reste désactivé pendant la fenêtre.

    `Retry-After` est vérifié en plus, parce que c'est ce que lit un client HTTP qui n'est
    pas notre SPA — la phase 11 en aura un autre.
    """
    from tests.factories import ProprietaireFactory

    proprietaire = ProprietaireFactory(client=affaire_reelle.client)
    api = _client_api()
    for _ in range(11):
        reponse = _connecter(api, proprietaire, mot_de_passe="faux")

    assert reponse.status_code == 429
    corps = reponse.json()
    assert corps["detail"] == "Trop de tentatives. Réessayez dans une minute.", (
        f"La copie servie est {corps['detail']!r}. `03-UI-SPEC.md` 6 en fixe le texte au "
        "caractère près."
    )
    assert isinstance(corps["reessayer_dans"], int) and 0 < corps["reessayer_dans"] <= 60, (
        f"`reessayer_dans` vaut {corps.get('reessayer_dans')!r}. L'interface en fait un "
        "compte à rebours : il lui faut un entier de secondes, pas une phrase."
    )
    assert reponse.headers["Retry-After"] == str(corps["reessayer_dans"])


def test_perm01_un_en_tete_x_forwarded_for_ne_contourne_pas_la_limitation(affaire_reelle):
    """T-03-47 — la moitié comportementale du réglage `NUM_PROXIES`.

    `SimpleRateThrottle.get_ident` lit `X-Forwarded-For` quand `NUM_PROXIES` vaut `None`,
    qui est le **défaut** de DRF. Un attaquant qui change l'en-tête à chaque requête
    obtient alors une clé de cache neuve à chaque tentative, et la limitation ne limite
    plus rien — tout en restant parfaitement verte dans un test qui n'envoie pas
    l'en-tête, c'est-à-dire dans le test précédent.

    Ce test envoie une adresse différente à chaque essai. Le compteur doit malgré tout
    atteindre son plafond.
    """
    from tests.factories import ProprietaireFactory

    proprietaire = ProprietaireFactory(client=affaire_reelle.client)
    api = _client_api()

    for essai in range(11):
        reponse = api.post(
            CONNEXION,
            {"email": proprietaire.email, "mot_de_passe": "faux"},
            format="json",
            headers={"x-forwarded-for": f"203.0.113.{essai}"},
        )

    assert reponse.status_code == 429, (
        f"Onze tentatives depuis onze `X-Forwarded-For` différents ont reçu "
        f"{reponse.status_code}. La limitation se contourne avec un en-tête que "
        "l'appelant choisit, donc elle n'existe pas."
    )


def test_perm01_aucun_corps_derreur_ne_renvoie_lidentifiant_soumis(affaire_reelle):
    """A-03-13 / T-03-55 — un corps d'erreur ne renvoie ni l'identifiant, ni la mécanique.

    Deux fuites différentes, vérifiées ensemble parce qu'elles sortent par la même porte.

    **L'identifiant soumis**, d'abord : un corps qui le reprend transforme la page de
    connexion en miroir. Cela paraît inoffensif — l'appelant connaît déjà ce qu'il a
    envoyé — jusqu'à ce que la valeur atterrisse dans un journal, dans un rapport Sentry
    ou dans une capture d'écran de support, et une adresse e-mail est une donnée
    personnelle au sens de la loi 09-08.

    **La mécanique interne**, ensuite : `NoTenantBound` nomme des alias et la façon dont
    la liaison de locataire fonctionne. C'est déjà la règle ASVS V7 de la phase 2, étendue
    ici à la résolution d'accès. Le cas est réel : un compte rattaché à une affaire non
    `ACTIVE` traverse l'authentification et ne peut pas lire sa base — il doit recevoir un
    503 sans cause, pas un 500 avec une trace.

    Le balayage couvre les quatre formes d'échec qu'un attaquant peut provoquer depuis
    l'écran de connexion, parce que celle qui fuit est toujours celle qu'on n'a pas
    listée.
    """
    from plateforme.control_plane.models import Client
    from tests.factories import MOT_DE_PASSE_DE_TEST, GerantFactory

    desactive = GerantFactory(client=affaire_reelle.client, is_active=False)
    adresse = "karim.bennani@optique-anfa.test"

    corps_a_examiner = []
    for donnees in (
        {"email": adresse, "mot_de_passe": "faux"},
        {"email": adresse},
        {"email": "pas-une-adresse", "mot_de_passe": "faux"},
        {"email": desactive.email, "mot_de_passe": MOT_DE_PASSE_DE_TEST},
    ):
        reponse = _client_api().post(CONNEXION, donnees, format="json")
        assert reponse.status_code in (400, 429), reponse.status_code
        corps_a_examiner.append(reponse.content.decode())

    for corps in corps_a_examiner:
        assert adresse not in corps and desactive.email not in corps, (
            f"Un corps d'erreur renvoie l'identifiant soumis : {corps}"
        )

    # La seconde moitié : une affaire authentifiable mais non joignable. Un gérant et
    # non un propriétaire, parce que `un_seul_proprietaire_par_client` est une contrainte
    # d'unicité partielle et que la fixture n'en crée pas — mais un test qui en demande
    # deux l'apprend par une `IntegrityError` à mi-parcours, ce qui est le bon refus au
    # mauvais moment.
    orpheline = GerantFactory(
        client=affaire_reelle.client, email="orphelin@optique.test"
    )
    Client.objects.using("default").filter(pk=affaire_reelle.client.pk).update(
        status=Client.SUSPENDED
    )
    api = _client_api()
    reponse = _connecter(api, orpheline)

    assert reponse.status_code == 503, (
        f"Un compte dont l'affaire n'est pas joignable a reçu {reponse.status_code}. "
        "Sans traitement, `NoTenantBound` remonte en 500 — et en développement, avec sa "
        "trace."
    )
    corps = reponse.content.decode()
    for fuite in ("NoTenantBound", "tenant_", "alias", orpheline.email):
        assert fuite not in corps, (
            f"Le corps du 503 contient {fuite!r} : {corps}"
        )


def test_perm01_une_requete_api_sans_jeton_csrf_est_refusee(affaire_reelle):
    """PERM-01 — le prix du cookie de session est le CSRF, et il se paie explicitement.

    L'authentification par cookie signifie que le navigateur joint la preuve
    d'authentification à **toute** requête vers notre origine, y compris celle qu'un autre
    site déclenche. Rouge, ce test dirait qu'une écriture passe sans jeton — donc qu'une
    page tierce peut créer un compte gérant ou accorder un droit au nom d'un propriétaire
    connecté. `SessionAuthentication` de DRF impose le CSRF ; ce test constate qu'on ne
    l'a pas contourné avec un `csrf_exempt` posé pour débloquer un test.

    **Le contrôle positif est la moitié qui compte.** Un point de terminaison cassé refuse
    aussi sans jeton, et un test qui n'assert que le refus serait vert au-dessus d'une
    route morte. La même requête, avec le jeton, doit réussir.

    Le jeton est relu **après** la connexion, délibérément : `django.contrib.auth.login`
    appelle `rotate_token`, donc le jeton obtenu avant vaut pour la connexion et plus rien
    après. Une SPA qui le mettrait en cache à l'amorçage casserait à la première écriture,
    et ce test l'aurait dit.
    """
    from tests.factories import MOT_DE_PASSE_DE_TEST, ProprietaireFactory

    proprietaire = ProprietaireFactory(client=affaire_reelle.client)
    api = _client_api(csrf=True)

    amorce = api.get(CSRF)
    assert amorce.status_code == 204
    assert "csrftoken" in api.cookies, (
        "`/api/auth/csrf/` n'a posé aucun cookie. La SPA n'a alors aucun jeton à renvoyer "
        "et la première écriture est refusée sans qu'on sache pourquoi."
    )

    connexion = api.post(
        CONNEXION,
        {"email": proprietaire.email, "mot_de_passe": MOT_DE_PASSE_DE_TEST},
        format="json",
        headers={"x-csrftoken": api.cookies["csrftoken"].value},
    )
    assert connexion.status_code == 200, connexion.data

    jeton = api.cookies["csrftoken"].value
    corps = {
        "mot_de_passe_actuel": MOT_DE_PASSE_DE_TEST,
        "nouveau_mot_de_passe": "correct-cheval-batterie-agrafe",
    }

    sans = api.post(MOT_DE_PASSE, corps, format="json")
    assert sans.status_code == 403, (
        f"Une écriture authentifiée sans jeton CSRF a reçu {sans.status_code}. Une page "
        "tierce peut alors agir au nom d'un opticien connecté."
    )

    avec = api.post(MOT_DE_PASSE, corps, format="json", headers={"x-csrftoken": jeton})
    assert avec.status_code == 200, (
        f"La même écriture *avec* jeton a reçu {avec.status_code} : le refus ci-dessus ne "
        "prouvait donc rien sur le CSRF."
    )


def test_perm01_une_requete_avec_en_tete_origin_n_est_pas_refusee_par_le_csrf(affaire_reelle):
    """PERM-01 — le contrôle d'origine du CSRF doit accepter l'origine du navigateur.

    **Pourquoi ce test existe.** La suite entière était verte pendant qu'un vrai
    navigateur était refusé en 403 sur `/api/auth/connexion/`, avec
    « Origin checking failed - http://localhost:5173 does not match any trusted
    origins. » Aucun test n'envoyait d'en-tête `Origin`, et Django saute
    **intégralement** le contrôle d'origine quand l'en-tête est absent en HTTP simple
    (`CsrfViewMiddleware.process_view`). La même requête curl passe de 200 à 403 selon la
    seule présence de `-H "Origin: ..."`. Ce test est le trou refermé : sans lui, la
    régression revient sans que rien ne rougisse.

    **Pourquoi l'hôte reste `testserver`.** `setup_test_environment()` l'ajoute à
    `ALLOWED_HOSTS` et le client de test le présente. On ne le change pas : le défaut
    reproduit ici est précisément une origine qui **diffère** de l'hôte vu par Django,
    ce que produisait le proxy Vite en réécrivant `Host` en `127.0.0.1:8010`.

    **Pourquoi la liste vient de `config.settings.local`.** `config/settings/test.py` fait
    `from .base import *` et ne lit jamais `local.py`, donc `CSRF_TRUSTED_ORIGINS` est
    absent du run de tests — et doit le rester. Le test importe donc la liste
    **réellement livrée** aux développeurs et l'applique par `override_settings`. Une
    constante recopiée dans le test resterait verte le jour où `local.py` perd l'entrée.

    **Piège Django, vérifié dans le 6.1.x installé — à connaître avant d'écrire un autre
    test qui envoie un `Origin`.** `csrf_protect` est
    `decorator_from_middleware(CsrfViewMiddleware)`, et `make_middleware_decorator`
    (`django/utils/decorators.py`) instancie le middleware **une seule fois, à l'import du
    module de vues**. `allowed_origins_exact` et `csrf_trusted_origins_hosts` sont des
    `cached_property` (`django/middleware/csrf.py`), et `django/test/signals.py` ne
    contient **aucun** récepteur qui les invalide sur `setting_changed`. La première
    requête du processus portant un `Origin` qui ne correspond pas à l'hôte fige donc la
    liste **pour tout le processus**. Conséquence tenue ici : les deux jambes partagent
    **un seul** `override_settings`. Deux overrides successifs avec deux valeurs
    différentes donneraient silencieusement la première valeur aux deux, et le second
    test serait vert ou rouge sans rapport avec ce qu'il croit mesurer.
    """
    from django.test import override_settings

    import config.settings.local as reglages_dev
    from tests.factories import MOT_DE_PASSE_DE_TEST, ProprietaireFactory

    origines = list(getattr(reglages_dev, "CSRF_TRUSTED_ORIGINS", []))
    proprietaire = ProprietaireFactory(client=affaire_reelle.client)

    with override_settings(CSRF_TRUSTED_ORIGINS=origines):
        # `enforce_csrf_checks=True` est obligatoire : sans lui le handler de test pose
        # `request._dont_enforce_csrf_checks = True`, `csrf_protect` rend la main sans
        # rien vérifier, et ce test serait vert au-dessus du défaut.
        api = _client_api(csrf=True)

        amorce = api.get(CSRF)
        assert amorce.status_code == 204
        jeton = api.cookies["csrftoken"].value

        identifiants = {
            "email": proprietaire.email,
            "mot_de_passe": MOT_DE_PASSE_DE_TEST,
        }

        # Jambe A, le contrôle positif du refus : identifiants valides, jeton valide,
        # origine tierce. Elle prouve que le contrôle d'origine est vivant — donc que la
        # jambe B ne passera pas parce qu'on aurait désarmé le CSRF quelque part.
        tierce = api.post(
            CONNEXION,
            identifiants,
            format="json",
            headers={"origin": "http://malveillant.example", "x-csrftoken": jeton},
        )
        assert tierce.status_code == 403, (
            f"Une connexion depuis une origine tierce a reçu {tierce.status_code} au lieu "
            "de 403. Le contrôle d'origine ne tourne plus : `csrf_protect` a disparu de "
            "`VueConnexion`, le client de test n'impose pas le CSRF, ou toute origine est "
            "devenue de confiance. Le login CSRF est une vraie attaque — on force une "
            "victime dans la session de l'attaquant."
        )

        # Jambe B, la régression. En dernier, parce que c'est la seule qui réussit, donc
        # la seule qui fasse tourner le jeton via `rotate_token`.
        navigateur = api.post(
            CONNEXION,
            identifiants,
            format="json",
            headers={"origin": ORIGINE_NAVIGATEUR, "x-csrftoken": jeton},
        )
        assert navigateur.status_code != 403, (
            f"Une connexion portant `Origin: {ORIGINE_NAVIGATEUR}` a été refusée en 403. "
            "L'origine du navigateur n'est de confiance nulle part : CSRF_TRUSTED_ORIGINS "
            f"vaut {origines!r} dans config/settings/local.py, et le proxy de "
            "développement réécrit peut-être encore l'en-tête Host (forme chaîne du proxy "
            "Vite, donc `changeOrigin: true` par défaut)."
        )
        assert navigateur.status_code == 200, (
            f"La connexion depuis l'origine du navigateur a reçu {navigateur.status_code} "
            f"au lieu de 200 : {getattr(navigateur, 'data', None)!r}"
        )


def test_perm01_moi_ne_rend_que_les_magasins_accordes_et_le_catalogue(affaire_reelle):
    """PERM-01 / PERM-04 — l'amorçage de la SPA en une requête, et sa portée.

    Trois propriétés, et chacune a son mode de défaillance :

    * **les magasins sont ceux de `acces.magasins_ids`**, jamais tous ceux du client. Le
      sélecteur de la barre supérieure est construit depuis cette liste (UI 5.4) : la
      renvoyer entière donnerait à un gérant d'Anfa un menu déroulant contenant Maârif,
      c'est-à-dire une énumération des magasins qu'il n'a pas ;
    * **`permissions` est calculé avec `peut_quelque_part`** — l'union — parce qu'une
      entrée de navigation doit apparaître dès que le droit est détenu *quelque part* :
      un gérant qui gère le stock du seul magasin de Casablanca perdrait l'entrée Stock
      sous la conjonction. Ce champ ne décide donc **rien** d'autre que l'affichage d'un
      menu, et la projection serveur reste seule juge des données (UI 8.3) ;
    * **le catalogue vient du serveur**, libellés et explications compris, pour que la SPA
      n'ait jamais à coder un libellé de droit en dur (UI 7.4) et qu'un code ajouté en
      phase 8 apparaisse sans changement côté client.
    """
    from plateforme.comptes.permissions_catalogue import PREREQUIS, SECTIONS, Permission
    from tests.factories import (
        AccesMagasinFactory,
        DroitAccordeFactory,
        GerantFactory,
    )

    gerant = GerantFactory(client=affaire_reelle.client)
    AccesMagasinFactory(utilisateur=gerant, magasin_code="AUTHANFA")
    DroitAccordeFactory(
        utilisateur=gerant, magasin_code="AUTHANFA", code=Permission.STOCK_VOIR
    )

    api = _client_api()
    _connecter(api, gerant)
    charge = api.get(MOI).json()

    assert [m["code"] for m in charge["magasins"]] == ["AUTHANFA"], (
        f"`moi` renvoie {charge['magasins']}. Il doit renvoyer les magasins accordés, pas "
        "ceux de l'affaire : la liste alimente le sélecteur de magasin."
    )
    assert charge["permissions"] == [Permission.STOCK_VOIR.value], (
        f"`permissions` vaut {charge['permissions']}. C'est l'union des droits détenus "
        "quelque part, et rien de plus."
    )
    assert charge["utilisateur"]["email"] == gerant.email
    assert charge["utilisateur"]["est_proprietaire"] is False
    assert "password" not in charge["utilisateur"]

    titres = [section["titre"] for section in charge["catalogue"]["sections"]]
    assert titres == [section.titre for section in SECTIONS]
    codes_servis = {
        droit["code"]
        for section in charge["catalogue"]["sections"]
        for droit in section["droits"]
    }
    assert codes_servis == set(Permission.values), (
        "Le catalogue servi ne couvre pas les 21 codes. Un code absent est un droit que "
        "le propriétaire ne peut pas accorder et que personne ne remarque."
    )
    assert charge["catalogue"]["prerequis"] == {
        code: list(requis) for code, requis in PREREQUIS.items()
    }


def test_perm01_le_changement_de_mot_de_passe_efface_le_drapeau(affaire_reelle):
    """PERM-01 — le chemin sans courriel, et la seule chose qui le rende acceptable.

    Il n'existe aucun fournisseur d'e-mail transactionnel dans la pile, donc
    `PasswordResetView` ne peut pas fonctionner : le propriétaire pose le mot de passe
    initial d'un gérant, `doit_changer_mot_de_passe` force le changement à la première
    connexion, et un propriétaire qui oublie le sien est réinitialisé par l'opérateur.
    Ce test tient la seule moitié automatisable : le drapeau tombe **parce que le mot de
    passe a changé**, et l'ancien ne vaut plus rien.

    Le mot de passe actuel est exigé. Sans lui, un poste laissé déverrouillé une minute —
    ou un CSRF réussi — donne un compte, définitivement, plutôt qu'une session.
    """
    from tests.factories import MOT_DE_PASSE_DE_TEST, GerantFactory

    gerant = GerantFactory(client=affaire_reelle.client, doit_changer_mot_de_passe=True)
    api = _client_api()
    assert _connecter(api, gerant).data["utilisateur"]["doit_changer_mot_de_passe"] is True

    refuse = api.post(
        MOT_DE_PASSE,
        {"mot_de_passe_actuel": "pas-le-bon", "nouveau_mot_de_passe": "orage-pluie-soleil-42"},
        format="json",
    )
    assert refuse.status_code == 400, (
        "Le changement a été accepté sans le mot de passe actuel : une session volée "
        "devient un compte volé."
    )

    accepte = api.post(
        MOT_DE_PASSE,
        {
            "mot_de_passe_actuel": MOT_DE_PASSE_DE_TEST,
            "nouveau_mot_de_passe": "orage-pluie-soleil-42",
        },
        format="json",
    )
    assert accepte.status_code == 200, accepte.data

    gerant.refresh_from_db()
    assert gerant.doit_changer_mot_de_passe is False
    assert gerant.check_password("orage-pluie-soleil-42")
    assert not gerant.check_password(MOT_DE_PASSE_DE_TEST)


def test_perm01_un_mot_de_passe_trivial_est_refuse_en_francais(affaire_reelle):
    """PERM-01 — `validate_password` sans validateurs déclarés est un no-op silencieux.

    Django ne pose aucun `AUTH_PASSWORD_VALIDATORS` par défaut dans un projet écrit à la
    main : appeler `validate_password` sans les déclarer valide alors `1234`. Le réglage
    et l'appel doivent exister ensemble, sinon le point de terminaison a l'air protégé et
    ne l'est pas.

    Le message est français parce que tout le produit l'est (APP-01) — et il vient des
    traductions de Django, pas d'une chaîne recopiée.
    """
    from tests.factories import MOT_DE_PASSE_DE_TEST, GerantFactory

    gerant = GerantFactory(client=affaire_reelle.client)
    api = _client_api()
    _connecter(api, gerant)

    reponse = api.post(
        MOT_DE_PASSE,
        {"mot_de_passe_actuel": MOT_DE_PASSE_DE_TEST, "nouveau_mot_de_passe": "1234"},
        format="json",
    )
    assert reponse.status_code == 400, (
        "« 1234 » a été accepté comme mot de passe. `AUTH_PASSWORD_VALIDATORS` est vide, "
        "ou `validate_password` n'est pas appelé."
    )
    corps = str(reponse.json())
    assert "mot de passe" in corps.lower(), (
        f"Le message d'erreur n'est pas en français : {corps}"
    )
