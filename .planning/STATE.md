---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: "Completed 03-14-PLAN.md (comptes et droits). La phase 3 est complete cote CODE : 14 plans, 14 summaries. Le point de controle a releve un BLOCAGE — l'ecran etait inatteignable par l'interface, corrige — et rendu trois decisions, toutes appliquees. AUCUNE des huit etapes de verification humaine n'est approuvee : l'etape 1 est re-activee mais non rejouee. Suivant : la verification de phase 3, dont la passe manuelle au navigateur (24 verifications accumulees depuis 03-12)"
last_updated: "2026-09-17T15:40:00.000Z"
last_activity: 2026-09-17
progress:
  total_phases: 12
  completed_phases: 2
  total_plans: 21
  completed_plans: 21
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-09)

**Core value:** The counter completes a sale end to end — client, ordonnance, payment including acompte, landing in that magasin's caisse — producing a facture legally valid in Morocco every time.
**Current focus:** Phase 3 — Comptes, Permissions & App Shell (Phase 1 continues in parallel as a calendar track)

## Current Position

Phase: 3 of 12 (Comptes, Permissions & App Shell)
Plan: **14 of 14 complete in current phase (03-01 à 03-14) — la phase 3 est complète côté CODE, pas côté vérification.** L'écran `Comptes et droits` existe : les 21 droits en sept sections venus du catalogue serveur (la SPA ne code aucun libellé), la surcharge par magasin qui n'apparaît qu'à la demande avec son tri-état `aria-checked="mixed"`, aucun preset ni palier nulle part, les deux dialogues destructifs qui énoncent **ce qui survit**, et l'historique de `JournalDroit`. Une entreprise mono-magasin ne rencontre aucun contrôle.

**Le point de contrôle a relevé un blocage, pas un écart de copie : l'écran entier était inatteignable par l'interface.** `Paramètres` menait au titre d'attente et rien dans le produit ne liait vers `/parametres/comptes` — 32 tests frontend étaient verts parce qu'ils montaient tous l'écran à sa propre route. La navigation de second niveau de `03-UI-SPEC.md` 5.3 est construite, l'accueil des paramètres redirige vers sa première entrée visible, et un test part de la racine et **clique**. Trois décisions du propriétaire appliquées : l'intersection de la réponse d'une bascule (qui amende le contrat du plan 03-09), l'abandon de la mise en évidence de 2 secondes, et une seconde affaire mono-magasin en développement.

Suites : backend **184 passed / 30 deselected**, web **119 passed**, build 0, `spectacular --fail-on-warn` 0 avec diff de schéma vide, `migrate_all --check` 2 ok / 0 behind.

Suivant : la **vérification de phase 3**, dont la passe manuelle au navigateur — 24 vérifications accumulées et aucune effectuée.
Status: Executing
Last activity: 2026-09-17

Progress: [██████████] 100% (14/14 plans de la phase 3 écrits ; la vérification de phase reste à faire)

## Performance Metrics

**Velocity:**

- Total plans completed: 1
- Average duration: ~1 session
- Total execution time: ~1 session

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 2 | 1 of 7 | 1 session | 1 session |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 2 P02 | 1 session | 3 tasks | 17 files |
| Phase 2 P03 | 1 session | 3 tasks | 18 files |
| Phase 03 P01 | ~50m | 3 tasks | 17 files |
| Phase 03 P02 | ~35m | 3 tasks | 8 files |
| Phase 03 P03 | ~45m | 4 tasks | 20 files |
| Phase 03 P11 | 20m | 3 tasks | 11 files |
| Phase 03 P04 | ~45m | 2 tasks | 6 files |
| Phase 03 P05 | 50m | 2 tasks | 5 files |
| Phase 03 P06 | ~70m | 3 tasks | 10 files |
| Phase 03 P07 | ~75m | 3 tasks | 6 files |
| Phase 03 P08 | ~75m | 3 tasks | 11 files |
| Phase 03 P09 | ~85m | 3 tasks | 8 files |
| Phase 03 P10 | ~30m | 3 tasks | 8 files |
| Phase 03 P12 | ~45m | 4 tasks | 18 files |
| Phase 03 P13 | ~55m | 4 tasks | 24 files |
| Phase 03 P14 | ~100m | 4 tasks | 25 files |

## Quick Tasks Completed

| ID | Titre | Date | Commits | Resultat |
|----|-------|------|---------|----------|
| 260917-04r | Corriger l'echec CSRF d'origine qui bloquait la connexion au navigateur | 2026-09-17 | `fe138d5` (test), `30b853c` (fix) | Le proxy Vite preserve `Host` (`changeOrigin: false`), `CSRF_TRUSTED_ORIGINS` en filet dans `local.py` seul, et le premier test de la suite qui envoie un en-tete `Origin`. Backend 180 passed / 30 deselected (baseline 179), frontend 50 passed, build a 0. Point de controle approuve sur **reproduction machine** (200 avec l'origine du navigateur, 403 avec une origine tierce) ; la connexion dans un vrai navigateur **n'a pas ete effectuee par un humain**. Detail : `.planning/quick/260917-04r-corriger-l-echec-csrf-d-origine-qui-bloq/260917-04r-SUMMARY.md` |
| 260917-l7l | Rendre l'octroi par magasin visible, et confirmer la reinitialisation | 2026-09-17 | `d94f9d1` (defaut 1), `e224987` (defaut 2) | Deux defauts trouves par le proprietaire dans un navigateur pendant que 303 tests etaient verts. `Par magasin` perd sa revelation au survol (`opacity-0` + `group-hover:`) et devient permanent, subordonne par `text-xs text-muted-foreground` ; CLAUDE.md #13 intact — defaut uniforme, aucune ligne depliee, stockage non touche. `Reinitialiser le mot de passe` passe derriere `DialogueReinitialisation` (`Retour` / `Réinitialiser`), plus aucun appel avant confirmation. Trois tests nommes, tous rouges d'abord. Backend 184 passed / 30 deselected (inchange), web 122 passed (baseline 119), build a 0, `audit:format` muet. **Verification humaine au navigateur non effectuee** — elle rejoint la passe unique de la porte de phase 3. Detail : `.planning/quick/260917-l7l-rendre-l-octroi-par-magasin-visible-et-c/260917-l7l-SUMMARY.md` |
| 260917-lhq | Une requete avortee n'est pas une coupure de lien | 2026-09-17 | `60a71ef` (test), `7fda076` (fix) | Cinquieme defaut trouve par le proprietaire dans un navigateur, suite verte. La banniere `Connexion perdue.` clignotait a **chaque** rechargement et **chaque** changement de route : `onError` comptait un abandon comme une coupure, alors que react-query annule sa requete des que le dernier observateur se desabonne. Pas cosmetique — 8.6 desactive tout controle d'ecriture tant que la banniere est levee, donc le produit se croyait brievement hors ligne a chaque navigation. `estUneRequeteAvortee()` consulte `request.signal.aborted` (le fait) avant le `name` de l'exception (le symptome) ; un `TypeError: Failed to fetch` leve toujours la banniere des le premier echec. **Aucun seuil ajoute** : `retry: false` fait qu'un second echec ne partirait jamais, donc un seuil rendrait la banniere muette pendant une vraie coupure. Quatre tests `test_app01_*`, les deux exiges observes rouges d'abord. Web 126 passed (baseline 122), backend 184 passed / 30 deselected (inchange), build a 0, schema non regenere. **Verification humaine non effectuee** — elle rejoint la passe de la porte de phase 3 (25 verifications accumulees). Le SUMMARY tranche la question « quel test aurait attrape celui-ci » : un double de `fetch` differe (~20 lignes, a construire au prochain formulaire) et un parcours de fumee Playwright etroit en debut de phase 4 ; 3 des 5 defauts de la phase sont mecaniquement attrapables, 2 sont des jugements humains qui ne le seront jamais. Detail : `.planning/quick/260917-lhq-une-requete-avortee-n-est-pas-une-coupur/260917-lhq-SUMMARY.md` |

## Accumulated Context

### Roadmap Evolution

- Phase 03.1 inserted after Phase 3: Assignation des droits par magasin (URGENT) — raised by the owner on 2026-09-17 while walking the `Comptes et droits` screen in a browser

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Online only, permanently — no offline phase exists; sale creation is idempotent and the facture number is server-issued from a locked counter row, never a database sequence
- [Roadmap]: One database per client business; magasins live inside it — Phase 2 is unretrofittable and comes first in build order
- [Roadmap]: Permissions (Phase 3) precede the feature surface so the single projection layer exists before modules invent their own filtering
- [Roadmap]: Manual onboarding (TENANT-06) lands in Phase 2, so a real optician uses the product long before self-serve billing in Phase 12
- [02-01]: Infrastructure package is `plateforme/`, never `platform/` — a top-level `platform/` shadows the stdlib module that psycopg, gunicorn and Sentry import. Every `platform.*` dotted path in 02-RESEARCH.md becomes `plateforme.*`
- [02-01]: Django pinned 6.1.1 (inside the mandated >=6.1,<6.2) — the tenancy design rests on Django internals source-verified against 6.1.x
- [02-01]: `django-celery-beat` 2.9.0's stale `Django<6.1` cap lifted by a documented `[tool.uv] override-dependencies`, verified working rather than assumed; remove when a release lifts it upstream
- [02-01]: Client databases use the PostgreSQL 18 ICU locale provider (`LOCALE_PROVIDER icu ICU_LOCALE 'fr-FR'` with `TEMPLATE template0`), not an OS locale — the stock postgres image generates only `en_US.utf8`
- [02-01]: Compose host ports 5435 / 6433 / 6380 / 8010, all bound to 127.0.0.1 (8000, 5432-5434 and 6379 are occupied on the dev machine)
- [Roadmap]: Phase 1 is a parallel calendar track — only LEGAL-02 (hosting jurisdiction) gates build work
- [Phase 02-02]: CheckConstraint takes condition= on Django 6.1.1; check= is removed, not merely deprecated (research assumption A6 resolved)
- [Phase 02-02]: Client.connection_params(direct=False) uses the row's db_host/db_port (PgBouncer); direct=True swaps in PG_ADMIN_* for DDL, migrations and pg_dump
- [Phase 02-02]: The session-start stale-database reaper is skipped inside pytest-xdist workers, so one worker cannot drop another's test databases
- [Phase 02-03]: clear() is set(_UNSET); the token-based ContextVar undo appears nowhere under plateforme/tenancy. tenant_context restores on exit, request/task teardown clears — never unified
- [Phase 02-03]: CONTROL_PLANE_APPS must include rest_framework and tenancy — the tenancy.E001 check exempts only django.* names. A later phase adds its app label to BUSINESS_APPS in the same commit as INSTALLED_APPS
- [Phase 02-03]: resolve_client reads the authenticated principal only, never a header or subdomain; Phase 3 swaps the lookup for a signed JWT client_id claim without changing the contract
- [Phase 02-03]: TENANT-08 measured, not assumed: 300 registered aliases at concurrency 4 gave a peak of 4 server connections and settled to 0; CONN_MAX_AGE=600 exhausts PostgreSQL's connection slots
- [Phase 02-03]: The tenancy django_db marker is applied in pytest_collection_modifyitems, not from a fixture body — pytest-django decides which test databases to create before any fixture runs
- [Phase 02-08]: PgBouncer resolves client credentials by auth_query against a SECURITY DEFINER function (docker/postgres/init/01-pgbouncer-auth.sql), never by userlist.txt — a provisioned client needs no pooler edit and no reload. auth_dbname is required, or auth_query runs inside the client's own database where the function does not exist
- [Phase 03]: AUTH_USER_MODEL swapped to comptes.Utilisateur by recreating the development control-plane database; pre-flight found 0 clients, so no data migration was needed
- [Phase 03]: No PermissionsMixin on Utilisateur: Group is a role tier (CLAUDE.md #6), and its absence is the guarantee, asserted by a test
- [Phase 03]: CLAUDE.md #12 fourth instance closed: REVOKE CONNECT on optique_control, applied to the local cluster by hand because Docker only runs initdb.d on an empty volume
- [Phase 03-02]: Grant factories (AccesMagasinFactory, DroitAccordeFactory) land in 03-04 with their models: factory_boy reads Meta.model at class creation, so a factory written before its model breaks collection for the whole suite
- [Phase 03-02]: Test fixtures now give two magasins per tenant, with the SAME codes (ANFA/MAARIF) in both tenants, so a magasin resolved by code outside the tenant connection is visible (03-RESEARCH P16)
- [Phase 03-02]: A parametrization over a not-yet-existing registry needs BOTH a guarded in-function import (or collection breaks suite-wide) and a constant fallback case (or the phase's load-bearing test is parametrized over zero cases, hence green and worthless)
- [Phase 03]: web/ : proxy meme-origine /api et /static vers 127.0.0.1:8010, prouve par requete reelle — aucune dependance CORS de part et d'autre
- [Phase 03]: Preset shadcn epingle : style new-york, baseColor zinc, cssVariables true. components.json ecrit a la main — le CLI 4.21.0 ne produit plus new-york
- [Phase 03]: Le bloc shadcn form est differe a la phase 4 : il tire react-hook-form, zod et @hookform/resolvers, que le plan 03-03 interdit. 21 blocs + sheet = 22 fichiers
- [Phase 03]: Le formateur MAD client est ecrit a la main et arrondit sur les chiffres de la chaine (ROUND_HALF_UP), jamais sur un double : 999.995 doit rendre 1 000,00 MAD. Intl.NumberFormat et toLocaleString sont interdits hors de web/src/format/, verifie par npm run audit:format
- [Phase 03]: Tout tableau passe par web/src/tableau/ : le registre filtre sur champ in ligne, zero ligne rend zero colonne, aucun th litteral, et toute valeur fournie par l'utilisateur est enveloppee dans un bdi par le composant Valeur. Regle a tenir des phases 4 a 10
- [Phase 03-04]: Les droits sont stockes par (utilisateur, magasin_code, code), unique sur les trois colonnes — CLAUDE.md #13 et 03-UI-SPEC 0.1, et NON la forme sans dimension magasin de 03-RESEARCH section 4, que son propre bandeau de correction abandonne
- [Phase 03-04]: magasin_code est le code metier, une valeur, jamais une cle etrangere : allow_relation refuse toute relation inter-alias, et le code survit a un pg_restore la ou un id est reattribue (TENANT-09)
- [Phase 03-04]: La regle « un droit ne vise qu'un magasin accorde » est une regle Python assumee (DroitAccorde.save + service d'octroi 03-09) : une CHECK ne porte pas sur une autre table, et queryset.update la contourne
- [Phase 03]: peut(code) sans magasin est une conjonction sur tous les magasins accordes, jamais une union (fail-closed, 03-05)
- [Phase 03]: l'acces du proprietaire et Acces.SCHEMA sont materialises, donc peut() n'a aucune branche de privilege (03-05)
- [Phase 03]: 03-06: le registre de projection est cle par champ de modele (app.Model.field), jamais par classe de serializer — un champ protege le reste imbrique dans la ressource d'un autre (A-03-08)
- [Phase 03]: 03-06: CHAMPS_PROTEGES reste vide en phase 3 ; la machinerie est prouvee contre une ressource test-only de tests/, injectee au registre par monkeypatch — la phase 8 ecrira la meme ligne a demeure
- [Phase 03]: 03-06: tout nouveau rendu doit rejoindre la liste RENDUS du test de conformite DANS LE PLAN QUI LE CREE — c'est la seule chose qui empeche la derive, et elle n'est pas mecanique
- [Phase 03]: 03-06: l'en-tete CSV est derive de serializer.child.fields ; separateur ';' et BOM UTF-8, revisables et non verifies contre un vrai Excel
- [Phase 03]: 03-06: le schema OpenAPI est epingle sur Acces.SCHEMA par GET_MOCK_REQUEST — sans cela build_mock_request recopie request.user et le document servi varie par utilisateur (plumbing.py:1288)
- [Phase 03]: 03-06: COMPONENT_NO_READ_ONLY_REQUIRED n'est pas seulement laisse a False, son nom est absent de config/settings/ et un test l'exige — le basculer rendrait id optionnel partout
- [Phase 03]: 03-06: DEFAULT_RENDERER_CLASSES est JSON seul en base ; le renderer HTML navigable de DRF n'existe que dans local.py (A-03-06)
- [Phase 03]: 03-06: le setter Request.user de DRF reecrit _request.user, donc request.acces paresseux voit le verdict de DRF — fail-closed en production, mais les tests doivent employer force_authenticate
- [Phase 03]: 03-07: la portee des lignes est dans get_queryset(), jamais dans list() — get_object() y passe, donc filtrer dans list() laisse la route de detail ouverte (IDOR)
- [Phase 03]: 03-07: MagasinScopedViewSet est un MIXIN et non une sous-classe de ModelViewSet (la caisse phase 7 est en ajout seul) ; le prix est le mauvais ordre de bases, qui fait disparaitre la portee sans erreur — le garde verifie donc le MRO
- [Phase 03]: 03-07: on ne caviarde pas un scalaire deja calcule — agreger_dans_la_portee PREND l'acces et restreint elle-meme, pour qu'un appelant qui se trompe obtienne un nombre restreint et non global
- [Phase 03]: 03-07: tout refus d'un parametre de tri ou de filtre produit le meme corps — champ protege, champ public non declare et nom inexistant sont indiscernables, sinon le code de statut est l'oracle
- [Phase 03]: 03-07: django-filter n'est pas ajoute ; une dependance qui entre dans la pile est une decision de PROJECT.md
- [Phase 03]: 03-07: les gardes d'enumeration restent des tests et non des system checks ; la condition de promotion en projection.E001 est ecrite dans la docstring de checks.py
- [Phase 03]: 03-07: regle des phases 5 a 10 — tout modele magasin-scope herite de MagasinScopedViewSet EN PREMIERE BASE, tout agregat passe par le queryset deja restreint, et toute annotate() produisant de la monnaie est une question de registre
- [Phase 03-08]: 03-08: la vue de connexion lie le locataire elle-meme — TenantMiddleware a deja tourne avec un utilisateur anonyme, donc login() puis serialiser leverait NoTenantBound
- [Phase 03-08]: 03-08: contrat de statuts — 400 pour un echec de connexion (jamais 401, que la SPA reserve a la session morte), 401 session morte, 403 CSRF ou droit manquant, 429 limite, 503 affaire injoignable
- [Phase 03-08]: 03-08: NUM_PROXIES = 0 — le defaut None de DRF derive l'identite du client de X-Forwarded-For, donc la limitation de debit se contourne par un en-tete
- [Phase 03-08]: 03-08: DRF rétrograde NotAuthenticated en 403 quand la classe d'auth ne rend pas de WWW-Authenticate ; corrige dans un gestionnaire d'exceptions et non dans une sous-classe, pour que la phase 11 ajoute la sienne sans heriter
- [Phase 03-08]: 03-08: NoTenantBound devient un 503 sans cause, general a toute l'API — un compte rattache a une affaire non ACTIVE passe l'authentification et ne peut pas lire sa base
- [Phase 03-08]: 03-08: les serialiseurs de l'amorcage sont des ModelSerializer et leurs champs entrent dans CHAMPS_PUBLICS — sur control_plane.Client c'est ce qui rend rouge l'ajout de db_name a la charge utile
- [Phase 03-08]: 03-08: toute nouvelle APIView porte un extend_schema dans le plan qui la cree — AutoSchema ignore une APIView nue, donc la route est absente du contrat TypeScript en silence
- [Phase 03-08]: 03-08: pas de reinitialisation par courriel — aucun fournisseur d'e-mail dans la pile ; approvisionnement des phases 1 et 12, dont l'inscription libre service aura besoin
- [Phase 03-08]: 03-08: django-axes non adopte (T-03-56 acceptee) — classifiers arretes a Django 6.0, modeles a classer dans CONTROL_PLANE_APPS, seconde table chaude sur le plan de controle
- [Phase 03-09]: 03-09: la regle d'octroi vit dans plateforme/comptes/services.py, jamais dans la vue — l'onboarding (TENANT-06) et l'inscription libre service de la phase 12 doivent obtenir la meme cascade sans requete HTTP
- [Phase 03-09]: 03-09: PeutGererLesComptes lit acces.peut(compte.gerer) sans branche « or est_proprietaire » — l'acces du proprietaire est materialise depuis 03-05, donc il passe par le meme chemin ; consequence assumee, un proprietaire sans magasin actif est refuse
- [Phase 03-09]: 03-09: le contrat de reponse d'une bascule est lignes / cascade / magasins_accordes / magasins_etendus, avec etat actif|inactif|mixte — le plan 03-14 construit l'ecran contre lui et un test nomme le fixe
- [Phase 03-09]: 03-09: un magasin ajoute etend les lignes UNIFORMES et jamais les personnalisees, calcul fait sur l'etat d'avant l'ajout ; l'inverse distribuerait une permission jamais accordee (T-03-62)
- [Phase 03-09]: 03-09: la cible d'une gestion de compte n'est jamais le proprietaire ni soi-meme (03-UI-SPEC 7.7) — sans cela un gerant-gestionnaire reinitialise le mot de passe du proprietaire et prend son compte
- [Phase 03-09]: 03-09: le dernier magasin d'un compte n'est PAS refuse cote serveur — un compte neuf en a legitimement zero, donc « au moins un » est un garde-fou d'interface, pas un invariant
- [Phase 03-09]: 03-09: le catalogue offrable est intersecte AVANT serialisation et « catalogue » rejoint RENDUS — une ligne de CHAMPS_PROTEGES produit desormais quatre assertions, pas trois
- [Phase 03]: 03-10: les constantes de format sont inscrites dans formats.py et recollees a la fixture par un test — la production ne lit jamais tests/ a l'execution
- [Phase 03]: 03-10: la fixture partagee gagne 0.125 et -0.125 ; sans eux ROUND_HALF_EVEN laissait la suite verte, et le cas 999.995 ne distingue pas les deux modes
- [Phase 03]: 03-10: le fuseau se convertit dans le formateur, TIME_ZONE reste UTC ; le glissement des bornes de journee pendant le Ramadan est accepte et reporte a la phase 10 (T-03-72)
- [Phase 03]: 03-10: pas de middleware de negociation de langue et pas de reglage de localisation retire — les noms vivent dans tests/test_locale.py, jamais dans config/settings/, pour que le grep de presence reste utilisable
- [Phase 03]: 03-10: tout total affiche est un champ du serveur ; la regle est ecrite dans base.py parce qu'aucun lint ne peut la verifier — le bug a attraper est un serialiseur qui omet un total
- [Phase 03]: 03-10: web/src/api/schema.yml est commite et garde par un test plus une porte de CI ; toute modification de vue, de serialiseur ou de route le regenere dans le meme changement
- [Phase 03]: 03-10: /api/schema/ est monte et ferme aux anonymes — SERVE_PERMISSIONS vaut AllowAny par defaut chez drf-spectacular 0.30.0
- [Phase 03]: 03-12: le client d'API ne prend AUCUN prefixe de chemin — les cles du schema portent deja /api/, donc baseUrl vaut l'origine de la page ; "/api" produirait /api/api/... et un 404 sur chaque appel
- [Phase 03]: 03-12: openapi-fetch consomme la reponse — le corps d'erreur (detail, reessayer_dans) se lit sur le champ error rendu, jamais en reclonant response, qui rend un corps vide
- [Phase 03]: 03-12: fetch est resolu a chaque appel (globalThis.fetch(requete)) et non capture a la creation du client — sinon aucune suite ne peut doubler le reseau sans doubler client.ts entier
- [Phase 03]: 03-12: un 401 sur /api/auth/moi/ au premier chargement anonyme est le cas NORMAL — le drapeau sessionOuverte empeche d'afficher « votre session a expire » a quelqu'un qui n'en a jamais ouvert
- [Phase 03]: 03-12: 03-UI-SPEC 9.4 AMENDEE au point de controle — /mot-de-passe porte un quatrieme champ, « Mot de passe actuel », parce que le point de terminaison 03-08 l'exige ; decision tranchee, la phase 9 ne la rouvre pas
- [Phase 03]: 03-12: les cinq etats globaux de 03-UI-SPEC 8.6 vivent dans web/src/etats/ (repertoire non prevu au plan) — neuf phases en heritent, et une copie par page rendrait fausse la regle « la chaine apparait une seule fois » des la phase 4
- [Quick 260917-04r]: **Piege transverse, verifie dans Django 6.1.1 — les origines de confiance du CSRF sont gelees au premier `Origin` du processus.** `csrf_protect` est `decorator_from_middleware(CsrfViewMiddleware)` et `make_middleware_decorator` (`django/utils/decorators.py:126`) instancie le middleware **une seule fois, a l'import du module de vues** ; `allowed_origins_exact` et `csrf_trusted_origins_hosts` sont des `cached_property` (`django/middleware/csrf.py:174-186`) et `django/test/signals.py` ne contient **aucun** recepteur de `setting_changed` qui les invalide. Consequence pour toute phase : **un test qui envoie un en-tete `Origin` ne peut pas supposer que son propre `override_settings` gagne** — s'il tourne apres un autre test porteur d'`Origin`, il voit la liste du premier. Les jambes d'un meme test partagent donc un seul override ; deux valeurs differentes donnent silencieusement le meme resultat aux deux, et le test « passe » sans rien prouver
- [Quick 260917-04r]: le proxy de developpement Vite preserve `Host` (`changeOrigin: false` explicite, la forme chaine le met a `true`) — `CsrfViewMiddleware` reconstruit l'origine attendue depuis `request.get_host()`, donc un `Host` reecrit refuse toute ecriture en 403. **Le reverse proxy de production doit preserver `Host` pour la meme raison**, et `CSRF_TRUSTED_ORIGINS` ne le rattrapera pas la-bas : il vit dans `local.py` seul, jamais dans `base.py`
- [Phase 03]: 03-13: `disponible` reste la porte de la navigation — une construction de production ne livre jamais une entree menant a un emplacement vide ; VITE_NAV_COMPLET reste un outil de revue de densite qui compile a `false` constant en production, jamais un drapeau livre actif
- [Phase 03]: 03-13: `--primary` aligne sur l'accent #2563EB de 03-UI-SPEC section 4, pose APRES le bloc du preset zinc pour que celui-ci reste reinstallable. Le bouton de /connexion change de couleur : consequence assumee. Blanc sur #2563EB mesure 5,17:1, au-dessus du plancher AA de 4,5:1
- [Phase 03]: 03-13: deux fichiers VENDUS par shadcn sont modifies — Ctrl+B retire de `sidebar.tsx` (5.7 interdit tout accord en v1) et MOBILE_BREAKPOINT 768 → 1024 dans `use-mobile.ts` (5.6). Chacun porte la raison en tete ET un test nomme : un `shadcn add` ramenerait les deux defauts sans que rien ne rougisse
- [Phase 03]: 03-13: /mot-de-passe est UNE route et DEUX chemins — le changement force rend deux champs, le volontaire trois, avec sa propre copie et une issue `Retour` (`Annuler` est reserve a l'annulation d'une modification enregistree)
- [Phase 03]: 03-13: le changement FORCE n'exige pas `mot_de_passe_actuel` — derogation conditionnee a `doit_changer_mot_de_passe` COTE SERVEUR, pas cote client. REVIENT sur la decision du point de controle 03-12 et amende les plans 03-08 et 03-12. Le garde-fou est `test_perm01_un_compte_ordinaire_reste_refuse_sans_le_mot_de_passe_actuel`, qui rougit le jour ou la derogation s'elargit
- [Phase 03]: 03-13: le plafond de navigation est de neuf entrees, huit prises et une reservee — un dixieme module entre dans une section existante ou en remplace une. Et toute route declare `portee: magasin|multi` : une route a portee magasin DEMANDE lequel plutot que de deviner
- [Phase 03]: 03-14: la navigation de second niveau de 03-UI-SPEC 5.3 n'avait jamais ete construite — `/parametres/comptes` n'etait atteignable qu'en TAPANT son adresse, et 32 tests frontend etaient verts parce qu'ils montaient tous l'ecran a sa propre route. Le second niveau vit desormais dans `NAV[].sousEntrees`, sous le meme predicat de visibilite que le premier. Regle qui en sort : au moins un test par surface doit y arriver comme une personne y arrive — monter a la racine, cliquer, assertir
- [Phase 03]: 03-14: l'accueil d'une section de parametres REDIRIGE vers sa premiere entree visible ; aucune entree visible rend la 403 pleine page SANS nommer de droit, parce qu'aucun droit unique ne possede `/parametres` et que la phase 9 y ajoutera un ecran sous un autre code
- [Phase 03]: 03-14: la reponse d'une BASCULE est intersectee avec les magasins de l'appelant (`services.intersecter`), etat recalcule sur les ensembles reduits. AMENDE le contrat fige par le plan 03-09 et son test nomme `test_perm03_les_trois_bascules_repondent_le_contrat_de_lecran_de_droits`. La forme et le schema OpenAPI sont inchanges. Regle generale : toute reponse portant un code de magasin ou de droit passe par l'intersection, en ECRITURE comme en lecture
- [Phase 03]: 03-14: la regle d'etat de 7.5 est ecrite UNE fois, dans `services.etat_de`, lue par `ligne_de`, `etat_des_droits` et `intersecter` — trois ecritures divergent, et la divergence serait un interrupteur qui ment sur l'etat reel
- [Phase 03]: 03-14: la mise en evidence de la nouvelle ligne pendant 2 secondes est SUPERSEDEE dans 03-UI-SPEC 7.2 — la navigation vers le detail demonte la liste dans le meme tick, donc elle se jouerait sur un ecran que personne ne regarde. Aucune ligne de code n'a change, elle n'avait jamais ete implementee
- [Phase 03]: 03-14: la base de developpement porte desormais DEUX affaires — `rabat` (Optique Rabat, un seul magasin AGDAL, proprietaire hind@optiquerabat.ma, gerant youssef@optiquerabat.ma, mot de passe rabat-dev-2026). Donnee de developpement, aucune fixture commitee dans un chemin de production

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 6] Four open questions block the facturation schema and need a Moroccan comptable, not research: TVA rate on optical goods after the 2026 reform, série per magasin vs per company, TVA treatment of the acompte, and whether the facture is issued at commande or délivrance. Start these during Phase 1.
- [Phase 1] CNDP prior authorization is reported at 2-4 months and the Moroccan merchant contract at weeks to months. Both must be in flight from day one or they become the launch critical path.
- [Phase 12] Recurring card-on-file on Moroccan rails is a vendor claim and needs sandbox proof; if false, billing falls back to invoice plus payment link per period.
- [Phase 3] **Les sept vérifications manuelles au navigateur du point de contrôle 03-12 n'ont pas été effectuées.** Le propriétaire a approuvé sur la preuve automatisée (50 tests frontend, 179 backend, build à 0) et a explicitement dit ne pas les avoir exécutées. Restent ouvertes : connexion sans clignotement, stabilité de la carte à l'erreur, compte à rebours à la onzième tentative, atterrissage forcé sans issue, traversée au clavier seul, lecture en français contre `03-UI-SPEC.md` 9.3 (la vérification manuelle nommée dans `03-VALIDATION.md`), bannière de connexion perdue. À reprendre à la vérification de phase — vitest rend dans jsdom et ne voit ni clignotement, ni saut de mise en page réel, ni anneau de focus, ni si une phrase se lit comme du français. Détail : `.planning/phases/03-comptes-permissions-app-shell/03-12-SUMMARY.md`. **S'y ajoute la confirmation au navigateur du quick 260917-04r** (connexion réussie depuis `http://localhost:5173/connexion`, et `Host: localhost:5173` dans les en-têtes reçus par Django) : le correctif est prouvé par reproduction HTTP, pas par un humain devant l'écran. Les huit vérifications se font en une seule passe. **S'y ajoutent les huit étapes du point de contrôle 03-13** (les huit entrées en propriétaire, la densité sous `VITE_NAV_COMPLET=1`, l'application visiblement plus petite d'un gérant, l'absence totale de contrôle en mono-magasin, le changement de portée sans changement de route, la traversée au clavier seul puis sous VoiceOver — la vérification manuelle nommée dans `03-VALIDATION.md` —, `Ctrl+P`, et le zoom à 200 %). Le propriétaire a **commencé** cette traversée, y a découvert le défaut du changement de mot de passe forcé, et **n'a rendu aucun verdict sur le reste** : aucune des huit étapes n'est approuvée ni déclarée passée. Trois des six décisions du point de contrôle repeignent ou redimensionnent le shell (accent `#2563EB`, retrait de `Ctrl+B`, borne du tiroir à 1024px), donc la passe doit se faire **après** elles — c'est le cas. Détail : `.planning/phases/03-comptes-permissions-app-shell/03-13-SUMMARY.md`. **S'y ajoutent enfin les huit étapes du point de contrôle 03-14** (créer un gérant et voir la bannière « aucun droit », la cascade de prérequis dans les deux sens avec **un seul** `Annuler`, l'état mixte et `Uniformiser`, un compte mono-magasin sans aucun `Par magasin`, le dialogue de désactivation et l'absence du mot « supprimer », l'absence d'un code **dans l'onglet réseau** en gérant-gestionnaire, la traversée au clavier puis sous VoiceOver, et la relecture contre le lexique de 9.3). Le propriétaire s'est arrêté à **l'étape 1, qui était bloquée** : l'écran n'était pas atteignable. **Aucune des huit n'est approuvée ni déclarée passée ; l'étape 1 a été ré-activée par le correctif mais n'a pas été rejouée par une personne.** L'étape 4 est désormais réellement vérifiable : l'affaire `rabat` (un seul magasin) existe en développement. Détail : `.planning/phases/03-comptes-permissions-app-shell/03-14-SUMMARY.md`. **Total : 24 vérifications manuelles en attente, à faire en une seule passe à la vérification de phase 3.**

## Session Continuity

Last session: 2026-09-17T13:19:18.270Z
Stopped at: Completed 03-14-PLAN.md (comptes et droits). La phase 3 est complete cote CODE : 14 plans, 14 summaries. Le point de controle a releve un BLOCAGE — l'ecran etait inatteignable par l'interface, corrige — et rendu trois decisions, toutes appliquees. AUCUNE des huit etapes de verification humaine n'est approuvee : l'etape 1 est re-activee mais non rejouee. Suivant : la verification de phase 3, dont la passe manuelle au navigateur (24 verifications accumulees depuis 03-12)
Resume file: None

Serveurs de developpement laisses TOURNANTS : Vite sur 5173 (navigation filtree, l'etat livre) et sur 5174 (`VITE_NAV_COMPLET=1`, la densite a huit entrees), Django sur 127.0.0.1:8010 — le proprietaire peut reprendre la traversee, celle du shell (03-13) comme celle de l'ecran des droits (03-14).

Deux affaires en base de developpement, et c'est la forme a deux locataires que le projet exige partout ailleurs :

| Affaire | Magasins | Proprietaire | Gerant | Mot de passe |
|---|---|---|---|---|
| `anfa` — Optique Anfa | ANFA, MAARIF | `amine@optiqueanfa.ma` | `karim@optiqueanfa.ma`, `nadia@optiqueanfa.ma`, `salma@optiqueanfa.ma` | inchange |
| `rabat` — Optique Rabat | **AGDAL seul** | `hind@optiquerabat.ma` | `youssef@optiquerabat.ma` | `rabat-dev-2026` |

L'affaire `rabat` sert l'etape 4 du point de controle 03-14 — « un compte a un seul magasin ne voit ni `Par magasin` ni case a cocher ». Donnee de developpement : aucune fixture ne la cree dans un chemin de production.
