---
phase: 03-comptes-permissions-app-shell
plan: 05
subsystem: acces-resolu-et-middleware
tags: [comptes, permissions, PERM-03, PERM-04, PERM-06, claude-md-8, claude-md-13, T-03-22, T-03-23, T-03-24, T-03-25, T-03-26, T-03-27, T-03-28]
requires:
  - 03-04 (permissions_catalogue.Permission, AccesMagasin, DroitAccorde — les trois tables lues)
  - 03-02 (les stubs pending nommés, GerantFactory / ProprietaireFactory / UtilisateurFactory, deux_magasins)
  - 02-03 (TenantMiddleware, le contexte de locataire, et la règle du clear() plutôt que reset())
  - 02-02 (domaine.magasins.Magasin — actif, jamais supprimé)
provides:
  - plateforme/comptes/acces.py — Acces gelé, ANONYME, SCHEMA, acces_pour(), _PorteurAcces
  - droits_par_magasin - Mapping[magasin_id, frozenset[str]], et non un ensemble plat
  - peut(code, magasin_id=None) conjonction ; peut_quelque_part(code) union ; magasins_pour(code)
  - plateforme/comptes/middleware.py — AccesMiddleware, request.acces paresseux
  - le garde source qui énumère les appelants de peut_quelque_part
affects:
  - 03-06 (registre de projection — consomme Acces.SCHEMA et _PorteurAcces)
  - 03-07 (portée des lignes et des agrégats — consomme magasins_ids et pour_le_schema)
  - 03-08 (/api/auth/moi/ — premier appelant sanctionné de peut_quelque_part, étiquette `navigation`)
  - 03-09 (catalogue pré-intersecté — second appelant sanctionné, étiquette `catalogue`)
  - phases 5 à 10 (chaque décision d'autorisation passe par acces.peut ; la conjonction est la règle)
tech-stack:
  added: []
  patterns:
    - un accès absent est une valeur vide, jamais None — le défaut ne doit rien laisser à décider
    - une branche de privilège se matérialise à la résolution, pas à chaque site d'appel
    - un sentinelle négatif plutôt qu'un court-circuit, quand le court-circuit rouvrirait un second chemin de code
    - l'état de requête vit sur la requête ; ce qui n'est pas partagé n'a pas à être nettoyé
    - une échappatoire se garde par une énumération testée, jamais par une docstring
key-files:
  created:
    - plateforme/comptes/acces.py
    - plateforme/comptes/middleware.py
  modified:
    - config/settings/base.py
    - tests/test_magasin_acces.py
    - tests/test_comptes_droits.py
decisions:
  - "peut(code) sans magasin est une CONJONCTION sur tous les magasins accordés — jamais une union"
  - "droits_par_magasin porte une entrée par magasin accordé même vide, sans quoi la conjonction n'a pas de sens"
  - "Acces.SCHEMA passe par un magasin fictif MAGASIN_DU_SCHEMA = -1, pas par un court-circuit `if pour_le_schema` dans peut()"
  - "peut_quelque_part est gardée par un garde source à étiquettes, pas par un comptage d'appelants"
  - "le test de non-fuite sur thread réutilisé remplace le résolveur, délibérément — le sujet est le rangement du middleware"
  - "REQUIREMENTS.md n'est pas coché : PERM-03 et PERM-04 sont réclamées par plusieurs plans de la phase"
metrics:
  tasks: 2
  commits: 2
  tests-added: 10
  tests-unpended: 3
  suite: 135 passed, 30 pending (122 passed, 33 pending avant)
  duration: ~50 min
  completed: 2026-09-15
---

# Phase 3 Plan 05 : l'accès résolu et son middleware — Summary

`request.acces` existe, il est paresseux, il ne fuit pas d'une requête à l'autre, et il
porte **la dimension magasin** : `droits_par_magasin: Mapping[int, frozenset[str]]`, pas un
ensemble plat de permissions. C'est la couture que les phases 5 à 10 liront sans la relire,
donc ce qui suit est écrit pour être relu par elles.

## La règle à connaître avant d'appeler `peut`

**`peut(code)` sans argument magasin est une CONJONCTION.** Vrai seulement si le code est
détenu dans **tous** les magasins accordés. Pas « détenu quelque part ».

| Appel | Sémantique | Usage |
|---|---|---|
| `peut(code, magasin_id=m)` | le code est dans l'ensemble de `m` | l'autorisation nominale |
| `peut(code)` | le code est dans l'ensemble de **chaque** magasin accordé | la projection de champs |
| `peut_quelque_part(code)` | le code est dans **au moins un** | **jamais une autorisation** |
| `magasins_pour(code)` | les magasins où il est détenu | uniforme / personnalisé (UI 7.5) |

La raison est structurelle, pas prudentielle : **la projection de champs s'applique à un
serializer, pas à une ligne.** Au moment où elle décide de garder ou d'ôter `prix_achat`,
elle ne sait pas encore de quel magasin sera la ligne rendue. Une union y livrerait le prix
d'achat des articles de Maârif à un gérant qui ne détient le droit qu'à Anfa (menace
T-03-25). La conjonction est le choix fail-closed, et c'est celui que CLAUDE.md #8 impose à
cette couche comme il l'impose au contexte de locataire.

Conséquence pratique, et elle n'est pas gratuite : un gérant dont les droits sont
**personnalisés** par magasin verra, dans les rendus non scopés, l'intersection de ses
droits. C'est délibéré et c'est le bon côté pour se tromper. L'état que la quasi-totalité des
entreprises verra est la ligne **uniforme** (`03-UI-SPEC.md` 7.5), où conjonction et union
coïncident.

Une sous-décision qui porte tout cela : **`droits_par_magasin` a une entrée par magasin
accordé et actif, même quand l'ensemble associé est vide.** Sans elle, accorder un second
magasin sans y poser aucun droit rendrait subitement universels les droits du premier — la
conjonction porterait sur un seul terme. Et un `all()` sur une collection vide vaut `True`,
ce qui est exactement le fail-open à ne pas écrire ; d'où le `bool(portee)` explicite dans
`peut`.

## L'accès du propriétaire est une valeur, et `Acces.SCHEMA` aussi

`acces_pour` matérialise pour le propriétaire `frozenset(Permission.values)` **pour chaque
magasin actif**. La branche existe une fois, à la résolution ; `peut()` n'en a aucune. C'est
`03-RESEARCH.md` P3 appliqué : une branche qui saute la vérification pour les propriétaires
est une branche qu'un bug peut atteindre pour un non-propriétaire.

Le même raisonnement a décidé une question que le plan laissait ouverte. `Acces.SCHEMA` doit
porter **le catalogue complet et aucun magasin**. Deux façons de l'écrire :

| Forme | Effet |
|---|---|
| `if self.pour_le_schema: return True` dans `peut` | rouvre le second chemin de code que ce module existe pour fermer |
| une clé `MAGASIN_DU_SCHEMA = -1` dans `droits_par_magasin` | `peut` reste sans branche ; `magasins_ids` reste vide |

C'est la seconde. L'identifiant est **négatif** parce que les `Magasin` viennent d'une
séquence Postgres, qui n'en produit jamais — la collision est impossible, pas improbable. Le
test du propriétaire a été renforcé en conséquence : il refuse `pour_le_schema` dans le corps
de `peut` **au même titre** que `est_proprietaire`, parce que fermer une porte en laissant la
voisine ouverte n'aurait fermé personne. `magasins_ids` reste vide, donc la portée des lignes
(plan 03-07) ne rend rien pour le schéma — c'est `pour_le_schema` qui la court-circuite, **à
l'endroit où elle est écrite**, et pas ici.

## Comment `peut_quelque_part` est gardée, et pourquoi pas par un compteur

Le plan demande un test source qui énumère les appelants et affirme qu'ils sont **exactement
deux**. Les deux appelants sanctionnés n'existent pas encore : ils arrivent aux plans 03-08
(le champ `navigation` de `/api/auth/moi/`) et 03-09 (le catalogue pré-intersecté). Un
compteur littéral serait donc soit rouge aujourd'hui, soit `pending` — et la vérification du
plan exige qu'il **passe**.

La forme retenue ne compte pas, elle **attribue**. `tests/test_magasin_acces.py` déclare

```python
USAGES_SANCTIONNES_PEUT_QUELQUE_PART = {"navigation", "catalogue"}
```

et exige de chaque site d'appel trouvé par `ast` dans `plateforme/` qu'il porte un marqueur
`# usage-sanctionne: peut_quelque_part <étiquette>`, que l'étiquette soit l'une des deux, et
qu'aucune ne serve deux fois. Quatre assertions, dont la première est `len(...) == 2` :
**« exactement deux » est pinné sur l'ensemble sanctionné lui-même**, et le nombre
d'appelants y est contraint à l'identité.

Ce que cela achète par rapport au comptage :

- il passe à 0, à 1 et à 2 appelants sans qu'aucune assertion ne bouge — donc les plans 03-08
  et 03-09 n'ont rien à modifier ici, seulement à marquer leur ligne ;
- un troisième appelant est rouge **à la seconde où il est écrit**, non parce qu'il déborde un
  compteur, mais parce qu'il **n'a pas d'étiquette libre à prendre** ;
- il ne code en dur aucun chemin de fichier. Un compteur par nom de module aurait rougi le
  jour où 03-08 choisit `serializers.py` plutôt que `vues.py`, pour une raison qui n'a rien à
  voir avec la sécurité — et c'est ainsi qu'un garde finit par être assoupli.

Le mode de défaillance que ce garde surveille est sûr dans le mauvais sens : un troisième
appelant n'affiche rien de cassé, il autorise trop, discrètement, et personne n'ouvre de
ticket. C'est exactement pour cela qu'une docstring n'y suffisait pas.

## Le test de non-fuite remplace le résolveur, et c'est un choix

`test_perm04_lacces_ne_fuit_pas_entre_deux_requetes_sur_un_thread_reutilise` reprend la forme
de la phase 2 — `ThreadPoolExecutor(max_workers=1)`, identité du thread asserée via
`Thread.name` et non `get_ident()` — mais substitue `acces_pour` par un faux résolveur.

Trois raisons, dans cet ordre :

1. **Le sujet sous test est la discipline de rangement du middleware**, pas la résolution.
   La résolution a ses propres tests, avec deux bases réelles.
2. **Passer par la base obligerait à écrire des lignes depuis le thread du pool**, hors de la
   transaction que pytest-django annule — donc à laisser des `Utilisateur` derrière soi dans
   la base de test, avec les collisions d'unicité que cela promet aux tests suivants. Le test
   de la phase 2 accepte ce coût pour des `Magasin` ; des comptes sur `default` sont une autre
   affaire.
3. **Le faux résolveur rend la fuite observable.** Deux résolutions réelles du *même* compte
   sont indiscernables ; deux accès aux `utilisateur_id` distincts ne le sont pas.

Le contrôle positif qui referme la boucle est un test séparé,
`test_perm04_le_middleware_pose_le_vrai_acces_resolu` : vraie base, vrai gérant, vrai octroi,
et l'objet reçu par la vue est comparé à `acces_pour(gerant)`. Sans lui, le test de fuite
passerait contre un middleware branché sur n'importe quoi.

Le test compte aussi les appels au résolveur : `[11, 22, None]`, trois pour trois requêtes.
C'est la seconde moitié de la promesse « la révocation prend effet sans reconnexion » — aucun
cache par utilisateur ni par thread ne s'est glissé entre le middleware et la résolution.

## Ce que le middleware ne fait pas, et pourquoi c'est écrit

`AccesMiddleware` n'a **pas** de `finally`. Il n'y a rien à nettoyer : c'est tout l'intérêt de
poser l'accès sur la requête, dont la durée de vie borne l'attribut. Le risque réel ici est le
mimétisme — quelqu'un lit `plateforme/tenancy/middleware.py`, y voit un `finally` qui nettoie,
et reproduit la forme sans la raison. La docstring du module le dit donc franchement, et
**l'interdiction du `reset(token)` qui pèse sur `plateforme/tenancy/` est étendue en toutes
lettres à `plateforme/comptes/`**, gardée par
`test_perm04_accesmiddleware_ne_pose_rien_dans_un_contextvar`, qui lit le source en excluant
la docstring et les commentaires — parce qu'un `contextvar` correctement nettoyé passerait
tous les tests de comportement et resterait une porte ouverte pour le prochain `finally`
oublié.

L'ordre dans `MIDDLEWARE` est asseré sur les **index** de `settings.MIDDLEWARE`, pas sur le
texte du fichier : un `grep` verrait « AccesMiddleware après TenantMiddleware » dans un
commentaire aussi bien que dans la liste. Et l'assertion porte sur les trois, pas sur deux :
`Authentication → Tenant → Acces`.

## Critères d'acceptation, tels qu'exécutés

### Tâche 1

| Critère | Résultat |
|---|---|
| `grep -c 'frozen=True' acces.py` → 1 | **1** |
| `grep -c 'ANONYME' acces.py` ≥ 2 | **5** |
| aucun `est_proprietaire` dans le corps de `def peut(`, via `inspect.getsource` | **vérifié par test** — et `pour_le_schema` refusé au même titre |
| `grep -c 'actif=True' acces.py` ≥ 1 | **2** (propriétaire et gérant) |
| `grep -c 'peut_quelque_part' acces.py` ≥ 1 | **2** |
| `pytest tests/test_magasin_acces.py -q -k "proprietaire or obsolete"` | **2 passed** |
| `pytest tests/test_comptes_droits.py -q -k fuit` | **1 passed** |
| `<verify>` : `-x -k "proprietaire or obsolete or fuit or absent"` | **4 passed** |

### Tâche 2

| Critère | Résultat |
|---|---|
| `grep -c 'AccesMiddleware' config/settings/base.py` → 1 | **1** |
| index `AccesMiddleware` > index `TenantMiddleware` | **vérifié par test** sur `settings.MIDDLEWARE` |
| `grep -c 'SimpleLazyObject' middleware.py` → 1 | **3** — insatisfaisable telle qu'écrite. Voir déviation 1 |
| `grep -cE 'contextvar\|ContextVar\|reset('` → 0 hors commentaire d'interdiction | **1**, ligne 17, qui **est** la phrase d'interdiction. Voir déviation 2 |
| `pytest tests/test_magasin_acces.py -q -k "paresseux or anonyme or thread"` | **4 passed** |
| `manage.py check` | **exit 0**, no issues (0 silenced) |
| `<verify>` : `-x -k "paresseux or anonyme or thread or middleware"` | **7 passed** |

### Vérification du plan

| Critère | Résultat |
|---|---|
| `manage.py check` | **no issues (0 silenced)** |
| `pytest tests/test_magasin_acces.py tests/test_comptes_droits.py -q` | **21 passed**, 6 restent `pending` (plans 03-07 et 03-09) |
| `pytest -x -q -m "not slow and not pending"` | **105 passed** (92 avant) |
| `pytest -q -m "not pending"` | **135 passed, 30 deselected** (122 / 33 avant) |
| `grep -rn 'user.droits\|utilisateur.droits' plateforme/ \| grep -v acces.py` | **1 ligne**, `comptes/middleware.py:46` — la phrase de docstring qui énonce l'interdiction. Aucun code. Voir déviation 3 |
| `grep -rn 'user.client_id' plateforme/ \| grep -v 'acces.py\|middleware.py'` | **1 ligne**, `comptes/models.py:6` — docstring expliquant pourquoi la FK s'appelle `client`. Aucun code |
| `pytest tests/test_magasin_acces.py -q -k peut_quelque_part` | **1 passed** |
| `grep -rnE 'contextvar\|ContextVar\|reset\(' plateforme/comptes/` | **1 ligne**, la phrase d'interdiction |

## Rouge → vert

| Test | Rouge, pour quelle raison | Vert |
|---|---|---|
| `..._lacces_du_proprietaire_est_lensemble_complet_et_non_un_filtre_saute` | `ImportError: cannot import name 'acces' from 'plateforme.comptes'` | après `acces.py` |
| `..._un_droit_obsolete_sur_un_magasin_inactif_n_accorde_rien` | `ModuleNotFoundError: plateforme.comptes.acces` | idem |
| `test_perm06_lacces_absent_vaut_aucun_droit` (neuf) | `ModuleNotFoundError` | après `Acces.ANONYME` |
| `..._peut_sans_magasin_est_une_conjonction_pas_une_union` (neuf) | `ModuleNotFoundError` | après `peut` / `peut_quelque_part` / `magasins_pour` |
| `..._un_operateur_sans_client_resout_vers_anonyme` (neuf) | `ModuleNotFoundError` | après la sortie `client_id is None` |
| `..._peut_quelque_part_n_est_appele_que_depuis_ses_deux_usages_sanctionnes` (neuf) | `AssertionError: acces.py a disparu` | après `acces.py` |
| `..._un_droit_accorde_dans_un_magasin_ne_fuit_pas_vers_un_autre` (moitié résolution) | `ImportError` sur `acces_pour` | après `peut(code, magasin_id)` |
| `..._la_revocation_prend_effet_sans_reconnexion` | `Failed: non implémenté : plan 03-05` | après `acces_pour` sans cache |
| `..._accesmiddleware_est_installe_strictement_apres_tenantmiddleware` (neuf) | `AssertionError: ... a disparu de MIDDLEWARE` | après l'insertion dans `base.py` |
| `..._accesmiddleware_ne_pose_rien_dans_un_contextvar` (neuf) | `FileNotFoundError: middleware.py` | après `middleware.py` |
| `..._request_acces_est_paresseux_et_ne_coute_rien_sil_nest_pas_touche` (neuf) | `ModuleNotFoundError` | après `SimpleLazyObject` |
| `..._sur_un_chemin_anonyme_request_acces_vaut_anonyme` (neuf) | `ModuleNotFoundError` | idem |
| `..._lacces_ne_fuit_pas_entre_deux_requetes_sur_un_thread_reutilise` (neuf) | `ImportError` | idem |
| `..._le_middleware_pose_le_vrai_acces_resolu` (neuf) | `ModuleNotFoundError` | idem |

Compte des `pending` : **33 → 30**. Trois marqueurs retirés
(`..._un_droit_obsolete_sur_un_magasin_inactif_n_accorde_rien`,
`..._lacces_du_proprietaire_est_lensemble_complet_et_non_un_filtre_saute`,
`..._la_revocation_prend_effet_sans_reconnexion`), aucun ajouté, aucun marqueur appartenant à
un autre plan touché.

## Déviations du plan

### 1. [signalé] `grep -c 'SimpleLazyObject' middleware.py` → 1 est insatisfaisable

Le compteur retourne **3**, et son minimum atteignable est **2** :

| Ligne | Contenu |
|---|---|
| 28 | docstring — « `SimpleLazyObject` signifie qu'un point de terminaison qui ne touche jamais… » |
| 36 | `from django.utils.functional import SimpleLazyObject` — **l'import, obligatoire** |
| 58 | `request.acces = SimpleLazyObject(lambda: acces_pour(request.user))` — **le site unique** |

L'intention — « il y a exactement un `SimpleLazyObject` posé, et le middleware s'en sert » —
est vérifiée exactement : **un seul appel**, ligne 58, confirmé ligne par ligne et non au
compteur. Supprimer la phrase de la docstring pour satisfaire un `grep` retirerait
l'explication de la paresse ; supprimer l'import rendrait le fichier incorrect. **Signalé
plutôt qu'assoupli** : un plan futur qui réutilise ce critère devrait le formuler sur le
nombre d'appels, pas sur le nombre d'occurrences textuelles.

C'est le troisième critère de cette phase à correspondre à sa propre prose plutôt qu'au
fichier livré (03-04 en a signalé deux).

### 2. [signalé] `grep -cE 'contextvar|ContextVar|reset('` → 1, et il le doit

Le critère prévoit lui-même l'exception (« hors commentaire d'interdiction »). L'unique
occurrence est la **ligne 17**, dans le paragraphe de la docstring du module qui étend
l'interdiction du `reset(token)` de `plateforme/tenancy/` à `plateforme/comptes/` — c'est-à-dire
le texte que le critère existe pour protéger. Vérifié ligne par ligne. Aucun code de contexte
dans le fichier, et le test source
`test_perm04_accesmiddleware_ne_pose_rien_dans_un_contextvar` l'affirme en excluant
docstring et commentaires, donc sans l'exception que le `grep` doit accorder à la main.

### 3. [signalé] Le grep de couture `user.droits` sort une ligne, hors de `acces.py`

`grep -rn 'user.droits\|utilisateur.droits' plateforme/ | grep -v acces.py` retourne
`plateforme/comptes/middleware.py:46` — la phrase de docstring « Rien ne lit
`request.user.droits` ni `request.user.client_id` ». Le filtre du critère suppose que seul
`acces.py` peut légitimement contenir ces mots ; la couture est pourtant décrite là où on la
lit, c'est-à-dire dans le middleware qui la pose. **Aucun code** hors de `acces_pour` ne lit
ces attributs — vérifié en lisant la ligne, pas en comptant. Même remarque pour
`user.client_id`, dont la seule occurrence restante est une docstring de
`plateforme/comptes/models.py` expliquant pourquoi la clé étrangère s'appelle `client`.

### 4. [Rule 2 — fonctionnalité critique manquante] Trois garanties au-delà du texte du plan

- **`Acces.SCHEMA` ne court-circuite pas `peut`.** Le plan décrit `SCHEMA` sans dire comment
  l'exprimer sans branche ; la solution évidente (`if pour_le_schema: return True`) rouvrait le
  second chemin de code que la tâche 1 existe pour fermer. D'où `MAGASIN_DU_SCHEMA = -1`, et
  l'assertion source étendue à `pour_le_schema`.
- **`droits_par_magasin` porte les magasins accordés sans droits.** Le plan dit « construire la
  table `magasin_id -> codes` depuis les `DroitAccorde` » — pris au pied de la lettre, les
  magasins sans aucun droit seraient absents et la conjonction porterait sur un sous-ensemble.
  Testé par la seconde moitié de `..._peut_sans_magasin_est_une_conjonction_pas_une_union`.
- **Un contrôle positif pour le test de non-fuite.** Voir « Le test de non-fuite remplace le
  résolveur » — sans lui, le test de fuite serait vert contre un middleware branché sur rien.

### 5. [Rule 3 — bloquant] Deux stubs mis au vert hors des fichiers nommés par le plan

`files_modified` nomme `tests/test_comptes_droits.py` et `tests/test_magasin_acces.py`, donc
rien n'est hors périmètre — mais le plan ne mentionnait pas
`test_perm03_la_revocation_prend_effet_sans_reconnexion`, que `03-02-SUMMARY.md` attribue
pourtant nommément au plan 03-05. Il a été dépiné et implémenté : sans cela, le compte des
`pending` du plan aurait été faux et le stub serait resté orphelin. Sa version 03-05 affirme
la propriété qui rend la promesse vraie — `acces_pour` relit les lignes à chaque appel — parce
qu'un test de vue, qui construit une requête neuve, ne saurait pas distinguer un cache d'une
résolution.

## Notes pour les plans suivants

- **03-06** consomme `Acces.SCHEMA` et `_PorteurAcces`. `SCHEMA.magasins_ids` est **vide** et
  `pour_le_schema` est `True` : c'est la portée des lignes qui doit court-circuiter sur ce
  drapeau, `peut()` ne le lit pas et ne doit pas apprendre à le lire.
- **03-07** consomme `magasins_ids`. Le filtre va dans `get_queryset()`, jamais dans `list()`,
  et l'agrégat se prend **sur le queryset déjà filtré** — `peut()` ne peut rien pour un scalaire.
- **03-08** est le premier appelant sanctionné de `peut_quelque_part`. Marquer la ligne
  `# usage-sanctionne: peut_quelque_part navigation`, sans quoi la suite rougit. Le marqueur est
  accepté sur la ligne de l'appel ou sur l'une des deux qui la précèdent.
- **03-09** est le second : étiquette `catalogue`. Et il consomme `magasins_pour(code)` pour
  répondre « uniforme » ou « personnalisé » (`03-UI-SPEC.md` 7.5).
- **Phases 5 à 10** : `acces.peut(code, magasin_id=...)` est la forme par défaut. La forme sans
  magasin est une **conjonction** ; si le résultat surprend, c'est qu'elle a été prise pour une
  union. Voir la première section de ce document.
- `REQUIREMENTS.md` n'a **pas** été modifié : PERM-03 et PERM-04 sont réclamées par plusieurs
  plans de cette phase, et cocher ici dirait au verrou de phase que l'exigence est faite alors
  que la portée des lignes (03-07) et la surface d'octroi (03-09) n'existent pas.

## Known Stubs

Aucun. `acces.py` et `middleware.py` sont complets et testés ; rien dans ce plan ne rend une
valeur vide ou un texte d'attente vers une interface. Les six `pending` restants des deux
fichiers touchés appartiennent nommément aux plans 03-07 (portée liste/détail, écriture,
agrégat) et 03-09 (création de compte, octroi inter-client).

Une seule assertion est **différée par construction** et le dit dans sa propre docstring : le
nombre d'appelants de `peut_quelque_part` monte de 0 à 2 aux plans 03-08 et 03-09. Ce n'est
pas un stub — le garde est actif et refuse dès maintenant tout appelant non étiqueté.

## Self-Check: PASSED

Les deux fichiers créés sont présents sur le disque (`plateforme/comptes/acces.py`,
`plateforme/comptes/middleware.py`), les trois fichiers modifiés portent bien les
changements, et les deux commits existent dans `git log` : `8297dec` (tâche 1) et `86cf626`
(tâche 2), chacun nommant explicitement ses chemins (`git commit -F - -- <chemins>`, la forme
sûre en worktree partagé). Suite re-passée après le dernier commit : **135 passed, 30
deselected**.
