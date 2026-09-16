---
phase: 03-comptes-permissions-app-shell
plan: 08
subsystem: authentification-de-session-et-amorcage-spa
tags: [auth, session, csrf, throttling, drf, openapi, PERM-01, PERM-02, T-03-47, T-03-48, T-03-49, T-03-50, T-03-51, T-03-52, T-03-53, T-03-55]
requires:
  - 03-05 (Acces, acces_pour, AccesMiddleware, l'etiquette `navigation` de peut_quelque_part)
  - 03-06 (SerializerProjete, CHAMPS_PUBLICS, REST_FRAMEWORK et le renderer JSON seul)
  - 03-04 (permissions_catalogue : Permission, SECTIONS, EXPLICATIONS, PREREQUIS)
  - 03-01 (Utilisateur, Argon2 en tete de PASSWORD_HASHERS, REVOKE sur optique_control)
  - 02-03 (TenantMiddleware, resolve_client, tenant_context, register_client_database)
provides:
  - "GET /api/auth/csrf/ — ensure_csrf_cookie, 204, anonyme"
  - "POST /api/auth/connexion/ — session, amorcage complet, throttle `connexion`, csrf_protect"
  - "POST /api/auth/deconnexion/ — logout(), 204, revocation immediate"
  - "GET /api/auth/moi/ — l'amorcage de la SPA en une requete"
  - "POST /api/auth/mot-de-passe/ — changement par l'interesse, efface doit_changer_mot_de_passe"
  - "plateforme/comptes/views.py:gestionnaire_dexceptions — 401 rendu a NotAuthenticated, 503 a NoTenantBound"
  - "plateforme/comptes/serializers.py:charge_utile_moi et AmorcageSerializer (le composant OpenAPI)"
  - "control_plane.clear_expired_sessions + l'entree CELERY_BEAT_SCHEDULE"
  - "conftest.py:affaire_reelle — une affaire dont l'alias runtime tenant_<pk> est joignable"
  - "conftest.py:cache_vide — isolation autouse du compteur de limitation"
affects:
  - 03-09 (service d'octroi : consomme le catalogue, le second usage sanctionne de peut_quelque_part, et la politique de mot de passe pour le mot de passe initial d'un gerant)
  - 03-10 (schema commite : les cinq routes y entrent, avec le composant Amorcage)
  - 03-12 et 03-13 (la SPA : /connexion, /mot-de-passe, le selecteur de magasin, la navigation)
  - phase 11 (Expo : ajouter une classe de jeton a DEFAULT_AUTHENTICATION_CLASSES, additivement)
  - phase 12 (inscription en libre service : a besoin du fournisseur d'e-mail que ce plan n'a pas)
tech-stack:
  added: []
  patterns:
    - "un echec d'authentification a une seule reponse, parce qu'il n'a qu'un seul chemin de code"
    - "un code de statut est un contrat d'interface : 400 pour un echec de connexion, 401 pour une session morte, 403 pour un droit manquant, 429 pour une limite, 503 pour une affaire injoignable"
    - "un ModelSerializer sur une table sensible est un garde-fou : le champ non classe rend la suite rouge"
    - "une APIView sans extend_schema est ignoree par drf-spectacular — absente du contrat, en silence"
    - "tout ce qui derive de la securite vient du serveur : REMOTE_ADDR et non X-Forwarded-For, des deux cotes (audit et limitation)"
key-files:
  created:
    - plateforme/comptes/views.py
    - plateforme/comptes/serializers.py
    - plateforme/comptes/urls.py
  modified:
    - config/settings/base.py
    - config/settings/test.py
    - config/urls.py
    - conftest.py
    - plateforme/control_plane/tasks.py
    - plateforme/projection/registre.py
    - tests/test_comptes_auth.py
    - tests/test_comptes_droits.py
key-decisions:
  - "La vue de connexion lie le locataire elle-meme : TenantMiddleware a deja tourne avec un utilisateur anonyme, donc une vue qui se contenterait de login() puis de serialiser leverait NoTenantBound"
  - "L'echec de connexion est un 400, jamais un 401 : l'interface branche sur 401 une redirection globale vers /connexion (UI 8.6), qui se declencherait alors depuis l'ecran de connexion lui-meme"
  - "NUM_PROXIES = 0 : le defaut None laisse DRF deriver l'identite du client de X-Forwarded-For, donc la limitation se contourne par un en-tete"
  - "Un gestionnaire d'exceptions plutot qu'une sous-classe d'authentification : DEFAULT_AUTHENTICATION_CLASSES reste la classe DRF de serie, que la phase 11 completera sans heriter de la notre"
  - "csrf_protect sur la connexion : les vues DRF sont csrf_exempt et SessionAuthentication n'impose le CSRF qu'aux deja authentifies, donc sans lui la connexion serait la seule ecriture non protegee"
  - "Les champs de l'amorcage entrent dans CHAMPS_PUBLICS : sur control_plane.Client, c'est ce qui rend rouge l'ajout de db_name ou du mot de passe chiffre a la charge utile"
  - "NoTenantBound devient un 503 sans cause : un compte rattache a une affaire non ACTIVE traverse l'authentification et ne peut pas lire sa base"
patterns-established:
  - "Une reponse d'erreur ne nomme jamais l'identifiant soumis ni la mecanique interne — balaye par test sur quatre formes d'echec"
  - "Toute nouvelle APIView porte un extend_schema dans le plan qui la cree, sinon elle n'existe pas dans le contrat TypeScript"
  - "Tout nouveau champ de modele expose rejoint CHAMPS_PROTEGES ou CHAMPS_PUBLICS dans le meme commit"
requirements-completed: [PERM-01]
duration: 75min
completed: 2026-09-16
---

# Phase 3 Plan 08 : l'authentification par session et l'amorçage de la SPA — Summary

**Cinq points de terminaison sous `/api/auth/`, une session de trente jours qui lie le
locataire dès la réponse de connexion, un échec de connexion indiscernable quel qu'en soit
le motif, et une limitation de débit qu'un en-tête ne contourne pas.**

## Performance

- **Durée :** ~75 min
- **Tâches :** 3 sur 3
- **Fichiers :** 3 créés, 8 modifiés
- **Suite :** 128 → **148** tests rapides au vert, plus 30 `slow`. Les `pending` passent de 45 à 39 : six marqueurs retirés, aucun ajouté.

## Ce qui a été livré

| Route | Auth | Ce qu'elle fait |
|---|---|---|
| `GET /api/auth/csrf/` | anonyme | `ensure_csrf_cookie`, 204 vide |
| `POST /api/auth/connexion/` | anonyme, `csrf_protect`, portée `connexion` | `authenticate` → `login` → **l'amorçage complet** |
| `POST /api/auth/deconnexion/` | session | `logout()`, 204 |
| `GET /api/auth/moi/` | session | compte, affaire, navigation, magasins accordés, catalogue |
| `POST /api/auth/mot-de-passe/` | session | changement par l'intéressé, efface `doit_changer_mot_de_passe` |

## La seule subtilité réelle : la connexion doit lier le locataire elle-même

C'est le point que le plan nomme et qu'il vaut la peine de réécrire ici, parce que rien
dans le code ne le signale à la lecture.

`TenantMiddleware` tourne **avant** la vue. Au moment où il s'exécute sur un POST de
connexion, `request.user` est anonyme — la session n'existe pas encore. Il ne lie donc
rien. Une vue de connexion qui appellerait `login(request, user)` puis sérialiserait
l'amorçage lèverait `NoTenantBound` à la première ligne qui lit `Magasin`.

`_amorcage()` lie donc explicitement, **par le même chemin que le middleware** —
`resolve_client`, `register_client_database`, `alias_for`, `tenant_context` — plutôt qu'en
réimplémentant la résolution. `tenant_context` restaure la valeur englobante en sortant,
donc l'appel depuis `/api/auth/moi/`, où l'alias est *déjà* lié, ne dérange rien : la
fonction commence par `is_bound()` et ne relie pas.

Le test le vérifie sur **la réponse de connexion elle-même**, et pas seulement sur la
requête suivante. Sans cette assertion, une vue renvoyant un 200 vide passerait, et la
SPA découvrirait le problème au premier écran.

## Les codes de statut sont un contrat, et ils ont été décidés ici

C'est la partie de ce plan que les plans 03-12 et 03-13 liront le plus.

| Situation | Statut | Pourquoi ce choix |
|---|---|---|
| identifiant inconnu / mot de passe faux / **compte désactivé** | **400** | un corps unique, indiscernable ; **pas 401**, parce que `03-UI-SPEC.md` 8.6 branche sur 401 une redirection globale vers `/connexion`, qui se déclencherait alors depuis l'écran de connexion lui-même |
| session expirée, absente, ou compte désactivé en cours de session | **401** | ce que l'interface attend pour vider le contexte et rerouter |
| jeton CSRF manquant, droit manquant | **403** | « authentifié, mais non » |
| limite de débit atteinte | **429** | copie française plus `reessayer_dans` en secondes, plus `Retry-After` |
| affaire authentifiable mais non joignable | **503** | sans cause : le statut commercial d'un client ne transite pas par un corps de réponse |

**Le 401 a demandé une correction.** `APIView.handle_exception` rétrograde
`NotAuthenticated` en **403** dès que la classe d'authentification ne fournit pas
d'en-tête `WWW-Authenticate` — et `SessionAuthentication` n'en fournit pas. Sans
correction, une session morte et un droit manquant répondent tous deux 403, alors que la
spécification leur demande deux comportements opposés. La correction vit dans
`gestionnaire_dexceptions` plutôt que dans une sous-classe d'authentification,
délibérément : `DEFAULT_AUTHENTICATION_CLASSES` reste la classe DRF de série, donc la
phase 11 y ajoute la sienne sans hériter de la nôtre — ce qui est exactement l'argument
« additif » sur lequel repose la décision session-contre-jeton.

## Trois trous trouvés en écrivant, et fermés

### 1. `NUM_PROXIES` — la limitation de débit se contournait avec un en-tête

`SimpleRateThrottle.get_ident` lit `HTTP_X_FORWARDED_FOR` **quand `NUM_PROXIES` vaut
`None`**, qui est le défaut de DRF (vérifié dans le 3.18.1 installé). Un attaquant qui
change l'en-tête à chaque requête obtient une clé de cache neuve à chaque tentative : la
limitation ne limite rien, tout en restant parfaitement verte dans le test qui envoie onze
tentatives sans l'en-tête. C'est T-03-47 rouvert par un défaut de bibliothèque.

`NUM_PROXIES = 0` fait retomber la clé sur `REMOTE_ADDR`. Zéro plutôt qu'un nombre
plausible parce que la juridiction d'hébergement est une décision de phase 1 encore
ouverte : derrière un reverse proxy, zéro rend la limite **globale** plutôt que
contournable, et trop strict est le bon côté pour se tromper. Deux tests le tiennent — le
réglage, et onze `X-Forwarded-For` différents qui atteignent quand même le plafond.

### 2. `AUTH_PASSWORD_VALIDATORS` était absent, donc `validate_password` aurait été un no-op

Un projet Django écrit à la main n'a pas de validateurs par défaut. Appeler
`validate_password` sans en déclarer valide `1234` en silence : le point de terminaison
aurait eu l'air protégé sans l'être, ce qui est pire que de ne rien valider. Quatre
validateurs posés, minimum à dix caractères plutôt que huit — une seule adresse de
connexion sert toute la flotte, donc le coût d'un mot de passe faible est porté par une
surface de bourrage partagée.

### 3. `csrf_protect` manquait sur la connexion

Les vues DRF sont `csrf_exempt` au niveau du middleware, et `SessionAuthentication`
n'impose le CSRF qu'aux utilisateurs **déjà** authentifiés. La connexion aurait donc été
la seule écriture non protégée du produit. Le login CSRF est une vraie attaque : on force
une victime dans la session de l'attaquant, qui relit ensuite ce qu'elle y a saisi. La SPA
appelle déjà `/api/auth/csrf/` au montage (`03-UI-SPEC.md` 6), donc cela ne lui coûte rien.

## Ce que `CHAMPS_PUBLICS` achète, et pourquoi les sérialiseurs sont des `ModelSerializer`

Les trois sérialiseurs de l'amorçage héritent de `SerializerProjete` et leurs dix champs
sont inscrits dans `CHAMPS_PUBLICS`. Écrire des `serializers.Serializer` à la main aurait
été plus court et aurait évité de toucher au registre du plan 03-06. Le choix inverse a
été fait pour une raison précise :

`test_perm06_tout_champ_de_modele_expose_est_classe` exige que tout champ exposé par un
`ModelSerializer` ait été **classé**. `control_plane.Client` porte `db_name`, `db_host`,
`db_user` et `db_password_encrypted`. Le jour où quelqu'un ajoute l'un d'eux à la charge
utile d'amorçage — celle que chaque opticien reçoit à chaque connexion — la suite rougit
en le nommant. Un `Serializer` écrit à la main n'aurait eu aucun garde. « Public » devient
ici une décision écrite, et son absence un refus.

C'est aussi le premier remplissage réel de `CHAMPS_PUBLICS`, que 03-06 avait laissé vide
en annonçant que les phases suivantes le rempliraient « dans le même commit que leurs
sérialiseurs ». La règle a été suivie.

## La fixture `affaire_reelle`, et son coût assumé

Le test porteur du plan — *la connexion lie bien le client et la requête suivante lit sa
base* — exige une requête HTTP complète traversant `TenantMiddleware`. Or le middleware ne
connaît pas les alias statiques `tenant_a` / `tenant_b` : il enregistre `tenant_<pk>`
depuis la ligne `Client`, donc **une autre connexion**.

La fixture fait pointer la ligne `Client` sur la base de test de `tenant_a` — même base,
connexion distincte. La conséquence est la contrainte à connaître avant de la réutiliser :
une connexion distincte ne voit pas la transaction de l'autre, donc les magasins sont
créés **à travers l'alias runtime** et **committés**, puis supprimés dans un `finally`.

C'est le seul endroit de la suite qui écrive hors de la transaction de test, et c'est
assumé plutôt que caché : sans cela, le test de bout en bout de PERM-01 n'existe pas et
l'exigence n'est vérifiée que par morceaux. Les codes de magasin sont préfixés `AUTH` pour
qu'ils ne puissent jamais entrer en collision avec les `ANFA` / `MAARIF` non committés de
`deux_magasins` — deux transactions insérant le même code unique se **bloqueraient**, et
un test qui pend est pire qu'un test qui échoue.

## Rouge → vert

| Test | Rouge, pour quelle raison | Vert |
|---|---|---|
| `..._le_cookie_de_session_survit_a_la_fermeture_du_navigateur` | `SESSION_COOKIE_AGE` aux 14 jours par défaut | après le bloc sessions |
| `..._les_reglages_drf_pinnent_session_permission_et_renderer` | `DEFAULT_AUTHENTICATION_CLASSES` vide | après le bloc `REST_FRAMEWORK` |
| `..._la_limitation_ne_fait_pas_confiance_a_un_en_tete_du_client` | `NUM_PROXIES` valait `None` | après `NUM_PROXIES = 0` |
| `..._le_montant_traverse_le_json_en_chaine_est_epingle` | le nom absent de `base.py` | après l'épinglage |
| `..._clearsessions_est_planifie_et_purge_reellement` | `CELERY_BEAT_SCHEDULE` inexistant | après la tâche et l'entrée Beat |
| `..._la_connexion_etablit_une_session_et_lie_le_client` | 404 sur `/api/auth/connexion/` | après les vues et les routes |
| `..._la_reponse_de_connexion_pose_un_cookie_de_trente_jours` | 404 | idem |
| `..._lechec_de_connexion_ne_distingue_jamais_les_motifs` | 404 | idem |
| `..._la_deconnexion_invalide_la_session_immediatement` | 404 | idem |
| `..._une_requete_api_sans_jeton_csrf_est_refusee` | 404 | idem |
| `..._moi_ne_rend_que_les_magasins_accordes_et_le_catalogue` | 404 | idem |
| `..._le_changement_de_mot_de_passe_efface_le_drapeau` | 404 | idem |
| `..._un_mot_de_passe_trivial_est_refuse_en_francais` | 404, puis `1234` accepté | après `AUTH_PASSWORD_VALIDATORS` |
| `..._la_connexion_est_limitee_en_debit` | `pytest.fail` | après la portée sur la vue |
| `..._le_429_porte_la_copie_francaise_et_un_delai_exploitable` | (neuf) | après `TropDeTentatives` |
| `..._un_en_tete_x_forwarded_for_ne_contourne_pas_la_limitation` | (neuf) | après `NUM_PROXIES = 0` |
| `..._aucun_corps_derreur_ne_renvoie_lidentifiant_soumis` | (neuf) | après le gestionnaire d'exceptions |
| `test_perm02_un_compte_desactive_est_refuse_des_la_requete_suivante` | `pytest.fail` (`tests/test_comptes_droits.py`) | après les vues |

## Critères d'acceptation, tels qu'exécutés

### Tâche 1

| Critère | Résultat |
|---|---|
| `grep -c 'SESSION_EXPIRE_AT_BROWSER_CLOSE = False'` → 1 | **1** |
| `grep -c 'SESSION_COOKIE_AGE'` → 1 | **1** |
| `grep -c 'SESSION_SAVE_EVERY_REQUEST = False'` → 1 | **1** |
| `grep -c 'COERCE_DECIMAL_TO_STRING'` → 1 | **1** |
| `BrowsableAPIRenderer` : 0 dans `base.py`, 1 dans `local.py` | **0 / 1** |
| `grep -c 'LocaleMiddleware\|USE_L10N'` → 0 | **0** |
| `grep -ci 'ATOMIC_REQUESTS' config/settings/*.py` → 0 | **0** sur les quatre modules |
| `grep -c 'clearsessions' tasks.py` ≥ 1 | **2** |
| `pytest -k "navigateur or renderer or decimal or clearsessions"` | **4 passed** |

### Tâche 2

| Critère | Résultat |
|---|---|
| `grep -c 'ensure_csrf_cookie' views.py` → 1 | **2** — insatisfaisable telle qu'écrite. Voir déviation 1 |
| `grep -cE 'connexion\|deconnexion\|mot-de-passe\|moi' urls.py` ≥ 4 | **5** |
| `Identifiant ou mot de passe incorrect.` exactement une fois | **1**, `views.py` |
| `grep -ci 'PasswordReset' plateforme/comptes/` → 0 | **0**. Voir déviation 2 |
| `grep -c 'magasins_ids' views.py` ≥ 1 | **3** |
| `pytest -k "session_et_lie or deconnexion or csrf or identique"` | **passed** |
| `pytest tests/test_comptes_droits.py -k desactive` | **1 passed** |

### Tâche 3

| Critère | Résultat |
|---|---|
| `grep -c 'throttle_scope' views.py` ≥ 1 | **1** |
| `grep -c '"connexion": "10/min"' base.py` → 1 | **1** |
| `Trop de tentatives` exactement une fois | **1**, `views.py` |
| `pytest -k "debit or 429"` | **passed** |
| `grep -c 'pytest.mark.pending' tests/test_comptes_auth.py` → 0 | **0** |

### Vérification du plan

| Critère | Résultat |
|---|---|
| `pytest tests/test_comptes_auth.py -q` | **19 passed** |
| `pytest tests/test_comptes_droits.py -k desactive` | **1 passed** |
| `manage.py check` | **no issues (0 silenced)** |
| `manage.py spectacular --fail-on-warn` | **exit 0** — après la déviation 3 |
| `pytest -x -q -m "not slow and not pending"` | **148 passed, 39 deselected** |
| `pytest -q -m slow` | **30 passed** |
| `grep -rn 'simplejwt\|SIMPLE_JWT' config/ plateforme/` | **aucun résultat** |

## Commits de tâches

1. **Tâche 1 : politique de session, pile DRF, purge des sessions** — `5335a1e` (feat)
2. **Tâche 2 : les cinq points de terminaison** — `46cd41c` (feat)
3. **Tâche 3 : la limitation de débit** — `ca60268` (test)

Chaque commit nomme explicitement ses chemins (`git commit -F - -- <chemins>`), la forme
sûre en worktree partagé.

## Déviations du plan

### 1. [signalé] `grep -c 'ensure_csrf_cookie' views.py` → 1 est insatisfaisable

Le compteur retourne **2**, et c'est son minimum atteignable : l'import
(`from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie`) et le
décorateur (`@method_decorator(ensure_csrf_cookie, name="dispatch")`). L'intention — « il
y a exactement un point de terminaison qui pose le cookie » — est vérifiée exactement, par
lecture et par le test CSRF qui exige que `GET /api/auth/csrf/` pose le cookie. C'est le
même mode de défaillance de critère que la déviation 1 du plan 03-05 : un critère formulé
sur des occurrences textuelles plutôt que sur des sites d'usage.

### 2. [Rule 3 — bloquant] Le nom `PasswordResetView` retiré du texte pour satisfaire son propre critère

Le plan demande à la fois de **dire** qu'il n'y a pas de réinitialisation par courriel et
de vérifier `grep -ci 'PasswordReset' → 0`. La docstring nommait la classe ; elle dit
désormais « la vue de réinitialisation par courriel de `django.contrib.auth` », et
explique en une ligne pourquoi le nom n'y figure pas. L'explication reste, le critère
passe. Préféré à une déviation signalée parce que l'intention du critère — aucun chemin de
réinitialisation par courriel câblé en douce — reste mécaniquement vérifiable pour le
prochain lecteur.

### 3. [Rule 2 — fonctionnalité critique manquante] `extend_schema` sur les cinq vues

`manage.py spectacular --fail-on-warn` échouait : *« unable to guess serializer. Ignoring
view for now »* sur les cinq. `AutoSchema` ne devine rien d'une `APIView` nue et
**l'ignore entièrement** — les cinq routes d'authentification auraient été absentes du
schéma dont le client TypeScript est généré. C'est la pire forme d'absence : silencieuse,
invisible en revue, et découverte par la SPA du plan 03-12. Ajouté : un
`AmorcageSerializer` déclaratif plus `@extend_schema` sur chaque méthode. Vérifié par
`spectacular --fail-on-warn` à zéro.

**Règle pour les phases suivantes :** toute nouvelle `APIView` porte son `extend_schema`
dans le plan qui la crée. Un `ModelViewSet` n'en a pas besoin, une `APIView` si.

### 4. [Rule 2 — fonctionnalité critique manquante] Trois trous de sécurité fermés

`NUM_PROXIES = 0`, `AUTH_PASSWORD_VALIDATORS`, `csrf_protect` sur la connexion. Chacun est
décrit plus haut avec son raisonnement. Les trois servent des menaces déjà au registre du
plan (T-03-47, T-03-49) ou la correction d'un point de terminaison que le plan demande
(le changement de mot de passe).

### 5. [Rule 2] Le gestionnaire d'exceptions, et le 503 sur `NoTenantBound`

Le plan demande que « `NoTenantBound` et un échec de résolution d'`Acces` n'atteignent
jamais un corps de réponse tel quel ». Sans traitement, `NoTenantBound` remonte en **500**,
avec sa trace en développement. Le cas est réel et non théorique : un compte rattaché à
une affaire non `ACTIVE` — en cours de provisionnement, ou suspendue en phase 12 — passe
l'authentification et ne peut pas lire sa base.

Traité dans le gestionnaire d'exceptions plutôt que dans les vues, donc **général** : tout
point de terminaison des phases 5 à 10 en hérite. Le même gestionnaire porte la correction
du 401.

### 6. [Rule 3 — bloquant] Trois fichiers de test hors de `files_modified`

- **`conftest.py`** : la fixture `affaire_reelle` est utilisée par deux modules de tests
  (`test_comptes_auth.py` et `test_comptes_droits.py`), donc sa place est la racine. Elle y
  rejoint `deux_magasins` et `tenant_a`, de même nature.
- **`conftest.py` (bis) et `config/settings/test.py`** : le compteur de limitation fuyait
  d'un fichier de tests à l'autre — `test_comptes_droits.py` a reçu un **429** en essayant
  de se connecter, après les onze tentatives de `test_comptes_auth.py`. Observé, pas
  supposé. Corrigé par un `CACHES` LocMemCache explicite dans les réglages de test et une
  fixture `cache_vide` **autouse**. Le plan demandait « un cache de test isolé » sans dire
  où ; autouse plutôt que sur demande, parce qu'un test qui oublie de demander l'isolation
  ne le découvre pas — il le fait découvrir au test d'après, et l'ordre de collecte décide
  lequel.
- **`tests/test_comptes_droits.py`** : le stub
  `test_perm02_un_compte_desactive_est_refuse_des_la_requete_suivante` s'annonçait « plan
  03-09 », mais les critères d'acceptation de **ce** plan exigent qu'il passe, et il lui
  faut une session ouverte par le vrai point de terminaison de connexion, qui naît ici.
  Dépiné et implémenté. Même forme que la déviation 5 du plan 03-05.

### 7. [Rule 3 — bloquant] `CHAMPS_PUBLICS` rempli dans `plateforme/projection/registre.py`

Non listé dans `files_modified`. Conséquence directe du choix `ModelSerializer` :
`test_perm06_tout_champ_de_modele_expose_est_classe` rougit sur tout champ non classé. La
docstring du registre prévoit exactement ce geste — « les phases 4 à 10 la remplissent au
fur et à mesure, dans le même commit que leurs sérialiseurs ». Le bénéfice est décrit plus
haut : il rend rouge l'ajout d'un identifiant de base de données à la charge utile
d'amorçage.

### 8. [signalé] Le test du cookie a été écrit en deux moitiés

Le plan place dans la tâche 1 un test qui doit constater que « le cookie porte un
`Max-Age` » — or aucun point de terminaison n'existe encore à la tâche 1, et
`Client.force_login` pose délibérément `max-age: None`. La tâche 1 assert donc les
réglages, et la tâche 2 ajoute
`test_perm01_la_reponse_de_connexion_pose_un_cookie_de_trente_jours`, qui lit l'en-tête
réellement émis. Les deux sont nécessaires et le disent dans leurs docstrings :
`SESSION_EXPIRE_AT_BROWSER_CLOSE = True` produit un cookie **sans** `Max-Age` alors que
`SESSION_COOKIE_AGE` reste à trente jours, donc un test qui ne lit que les réglages
resterait vert.

### 9. [signalé] `test_perm06_le_renderer_html_est_absent_hors_developpement` existait déjà

Le plan l'inscrit au comportement de la tâche 1 ; il a été livré par le plan 03-06 et
passe. Non dupliqué. Le test de la tâche 1 qui porte le mot-clé `renderer` vérifie le bloc
`REST_FRAMEWORK` dans son ensemble — authentification, permission, renderer, limitation —
c'est-à-dire ce que **ce** plan y ajoute.

### 10. [signalé] `config/settings/local.py` n'a pas été modifié

`files_modified` le liste et la tâche 1 demande d'y ajouter `BrowsableAPIRenderer` — c'est
déjà fait, par le plan 03-06, avec le commentaire d'A-03-06 et le `dict` neuf plutôt qu'un
`.append()`. Rien à faire ; le critère d'acceptation passe.

---

**Total des déviations :** 10, dont **4 corrections automatiques** (Rule 2 : schéma
OpenAPI, trois trous de sécurité, gestionnaire d'exceptions) et **3 déblocages** (Rule 3 :
fichiers de test, registre, nom retiré d'une docstring). Trois sont des signalements sans
changement de code.

**Impact :** aucune dérive de périmètre. Les ajouts Rule 2 servent tous une menace déjà au
registre du plan ou un contrat déjà écrit dans `03-UI-SPEC.md`.

## Ce qu'il faut signaler au-delà du code

### Le fournisseur d'e-mail transactionnel est un élément d'approvisionnement des phases 1 et 12

La pile n'en nomme aucun, donc la réinitialisation de mot de passe par courriel n'existe
pas et ne peut pas exister. Le chemin livré est sans courriel :

- le **propriétaire** pose et réinitialise le mot de passe d'un gérant (plan 03-09) ;
- `doit_changer_mot_de_passe` force le changement à la première connexion, et la SPA
  atterrit sur `/mot-de-passe` (plan 03-12) ;
- un **propriétaire** qui oublie le sien est réinitialisé par l'opérateur via l'admin.

C'est défendable pour des boutiques de cette taille et cela retire une dépendance
d'approvisionnement du chemin critique. L'écran de connexion porte en conséquence une
ligne d'aide et **aucun lien mort**. **La phase 12 en aura besoin de toute façon** :
l'inscription en libre service ne peut pas vérifier une adresse sans envoyer un message.
Si un fournisseur est procuré, la ligne d'aide devient un lien et rien d'autre ne change.

### `django-axes` : ce qu'il aurait coûté, ce qu'il aurait apporté

**Non adopté en phase 3**, et consigné ici pour que la décision reste disponible plutôt
qu'oubliée.

**Ce qu'il apporte :** le verrouillage par **nom d'utilisateur** — que la limitation par IP
ne couvre pas, puisqu'un attaquant distribué essaie un mot de passe depuis mille adresses
contre un seul compte — et une piste d'audit des tentatives, que nous n'avons pas du tout.

**Ce qu'il coûte :** ses classifiers s'arrêtent à Django 6.0, donc la compatibilité avec le
6.1.1 épinglé doit être **prouvée** et non supposée (le même travail que
`django-celery-beat` a demandé au plan 02-01, avec son `override-dependencies`) ; il porte
des modèles, donc il faut l'ajouter à `CONTROL_PLANE_APPS` **dans le même commit** que
`INSTALLED_APPS`, sans quoi `tenancy.E001` fait échouer `manage.py check` ; et ses tables
de tentatives vivent sur la base partagée du plan de contrôle, ce qui ajoute une seconde
table chaude à côté de `django_session`, avec la même question de purge.

**Ce qui est en place à la place :** `10/min` par IP réelle, Argon2 qui rend chaque essai
coûteux, `login()` qui traite la fixation, et un message d'échec unique qui refuse de dire
si le compte existe. Cela couvre le bourrage large ; cela ne couvre pas le bourrage
distribué contre un compte nommé. La menace est au registre comme **acceptée** (T-03-56).

### La phase 11 n'est pas bloquée, et voici exactement pourquoi

`DEFAULT_AUTHENTICATION_CLASSES` est une **liste**. Ajouter une classe de jeton en phase 11
ne touche ni vue, ni sérialiseur, ni permission, ni projection. La seule chose qu'il
fallait préserver aujourd'hui est que la liaison de locataire ne soit pas soudée au
middleware — et elle ne l'est pas : `resolve_client(request)` est une fonction autonome au
contrat « identité vérifiée par le serveur en entrée, `Client` en sortie », et c'est elle
que la vue de connexion appelle, exactement comme le middleware.

Une précision utile à la phase 11 : `gestionnaire_dexceptions` force le 401 parce que
`SessionAuthentication` ne fournit pas de `WWW-Authenticate`. Une classe de jeton qui en
fournit un rendra cette branche inopérante pour ses requêtes — ce qui est le comportement
correct, et non une régression.

## Notes pour les plans suivants

- **03-09** est le **second** usage sanctionné de `peut_quelque_part`, étiquette
  `catalogue`. Le premier est pris : `plateforme/comptes/serializers.py`, dans
  `charge_utile_moi`, étiquette `navigation`. Le garde source accepte encore exactement
  une étiquette.
- **03-09** sert le catalogue *pré-intersecté* (ce qu'un gérant-gestionnaire peut
  **accorder**). Le catalogue **complet** est déjà servi par `/api/auth/moi/` via
  `catalogue_des_droits()` — ce sont deux questions différentes, et la première n'a pas à
  réimplémenter la seconde. `AUTH_PASSWORD_VALIDATORS` est posé, donc le mot de passe
  initial d'un gérant doit passer par `validate_password` comme le fait
  `ChangementMotDePasseSerializer`.
- **03-10** commite le schéma : les cinq routes y entrent avec le composant `Amorcage`.
  `spectacular --fail-on-warn` est à zéro aujourd'hui, donc un avertissement qui
  apparaîtrait vient d'un ajout ultérieur.
- **03-12 / 03-13** : le tableau des codes de statut ci-dessus est le contrat. En
  particulier — **400 pour un échec de connexion, 401 pour une session morte** — et le
  `reessayer_dans` du 429 est un entier de secondes prêt pour le compte à rebours.
- **Phases 5 à 10** : toute nouvelle `APIView` porte un `extend_schema` dans son propre
  plan ; tout champ de modèle exposé rejoint `CHAMPS_PROTEGES` ou `CHAMPS_PUBLICS` dans le
  même commit.

## Known Stubs

Aucun. Les cinq points de terminaison sont complets, testés et servis ; rien ne rend une
valeur vide ni un texte d'attente vers une interface.

Deux **absences délibérées**, documentées plutôt que masquées, et ni l'une ni l'autre n'est
un stub :

1. **Pas de réinitialisation par courriel** — il n'existe aucun fournisseur d'e-mail dans
   la pile. Le chemin sans courriel est livré en entier et l'écran de connexion ne porte
   aucun lien mort.
2. **Pas de verrouillage par nom d'utilisateur** — `django-axes` non adopté, coût et
   bénéfice consignés ci-dessus, menace acceptée au registre (T-03-56).

## Self-Check: PASSED

Les trois fichiers créés sont présents sur le disque (`plateforme/comptes/views.py`,
`serializers.py`, `urls.py`), les huit fichiers modifiés portent bien leurs changements, et
les trois commits existent dans `git log` : `5335a1e`, `46cd41c`, `ca60268`. Suite
re-passée après le dernier commit : **148 passed, 39 deselected** en rapide, **30 passed**
en `slow`, `manage.py check` sans problème et `spectacular --fail-on-warn` à zéro.

---
*Phase : 03-comptes-permissions-app-shell*
*Terminé : 2026-09-16*
