---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 03-08-PLAN.md
last_updated: "2026-09-16T21:15:18.936Z"
last_activity: 2026-09-16
progress:
  total_phases: 12
  completed_phases: 1
  total_plans: 21
  completed_plans: 16
  percent: 76
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-09)

**Core value:** The counter completes a sale end to end — client, ordonnance, payment including acompte, landing in that magasin's caisse — producing a facture legally valid in Morocco every time.
**Current focus:** Phase 3 — Comptes, Permissions & App Shell (Phase 1 continues in parallel as a calendar track)

## Current Position

Phase: 3 of 12 (Comptes, Permissions & App Shell)
Plan: 9 of 14 complete in current phase (03-01 à 03-08 et 03-11) ; l'authentification par session existe et la vague 6 est close — les cinq points de terminaison /api/auth/ sont servis, PERM-01 est vert. Le prochain est 03-09 (surface d'octroi), qui consomme le catalogue et le second usage sanctionné de peut_quelque_part
Status: Executing
Last activity: 2026-09-16

Progress: [████████░░] 76%

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

## Accumulated Context

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

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 6] Four open questions block the facturation schema and need a Moroccan comptable, not research: TVA rate on optical goods after the 2026 reform, série per magasin vs per company, TVA treatment of the acompte, and whether the facture is issued at commande or délivrance. Start these during Phase 1.
- [Phase 1] CNDP prior authorization is reported at 2-4 months and the Moroccan merchant contract at weeks to months. Both must be in flight from day one or they become the launch critical path.
- [Phase 12] Recurring card-on-file on Moroccan rails is a vendor claim and needs sandbox proof; if false, billing falls back to invoice plus payment link per period.

## Session Continuity

Last session: 2026-09-16T21:15:18.934Z
Stopped at: Completed 03-08-PLAN.md
Resume file: None
