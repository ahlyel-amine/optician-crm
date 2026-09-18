---
phase: 04-clients-ordonnances
plan: 06
subsystem: domain
tags: [ordonnance, photo, stockage, tenancy, telemetrie, openapi, loi-09-08]

requires:
  - phase: 04-clients-ordonnances
    plan: 04
    provides: "le modèle `Ordonnance`, ses contraintes, `OrdonnanceFactory`"
  - phase: 04-clients-ordonnances
    plan: 05
    provides: "le versionnement, `VueOrdonnances` et ses deux classes de permission"
  - phase: 02-tenancy
    provides: "`current_alias()` fail-closed, les fixtures à deux locataires, `telemetry.before_send`"
provides:
  - "`StockageOrdonnances` — un `Storage` Django dont le préfixe vient du contexte vivant"
  - "cinq colonnes de photo sur `Ordonnance`, écrites par un `update_fields` nommé"
  - "`attacher_photo` — taille, type déclaré et octets magiques, une seule fois"
  - "`POST`/`GET /api/ordonnances/<id>/photo/`, derrière `ordonnance.voir` et `ordonnance.saisir`"
  - "`SENSITIVE_KEY` élargie aux six clés de nom de fichier"
  - "la limite de TENANT-09 écrite dans `backup.py` et dans `deferred-items.md`"
affects: [04-09-historique-et-photo, 12-offboarding, 01-legal]

tech-stack:
  added: []
  patterns:
    - "`FileField(storage=<appelable>)` est correct pour choisir le BACK-END (une fois, au déploiement) et fatal pour choisir le LOCATAIRE (par requête) — la distinction règle les deux besoins d'un coup"
    - "Un appelable de `storage=` rend la migration indépendante du réglage : `FileField.deconstruct()` resérialise `_storage_callable`, donc le fichier nomme la fonction"
    - "Le nom stocké se fabrique dans le `Storage` (`get_available_name`), pas seulement dans le service : un futur appelant distrait ne peut alors pas persister le nom du patient"
    - "`model_to_dict` saute les champs `editable=False` — une comparaison champ par champ doit passer par `_meta.concrete_fields`"
    - "Une menace sur la forme d'un champ se teste sur sa PROPRIÉTÉ observable, jamais sur sa forme : « le préfixe change avec le locataire » survit à un refactor que « storage n'est pas un appelable » interdirait à tort"

key-files:
  created:
    - domaine/ordonnances/stockage.py
    - domaine/ordonnances/migrations/0002_photo.py
    - tests/test_ordonnance_photo.py
    - .planning/phases/04-clients-ordonnances/deferred-items.md
  modified:
    - config/settings/base.py
    - config/settings/test.py
    - config/urls.py
    - .env.example
    - .gitignore
    - domaine/ordonnances/models.py
    - domaine/ordonnances/serializers.py
    - domaine/ordonnances/services.py
    - domaine/ordonnances/vues.py
    - domaine/ordonnances/urls.py
    - plateforme/projection/registre.py
    - plateforme/tenancy/telemetry.py
    - plateforme/control_plane/backup.py
    - tests/test_telemetry.py
    - tests/test_schema_contrat.py
    - web/src/api/schema.yml
    - web/src/api/types.gen.ts

key-decisions:
  - "`storage=` reçoit un appelable **contre la lettre du plan**, parce que l'appelable ne décide que du back-end et rend la migration indépendante du réglage ; la menace T-04-39 est tenue par un test de propriété, pas par une interdiction de forme"
  - "Une cinquième colonne, `photo_par` : le plan en nommait quatre et passait `par` au service sans lui donner où atterrir"
  - "Le refus sous le mauvais locataire est un `FileNotFoundError` — mesuré, pas supposé"
  - "Le nom du fichier envoyé n'est conservé **nulle part**, donc `04-UI-SPEC.md` §22.2 n'est pas satisfaite (D-4-4)"
  - "TENANT-09 : consigner, ne pas étendre — la raison est recopiée ci-dessous"
  - "Le schéma et le client TS sont régénérés dans le commit de la cause, pas dans celui de la tâche 3"

requirements-completed: []

duration: 75min
completed: 2026-09-18
---

# Phase 4 Plan 06 : la photo de l'ordonnance — Summary

**Le premier fichier du produit : un `Storage` Django dont le préfixe est redérivé de
`current_alias()` dans chaque méthode — donc qu'un locataire B présentant le chemin
stocké d'un locataire A ne peut pas résoudre —, une attache unique qui n'écrit que ses
cinq colonnes, des octets qui ne sortent que d'une vue ayant déjà résolu `ordonnance.voir`,
et trois limites écrites plutôt que découvertes.**

## Les nombres relevés, pas devinés

| Porte | Avant | Après |
|---|---|---|
| `uv run pytest -q -m "not slow"` | **264 passed / 33 deselected** | **276 passed / 33 deselected** |
| `uv run pytest -q -m slow` | 33 passed | **33 passed, 0 failed** |
| `npm --prefix web test` | 160 passed | **160 passed** (aucun fichier web touché hors `src/api/`) |
| `npm --prefix web run build` | exit 0 | **exit 0** |
| `uv run python manage.py check` | 0 issue | **0 issue** |
| `makemigrations --check --dry-run` | code 0 | **code 0 — « No changes detected »** |
| `spectacular --fail-on-warn` + `diff -q` | 0, muet | **0, muet** |
| `migrate_all --check` | `2 ok, 0 behind` (run #16 : **2 behind** après la migration) | **`2 ok, 0 behind` (run #18)** |

**Pour le tableau de comptage de `04-VALIDATION.md` §1 :**

| Plan | Tests écrits (`def`) | Emplacements neufs |
|---|---|---|
| 04-06 | **7** | **12** (12 dans la porte rapide, 0 dans `-m slow`) |

Sept `def` : six dans `tests/test_ordonnance_photo.py`, un dans `tests/test_telemetry.py`.
Douze emplacements : les six de la photo, plus le test de télémétrie **paramétré sur ses
six clés**. Vérifié par `--collect-only` — 6 et 10 (4 préexistants + 6) — et le delta
264 → 276 le confirme.

Le plan nommait six tests ; sept ont été écrits. Le septième est
`test_client09_le_champ_ne_fige_aucun_locataire_a_la_construction`, justifié plus bas.

## Les rouges observés avant la tâche 2, un par un

Premier passage de la tâche 1 : **11 failed, 4 passed**.

| Test | Message d'échec observé |
|---|---|
| `…la_photo_est_rangee_sous_le_client_lie` | `ImportError: cannot import name 'attacher_photo' from 'domaine.ordonnances.services'` |
| `…un_chemin_d_un_autre_client_est_refuse` | `ModuleNotFoundError: No module named 'domaine.ordonnances.stockage'` |
| `…l_image_exige_le_droit_ordonnance_voir` | `ImportError: cannot import name 'attacher_photo' …` |
| `…une_photo_s_attache_une_fois_et_ne_se_remplace_jamais` | `ImportError: cannot import name 'VuePhotoOrdonnance' from 'domaine.ordonnances.vues'` |
| `…un_televersement_est_borne_en_taille_et_en_type` | `ImportError: cannot import name 'VuePhotoOrdonnance' …` |
| `…un_nom_de_fichier_n_atteint_pas_sentry_en_clair` (×6) | `AssertionError: La clé « photo » survit dans extra avec 'ordonnance_benali_ahmed.jpg'` — puis `image`, `fichier`, `scan`, `upload`, `piece_jointe`, **six fois, une par clé** |

### Le rouge le plus intéressant du plan, et pourquoi il l'est

Les cinq premiers sont des absences : le module n'existe pas encore, ce qui est la forme
normale d'un rouge de tâche 1. **Le sixième est différent** : il échoue contre le code
**livré, en production, tel qu'il est depuis la phase 2**.

```
assert 'ordonnance_benali_ahmed.jpg' == '[redacted]'
```

La recherche de phase avait relevé ce trou par lecture (`04-RESEARCH.md` §4.6 : « une
alternance de regex, dans le plan qui ajoute le téléversement »). Le test le **démontre**
avant de le fermer : six clés sous lesquelles un nom de fichier voyage, six valeurs
arrivant intactes dans un événement Sentry — y compris dans `frame["vars"]`, que
`send_default_pii = False` ne couvre pas, et qui est le chemin par lequel une
`ValidationError` d'un sérialiseur de téléversement l'aurait emporté.

Le contrôle positif (`duree_ms` non caviardée) est dans le même test, et il n'est pas
décoratif : sans lui, un `SENSITIVE_KEY` réduit à `.` serait vert.

## La forme exacte du refus, mesurée par une sonde jetable

Le plan demandait de relever, et non de supposer, ce que le stockage rend sous le mauvais
locataire. Une sonde jetable a présenté six chemins sous le locataire B et quatre hors de
tout contexte, en imprimant **le type et le message de l'exception** :

```
nom stocké                    -> '1/943374eec2974c6da677ab2f1c0d8e92.jpg'
B présente le nom stocké de A -> FileNotFoundError: [Errno 2] No such file or directory: '/private/var/.../tenant_b/1/9433...'
B: exists() sur le nom de A   -> False          (aucune exception, et c'est la bonne réponse)
B: traversée ../tenant_a/     -> SuspiciousFileOperation: Detected path traversal attempt in '../tenant_a/1/9433...'
B: chemin absolu              -> SuspiciousFileOperation: Detected path traversal attempt in '/etc/passwd'
B: dossier non numérique      -> SuspiciousFileOperation: Le dossier 'benali' n'est pas un numéro de version...
B: size() sur le nom de A     -> FileNotFoundError
hors contexte: open()         -> NoTenantBound: No client is bound to this context…
hors contexte: exists()       -> NoTenantBound
hors contexte: url()          -> NotImplementedError: Une photo d'ordonnance n'a pas d'adresse directe…
hors contexte: delete()       -> NotImplementedError: Une photo d'ordonnance ne s'efface pas…
```

**Trois choses que la sonde apprend, et qu'une supposition aurait ratées.**

1. **Le refus du cas réel est un `FileNotFoundError`, pas une `SuspiciousFileOperation`.**
   C'est exactement ce qu'il faut : le nom stocké de A est un chemin **relatif
   parfaitement licite**, rien en lui n'est suspect. Ce qui le refuse n'est aucun
   contrôle de sécurité explicite — c'est la **redérivation du préfixe** : sous B, il
   désigne un fichier de l'arborescence de B, qui n'existe pas. La garantie est
   structurelle, pas défensive, et c'est pourquoi le test accepte les deux formes et
   assert surtout qu'**aucun octet ne sort**.

2. **Les traversées fabriquées sont refusées par le cadre, pas par mon code.**
   `validate_file_name(..., allow_relative_path=True)` arrive le premier et rend
   « Detected path traversal attempt ». Mon `is_relative_to(prefixe)` est donc un filet
   qui, sur ces cas-là, **n'est jamais consulté** — dit autrement, c'est une garde que
   rien n'éprouve, et la docstring le dit plutôt que de laisser croire le contraire.
   C'est la leçon du plan 04-04 (« une contrainte qu'une autre intercepte d'abord n'est
   pas éprouvée ») appliquée à un chemin de fichier.

3. **Le contrôle « le dossier est un numéro de version », lui, est bien celui qui
   refuse** `benali/x.jpg` — il n'est pas mort. C'est le seul de mes trois contrôles qui
   attrape un cas que le cadre laisse passer.

## La décision TENANT-09, recopiée ici pour être lisible sans ouvrir `deferred-items.md`

`backup_client` produit **un** `pg_dump` et rien d'autre — lu de bout en bout, pas
supposé. Une photo qui vit hors de la base est donc hors de la garantie de TENANT-09
(« sauvegarde par client, restauration mono-client **vérifiée** »). Restaurer ce `.dump`
seul rend toutes les lignes, chemin de photo compris, et **aucun fichier image**.

> **Retenu : consigner, ne pas étendre.** Étendre l'artefact obligerait à passer du
> `.dump` unique à une archive, donc à changer le chemin de restauration **et** la
> comparaison `tenant_checksum` que la phase 2 a prouvés par un exercice réel — pour un
> back-end de stockage que la **phase 1 n'a pas encore choisi**, et qu'il faudrait donc
> refaire. Le travail serait fait deux fois, et la seconde fois contre un chemin de
> restauration qu'on aurait entre-temps fragilisé.
>
> **Mais la garantie ne devient pas fausse en silence.** Cinq lignes ajoutées à la
> docstring de `backup_client`, nommant ce que l'artefact ne couvre pas et pointant
> **D-4-1**.

`deferred-items.md` porte quatre entrées : **D-4-1** (TENANT-09), **D-4-2** (la rétention
à dix ans et l'archive d'offboarding de la phase 12 ont le même trou), **D-4-3** (aucun
PDF en pièce jointe, phase 9), **D-4-4** (le nom du fichier n'est affiché nulle part,
contre `04-UI-SPEC.md` §22.2).

## Ce que la garantie repose sur, écrit franchement

L'isolation des **lignes** entre opticiens repose sur `REVOKE CONNECT` et une base
séparée — une frontière *sous* l'application. L'isolation des **fichiers** repose sur
Python et sur une seule classe. **Il n'y a aucun `REVOKE` en dessous**, et la docstring du
module le dit avant de dire quoi que ce soit d'autre.

Le contrôle compensatoire est `test_client09_un_chemin_d_un_autre_client_est_refuse` et
ses trois moitiés — refus sous B, **octets bien rendus sous A**, refus hors contexte. La
moitié du milieu est celle sans laquelle le test serait le plus rassurant et le plus vide
de la suite : une implémentation qui refuse tout la ferait rougir.

## Commits par tâche

1. **Tâche 1 — les tests, rouges d'abord** — `ea10cab` (test)
   `tests/test_ordonnance_photo.py`, `tests/test_telemetry.py`
2. **Tâche 2 — le stockage, le champ, les deux routes, le contrat** — `0081080` (feat)
   `config/settings/base.py`, `config/settings/test.py`, `config/urls.py`,
   `.env.example`, `.gitignore`, `domaine/ordonnances/{stockage,models,serializers,services,vues,urls}.py`,
   `domaine/ordonnances/migrations/0002_photo.py`, `plateforme/projection/registre.py`,
   `tests/test_ordonnance_photo.py`, `tests/test_schema_contrat.py`,
   `web/src/api/schema.yml`, `web/src/api/types.gen.ts`
3. **Tâche 3 — la télémétrie, la limite de TENANT-09** — `a9fbb6e` (feat)
   `plateforme/tenancy/telemetry.py`, `plateforme/control_plane/backup.py`,
   `.planning/phases/04-clients-ordonnances/deferred-items.md`
4. **Hors tâches — la garde de T-04-39** — `b233e54` (test)
   `domaine/ordonnances/models.py`, `tests/test_ordonnance_photo.py`

Chemins nommés aux quatre commits, jamais `git add -A`, aucune mention de Claude.

## Déviations du plan

### 1. [Choix de forme, contre la lettre du plan] `storage=` reçoit un appelable

Le plan et la menace **T-04-39** disent : « instance de module, **jamais** un appelable ».
Le champ en porte un — `storage=stockage_des_photos` — et voici pourquoi.

La menace réelle est un appelable qui résout le **locataire** :
`lambda: StockageDuLocataire(current_alias())` figerait celui qui est lié à l'import.
`stockage_des_photos` ne résout que le **back-end** —
`import_string(settings.ORDONNANCE_STORAGE)()` — c'est-à-dire une décision de
déploiement, arrêtée une fois, qu'il est *correct* de figer à la construction du champ.
Le locataire, lui, reste redérivé dans chaque méthode.

Ce que la forme « instance » aurait coûté, et qui n'est pas théorique : **la migration.**
`FileField.deconstruct()` resérialise `_storage_callable` quand il existe, donc
`0002_photo.py` nomme `domaine.ordonnances.stockage.stockage_des_photos`. Avec une
instance, il aurait nommé la classe *effectivement configurée*, et
`makemigrations --check` serait devenu rouge sur tout déploiement réglant
`ORDONNANCE_STORAGE` — c'est-à-dire exactement le jour où la phase 1 choisit le back-end.

**Ce qui tient la menace à la place de l'interdiction de forme :**
`test_client09_le_champ_ne_fige_aucun_locataire_a_la_construction` (le septième test),
qui vérifie la **propriété** — le préfixe change avec le locataire lié et n'existe pas
sans lui — au lieu de la forme. **Contrôle négatif joué** : un `Storage` qui gèle un
locataire dans son `__init__` fait bien rougir ce test (`Le stockage du champ rend le
même préfixe … pour deux locataires différents`). Une assertion « `storage` n'est pas un
appelable » aurait interdit une forme sûre et laissé passer une instance dont
`__init__` calculerait le préfixe.

Le commentaire du champ interdit explicitement la seule chose dangereuse : **ne jamais
faire entrer le locataire dans cet appelable.**

### 2. [Rule 2 — fonctionnalité manquante] Une cinquième colonne, `photo_par`

Le plan nommait quatre colonnes et donnait au service la signature
`attacher_photo(ordonnance, fichier, *, par)` — un paramètre sans nulle part où atterrir,
donc soit un argument mort, soit une provenance perdue. `photo_par` suit `created_par` :
adresse en chaîne, jamais une clé étrangère (CLAUDE.md #11), lisible dix ans plus tard.
La provenance d'une pièce justificative de santé est ce qui rend une mauvaise pièce
jointe discutable au comptoir.

Le test de l'attache unique autorise donc **cinq** colonnes à bouger, et c'est lui qui a
signalé l'écart en rougissant sur `['photo_par']`.

### 3. [Discipline d'orchestration] Le contrat régénéré à la tâche 2, pas à la tâche 3

Le plan plaçait `spectacular` et `api:types` dans la tâche 3. La consigne d'exécution est
formelle depuis le plan 04-05 : *si vous touchez un sérialiseur, une vue ou une route,
régénérez `schema.yml` **et** le client TS dans le même commit*. La cause est la tâche 2 ;
les deux artefacts y sont donc. La tâche 3 ne contient que ce qui lui appartient
réellement.

### 4. [Écart de périmètre] Deux fichiers hors de la liste du plan

- **`config/urls.py`** — la route `/api/ordonnances/<id>/photo/` est **plate** (le plan et
  `04-09` l'écrivent ainsi), donc elle demande un second préfixe monté. Le plan listait
  `domaine/ordonnances/urls.py` sans le fichier qui le monte. Forme reprise de
  `urlpatterns_gestion` : une seconde liste nommée dans le module, importée
  explicitement.
- **`tests/test_schema_contrat.py`** — `test_perm06_le_contrat_porte_les_routes_montees…`
  est un **inventaire**, et un inventaire auquel on n'ajoute pas la route qu'on vient de
  monter cesse d'en être un. La photo est même le cas que ce test décrit depuis le
  début : une `APIView` nue, sans routeur ni `serializer_class`, que le générateur
  ignorerait en silence.

### 5. [Écart mineur] `201` là où le plan écrivait `200`

Une attache crée une ressource ; `201 Created` est le code qui le dit. Le test accepte
`200` ou `201` sur la première attache — ce qu'il refuse absolument, c'est un `2xx` sur la
**seconde** — et exige `409` sur celle-là.

### 6. [Rule 1 — correction trouvée à l'exécution] Deux littéraux attrapés par la garde clinique

`test_client07_les_bornes_vivent_a_un_seul_endroit` a rougi sur `services.py` :
`ligne 263 : 10, ligne 262 : 10, ligne 248 : 4, ligne 250 : 4`. Le `10` venait de
`ceil(octets * 10 / (1024*1024))`, le `4` des offsets `tete[:4]` et `tete[4:8]` du
renifleur d'octets magiques. Ce sont des **faux positifs de nature** — un diviseur de
formatage et un offset ISO-BMFF — mais la garde ne peut pas le savoir, et l'affaiblir
pour deux nombres serait la désactiver.

Réécrit sans les littéraux plutôt que sorti de la vue de la garde : `Decimal.quantize`
avec `ROUND_UP` pour les mégaoctets (et c'est de toute façon plus juste que `float`), et
`b"ftyp" in tete[:12]` avec la marque épinglée à `tete[8:12]` pour le HEIC. **La garde
reste stricte sur `services.py`** — c'était le choix à ne pas rater.

## Deux mesures faites plutôt que recopiées

### `model_to_dict` est aveugle à la moitié de la ligne

La comparaison champ par champ de l'attache unique passait d'abord par
`django.forms.models.model_to_dict`. Elle a rougi sur l'assertion de contrôle — « au
moins une colonne de photo a bougé » — et la cause est que **`model_to_dict` saute tout
champ `editable=False`**, donc précisément `photo`, la colonne que ce test existe pour
surveiller.

Sans cette assertion de contrôle, le test aurait été **vert en comparant une ligne dont
il ne voyait pas la colonne qui change**. Remplacée par une lecture de
`_meta.concrete_fields`.

### `FileField.__init__`, lu dans le Django installé

```python
self.storage = storage if storage is not None else default_storage
if callable(self.storage):
    self._storage_callable = self.storage
    self.storage = self.storage()      # une fois, à la construction du champ
```

Django **6.1.1**. C'est la ligne qui rend impossible un stockage par locataire construit
par appelable, et c'est elle qui est citée dans la docstring pour que personne ne
« corrige » le module dans ce sens.

## Le contrat d'API

Deux opérations nouvelles, `--fail-on-warn` à **0** et diff vide contre le fichier
commité :

```
GET  /api/ordonnances/{id}/photo/  -> 200 image/* (binary) | 404
POST /api/ordonnances/{id}/photo/  -> 201 PhotoOrdonnance  | 409
     requestBody: multipart/form-data -> PhotoTeleversee
```

Le `multipart` et la réponse binaire sont **déclarés** dans `@extend_schema`, pas devinés
— c'est la raison pour laquelle le drapeau n'a pas eu à être relâché. `openapi-typescript`
les rend sans broncher, et le build passe.

## Ce que ce plan ne fait pas, délibérément

- **Aucun rendu ajouté.** La lecture est une `APIView` rendant un `FileResponse`, pas un
  rendu au sens de `plateforme/projection/` : elle ne sérialise aucun champ et ne consulte
  pas le registre. La liste `RENDUS` de `tests/test_projection.py` reste donc à **quatre**,
  et c'est une décision écrite dans la docstring de la vue plutôt qu'une omission. Ce qui
  la garde est son test de droit dédié.
- **Aucune adresse directe, aucun service de fichiers statiques, aucune adresse
  pré-signée.** `grep -rn "MEDIA_URL" config/ plateforme/ domaine/` ne rend rien, et
  `Storage.url()` **lève** avec un message qui explique pourquoi. L'échappatoire
  `X-Accel-Redirect`, après vérification du droit, est consignée dans la docstring — pas
  construite.
- **Pillow n'est pas installée.** `ImageField` prouverait seulement que les octets sont
  décodables ; poser une bibliothèque d'images sur un flux non fiable élargit la surface
  d'attaque au service d'une garantie inutile (T-04-43).
- **Aucun fichier sous `web/src/pages/` ni `web/src/champs/`** — l'interface est aux plans
  04-08 et 04-09. Vérifié : `git diff --stat ea10cab~1..HEAD -- web/src/pages/ web/src/champs/`
  rend zéro ligne.

## Aucune photo n'est commise, et ne peut l'être

- `/media/` est dans `.gitignore`, avec le commentaire qui dit que ce n'est pas du
  ménage : une photo d'ordonnance commise est une fuite de donnée de santé dans un
  historique qui n'est pas révocable.
- `git status --porcelain media/` : **vide**. `git ls-files media/` : **vide**.
- `git log --name-only b3b5161..HEAD | grep -c '^media/'` : **0**, sur un intervalle de
  **34 commits** — vérifié non vide d'abord, parce qu'en phase 03.1 une garde du même
  genre est passée pour la mauvaise raison sur un intervalle qui rendait zéro commit.
- La suite de tests écrit dans un `mkdtemp` de session, jamais dans l'arbre du dépôt.

## Exigences : aucune cochée

CLIENT-09 a ici sa **moitié serveur**. Son écran — le sélecteur de fichier, la vignette,
le dialogue, la phrase « Une photo ne se remplace pas » — est le plan `04-09`, et le
projet tient le précédent depuis les plans 03-05 à 03-10 : une case cochée veut dire
qu'un opticien peut le faire. C'est `04-09` qui coche.

## État pour la suite

**Prêt :**

- **`04-09`** trouve les deux routes sous la forme exacte que son plan attend
  (`GET`/`POST /api/ordonnances/<id>/photo/`), le type TS généré, et sur chaque version
  d'ordonnance : `a_une_photo` (le booléen dont dépend l'affichage de la vignette ou du
  contrôle d'attache), `photo_type`, `photo_octets`, `photo_attachee_le`, `photo_par`.
- **La phase 1** trouve, à l'endroit du réglage et dans `deferred-items.md`, ce qu'elle
  doit décider : la juridiction, puis le back-end (`ORDONNANCE_STORAGE`).

**À ne pas manquer :**

- **`04-09` ne peut pas afficher le nom du fichier** que `04-UI-SPEC.md` §22.2 décrit : il
  n'est conservé nulle part, exprès. Lire **D-4-4** avant d'écrire ce bloc d'écran — la
  vignette est le meilleur contrôle de mauvaise pièce jointe, et la version plus la date
  d'attache sont servies.
- **`storage.url()` lève.** Un `ModelSerializer` qui exposerait la colonne `photo`
  produirait un 500 à la première lecture. C'est pourquoi elle est `editable=False`, et
  pourquoi seul le booléen sort.
- **La photo est hors de la sauvegarde** (D-4-1). Toute phase qui promet « on restaure un
  client » doit lire cette entrée d'abord.
- **Ne pas faire entrer le locataire dans `stockage_des_photos`.** Le commentaire du champ
  et le septième test existent pour cela.

---
*Phase : 04-clients-ordonnances*
*Terminé : 2026-09-18*

## Self-Check: PASSED

Les cinq fichiers créés existent sur le disque, les quatre commits `ea10cab`, `0081080`,
`a9fbb6e` et `b233e54` existent dans l'historique, et les six greps d'acceptation du plan
rendent chacun leur symbole — `def test_client09_un_chemin_d_un_autre_client_est_refuse`,
`current_alias` dans `stockage.py`, `piece_jointe` et `upload` dans `telemetry.py`,
`TENANT-09` dans `deferred-items.md`, `D-4-1` dans `backup.py`, `FileResponse` dans
`vues.py`.

Quatre affirmations vérifiées plutôt que supposées :

- **Le décompte de tests.** `grep -c '^def test_'` rend **6** dans
  `tests/test_ordonnance_photo.py`, et `--collect-only` rend **6** et **10** (4
  préexistants + 6 paramétrages) — soit les 12 emplacements neufs du delta 264 → 276.
- **Le refus sous le mauvais locataire** est un `FileNotFoundError`, relevé par une sonde
  jetable et non déduit de la lecture du code.
- **La garde de T-04-39 rougit vraiment** : contrôle négatif joué avec un `Storage` qui
  gèle un locataire dans son `__init__`.
- **Aucun fichier sous `media/`** n'est suivi ni présent dans les 34 commits de
  l'intervalle de la phase — intervalle vérifié non vide **avant** de conclure.

`state advance-plan` n'a pas été exécuté. Rien n'a été fusionné vers `main`.
