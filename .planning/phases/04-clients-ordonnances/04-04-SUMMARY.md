---
phase: 04-clients-ordonnances
plan: 04
subsystem: domain
tags: [ordonnance, decimal, checkconstraint, transposition, bornes, tenancy, openapi]

requires:
  - phase: 04-clients-ordonnances
    plan: 01
    provides: "le modèle `Client`, `FicheClientFactory`, le précédent d'un modèle délibérément non scopé au magasin"
  - phase: 04-clients-ordonnances
    plan: 03
    provides: "l'API fiche client, et la note disant que la garde positive de non-scoping revient à ce plan"
  - phase: 02-tenancy
    provides: "`BUSINESS_APPS`, le routeur fail-closed, `migrate_all`, les fixtures à deux locataires"
  - phase: 03-comptes-et-droits
    provides: "l'amorçage `/api/auth/moi/`, l'idiome de la garde de source par AST"
provides:
  - "l'application métier `domaine.ordonnances`, installée et classée"
  - "`BORNES` — l'unique endroit nommé des chiffres cliniques, chaque ligne sourcée"
  - "`canonicaliser_axe`, `transposer`, `snapshot_pour_fournisseur` — trois fonctions pures"
  - "le modèle `Ordonnance` : plat OD/OG, en `Decimal`, non scopé magasin mais porteur du magasin"
  - "25 `CheckConstraint` dérivées de `BORNES` + l'unicité `(client, version)`"
  - "`bornes_ordonnance` sur l'amorçage, en chaînes pour les décimaux"
  - "`OrdonnanceFactory` et ses trois traits délibérément invalides"
affects: [04-05-versionnement, 04-08-saisie-ordonnance, 05-stock, 08-achats-fournisseurs]

tech-stack:
  added: []
  patterns:
    - "Une contrainte de pas s'écrit `Q(Exact(Mod(F(champ), Value(pas)), Value(ZERO)))` — un `Lookup` est `conditional` dès que son `output_field` est booléen, donc il entre dans un `Q`"
    - "Une contrainte de bornes se génère par compréhension sur une table nommée ; les nombres ne sont jamais recopiés dans le modèle"
    - "Une garde de littéraux par AST exclut les mots-clés de forme (`max_digits`, `decimal_places`, `max_length`) : sans cette exclusion elle est inutilisable, avec elle elle reste stricte"
    - "Un test de refus par `bulk_create` s'écrit `with pytest.raises(IntegrityError), transaction.atomic(using=alias)` — `atomic` à l'intérieur, sinon la transaction du test reste cassée"
    - "Une valeur cross-base (un compte du plan de contrôle) se porte en chaîne, jamais en clé étrangère — même choix que `AccesMagasin.magasin_code`, dans l'autre sens"
    - "Un champ `read_only` est **toujours** `required` dans un schéma de sortie : une forme facultative se modélise par une classe, pas par `required=False`"

key-files:
  created:
    - domaine/ordonnances/__init__.py
    - domaine/ordonnances/apps.py
    - domaine/ordonnances/bornes.py
    - domaine/ordonnances/optique.py
    - domaine/ordonnances/models.py
    - domaine/ordonnances/migrations/0001_initial.py
    - tests/test_optique.py
    - tests/test_ordonnances.py
  modified:
    - config/settings/base.py
    - plateforme/tenancy/router.py
    - plateforme/comptes/serializers.py
    - tests/factories.py
    - web/src/api/schema.yml
    - web/src/api/types.gen.ts

key-decisions:
  - "Le ±20 de PITFALLS.md écrase le ±30 de la zone grise 1 — et **aucun des deux n'a de source normative**, ce qui est écrit dans la docstring de `bornes.py`"
  - "Aucune table de suivi de commande spéciale n'est créée : STOCK-08 (phase 5) possède ce cycle de vie. CLIENT-08 n'est pas cochée"
  - "`transposer` n'impose aucun signe au cylindre — c'est ce qui la rend réciproque ; le refus du signe est une règle de stockage, tenue par la base"
  - "`canonicaliser_axe` ne replie **pas** un axe hors plage : replier 400° en 40° changerait une faute de frappe en valeur plausible"
  - "`created_par` est une chaîne d'adresse, pas une clé étrangère : `allow_relation` refuse la relation entre le plan de contrôle et la base client"
  - "La garde des littéraux cliniques exclut `optique.py`, qui porte la géométrie (quart de tour, période de l'axe) et non des bornes révisables"
  - "Une classe de sérialiseur par forme de borne, parce qu'un `required=False` sur un champ `read_only` ne produit rien : le contrat aurait promis `convention` sur la sphère"

patterns-established:
  - "Une contrainte qu'une autre contrainte intercepte d'abord n'est pas éprouvée : le test du cylindre nul pose l'axe pour que sa propre contrainte soit celle qui refuse"
  - "Une sonde jetable qui imprime le **nom** de la contrainte violée, cas par cas, avant de déclarer une garantie tenue"

requirements-completed: []

duration: 40min
completed: 2026-09-18
---

# Phase 4 Plan 04 : Le domaine de l'ordonnance — Summary

**Le modèle de la prescription, ses chiffres cliniques à un seul endroit nommé et servis à la SPA, vingt-cinq contraintes de base dérivées de ce seul endroit — dont la seule qui attrape une classe d'erreur entière, l'axe exigé si et seulement si le cylindre est non nul — et la transposition minus-cyl ↔ plus-cyl en fonction pure, sans la table que la phase 5 possède.**

## Performance

- **Durée :** ~40 min (premier commit 16:47, dernier 16:56)
- **Tâches :** 3 / 3
- **Fichiers :** 14 (8 créés, 6 modifiés)
- **Vague parallèle :** exécuté en même temps que `04-07` dans le même worktree.
  `npm run build` **non lancé** (04-07 en est propriétaire), `state advance-plan`
  **non exécuté**, chemins nommés aux trois commits. Le commit `4ddd92d` de `04-07`
  s'est intercalé entre mes tâches 1 et 2 sans absorber aucun de mes fichiers, et
  aucun de mes trois commits ne porte de fichier sous `web/src/pages/` ni
  `web/src/champs/` — vérifié commit par commit.

## Les nombres relevés, pas devinés

| Porte | Avant | Après |
|---|---|---|
| `uv run pytest -q -m "not slow"` | **213 passed / 32 deselected** | **249 passed / 32 deselected** |
| `uv run pytest -q -m slow` | 32 passed | **32 passed, 0 failed** |
| `uv run python manage.py check` | 0 issue | **0 issue** |
| `makemigrations --check --dry-run` | code 0 | **code 0 — « No changes detected »** |
| `migrate_all --check` | `2 ok, 0 behind` (run #12) | **`2 ok, 0 behind` (run #15)** |
| `spectacular --fail-on-warn` + `diff -q` | 0, muet | **0, muet** |
| `npm --prefix web run build` | 0 | **non lancé — voir Déviations** |

`migrate_all --check` a d'abord rendu **`0 ok, 0 failed, 2 behind`** : la migration
`ordonnances=0001_initial` existait et les deux clients de développement ne l'avaient
pas. Après `migrate_all` : `2 ok, 0 behind`, et les deux portent désormais
`caisse=0001_initial, clients=0003_equivalence_nom, magasins=0001_initial,
ordonnances=0001_initial, stock=0001_initial`.

**Pour le tableau de comptage de `04-VALIDATION.md` §1 :**

| Plan | Tests écrits (`def`) | Emplacements neufs |
|---|---|---|
| 04-04 | **20** | **36** (36 dans la porte rapide, 0 dans `-m slow`) |

L'écart de 16 vient de trois paramétrages : la table de corrections de la réciprocité
(×6), les formes flottantes refusées (×4), les quatre cas de l'axe ↔ cylindre (×4), les
contrôles synthétiques des deux gardes (×4 et ×3), moins les `def` qui les portent.

Le plan nommait **quatorze** tests ; vingt ont été écrits. Les six de plus sont
énumérés et justifiés dans « Tests au-delà du plan » ci-dessous — aucun n'est du
remplissage, chacun ferme un trou constaté pendant l'écriture.

## Les rouges observés avant la tâche 2, un par un

Premier passage : **15 failed, 7 passed, 14 errors**.

| Test | Message d'échec observé |
|---|---|
| `test_client07_transposition_aller_retour_est_identite` (×6) | `ModuleNotFoundError: No module named 'domaine.ordonnances'` |
| `…la_transposition_suit_l_exemple_marocain_verifie` | idem |
| `…la_transposition_replie_l_axe_et_n_emet_jamais_zero` | idem |
| `…la_canonicalisation_de_l_axe_ne_replie_pas_une_faute_de_frappe` | idem |
| `…la_transposition_est_en_decimal_jamais_en_flottant` (×4) | idem |
| `…les_bornes_vivent_a_un_seul_endroit` | `AssertionError: la garde n'a trouvé aucun module à lire dans domaine/ordonnances/ ; une garde qui ne lit rien est verte pour toujours` — `assert 'models.py' in {}` |
| les 13 tests de `tests/test_ordonnances.py` avec base (×14 emplacements) | **ERREUR au setup**, pas échec : `LookupError: No installed app with label 'ordonnances'` |
| `test_client08_aucune_table_de_commande_speciale_n_est_creee` | `AssertionError: l'application ordonnances n'existe pas` — `assert []` |
| les 7 contrôles positifs synthétiques | **VERTS d'emblée** — voir ci-dessous |

### Deux détails du rouge qui valent d'être écrits

**1. Les quatorze rouges de `test_ordonnances.py` sont des *erreurs de setup*, pas des
échecs, et la cause n'est pas celle qu'on attend.** `LookupError: No installed app with
label 'ordonnances'` ne vient pas du corps du test : il vient de la fixture
`deux_magasins`, qui importe `tests/factories.py`, dont le corps de classe
`OrdonnanceFactory` résout `Meta.model = "ordonnances.Ordonnance"` **à la définition de
la classe**. Une chaîne de modèle dans une fabrique factory_boy n'est donc pas aussi
paresseuse qu'elle en a l'air : elle casse l'import du module entier, et donc tous les
tests qui importent une *autre* fabrique du même fichier. Bon à savoir avant la phase 5.

**2. Les sept contrôles positifs synthétiques étaient verts avant toute implémentation,
et c'est correct.** Les deux détecteurs — littéraux cliniques, dérivation d'un écart
pupillaire — sont des fonctions pures sur un AST ; ils n'attendent aucun code
applicatif. Leur valeur est ailleurs : ils rougissent le jour où quelqu'un « simplifie »
un détecteur au point qu'il n'attrape plus la faute qu'il décrit. Le quatrième cas de la
garde des bornes est le plus important de tout le fichier — une docstring qui **cite**
les bornes en toutes lettres ne doit pas être attrapée, et c'est la dixième occurrence
dans ce projet du critère qui attrape sa propre prose.

## Ce que le plan demandait de consigner

### 1. Le ±20 écrase le ±30, et ni l'un ni l'autre n'a de source

`04-CONTEXT.md` zone grise 1 proposait −30,00 .. +30,00 pour la sphère ;
`.planning/research/PITFALLS.md:449` dit −20,00 .. +20,00 ; D-4b a tranché pour le
second. **Ce plan applique donc le ±20 et écrase explicitement le ±30.**

Ce qui compte davantage que le nombre, et qui est écrit dans la docstring de
`bornes.py` plutôt que dans ce résumé seul : **aucun des deux n'a de source normative.**
`04-RESEARCH.md` §6.3 le dit franchement après avoir cherché. Le tableau de provenance
de `bornes.py` distingue en conséquence quatre lignes sourcées (sphère, cylindre, axe,
addition) de deux lignes marquées `JUGEMENT — sans source` (les deux écarts
pupillaires), parce que mélanger les deux natures sans le dire est ce qui produit, trois
phases plus tard, un refus qu'on n'ose plus toucher parce qu'on ne sait plus d'où il
vient.

### 2. La contradiction CLIENT-08 / STOCK-08

`04-RESEARCH.md` §3.4 et la zone grise 2 de `04-CONTEXT.md` demandaient tous deux une
table de commande spéciale rattachée à l'ordonnance et portant ses valeurs. **La feuille
de route donne le cycle de vie de la commande spéciale — commandé → prêt → client
prévenu → livré — à STOCK-08, phase 5.**

**Ce qui a été livré à la place :** `snapshot_pour_fournisseur(ordonnance)`, qui produit
la **copie figée en cylindre positif**, avec la convention en clair dans la charge, et
son test — y compris la moitié qui compte, à savoir qu'une correction saisie *après*
coup ne change pas un instantané déjà produit. C'est la décision de
`.planning/research/ARCHITECTURE.md:290` — la prescription est copiée, pas référencée —
et c'est la seule moitié de CLIENT-08 que la phase 4 peut honnêtement posséder.

**Pourquoi pas la table :** la poser ici préempterait le statut et les transitions que la
phase 5 doit dessiner, et la phase 5 devrait alors migrer une table qu'elle n'a pas
conçue. La répartition est donc : **phase 4** le producteur de la copie et son test,
**phase 5** la table et son cycle de vie, **phase 8** le branchement au bon de commande
fournisseur. **CLIENT-08 n'est cochée par aucune des trois** — une case cochée doit
vouloir dire « un opticien peut le faire ».

Une garde tient cette frontière : `test_client08_aucune_table_de_commande_speciale_n_est_creee`
lit les **définitions de classe** de l'application par AST, et non son texte. Le `grep`
du nom aurait attrapé la docstring d'`optique.py`, qui explique précisément pourquoi la
table n'est pas là — onzième occurrence évitée du critère qui attrape sa propre prose.

## Les mesures faites plutôt que recopiées

### Les vingt-six contraintes existent et refusent, une par une

Une sonde jetable a inséré par `bulk_create` une ligne fautive par règle et imprimé le
**nom de la contrainte violée**, parce que « la ligne a été refusée » ne dit pas *par
quoi* — et une contrainte interceptée par une autre est une contrainte non éprouvée :

```
sphere -40           -> ordonnance_sphere_od_dans_les_bornes
sphere -0.17         -> ordonnance_sphere_od_sur_la_grille
addition 0.50        -> ordonnance_addition_od_dans_les_bornes
axe 400              -> ordonnance_axe_od_dans_les_bornes
ep 6.0               -> ordonnance_ep_binoculaire_dans_les_bornes
ep 62.3              -> ordonnance_ep_binoculaire_sur_la_grille
cylindre +1.00       -> ordonnance_cylindre_od_dans_les_bornes
cylindre 0 avec axe  -> ordonnance_cylindre_od_non_nul_ou_absent
axe sans cylindre    -> ordonnance_axe_od_ssi_cylindre_od
prescripteur vide    -> ordonnance_prescripteur_ssi_source_medicale
prescripteur sur réfraction -> ordonnance_prescripteur_ssi_source_medicale
ordonnance saine     -> ACCEPTÉE
```

**Cette sonde a trouvé une faiblesse réelle dans mon propre test.** La première version
de `test_client07_un_cylindre_de_zero_est_stocke_null_et_l_axe_avec` posait un cylindre
de zéro **sans axe** — et c'est alors `ordonnance_axe_od_ssi_cylindre_od` qui refuse, la
contrainte croisée arrivant la première. `ordonnance_cylindre_od_non_nul_ou_absent`
serait restée verte sans jamais avoir été consultée, pendant deux ans, jusqu'au jour où
quelqu'un l'aurait supprimée en constatant qu'aucun test ne rougit. Le test pose
maintenant l'axe, et le commentaire dit pourquoi.

Deux remarques sur la forme des contraintes de bornes, mesurées :

- **`cylindre <= 0` n'est pas une contrainte séparée** : c'est la borne haute de
  `BORNES["cylindre"]`, donc la contrainte de bornes **est** la règle de signe. Écrire
  les deux aurait donné deux endroits à modifier le jour où la convention change.
- **Le pas n'a pas de contrainte sur l'axe**, et c'est écrit dans `BORNES_ENTIERES` : un
  modulo de un degré sur une colonne entière est toujours vrai, et une garantie vide se
  lit comme une protection.

### La forme d'une contrainte de pas, vérifiée contre le Django installé

`Q(Exact(Mod(F(champ), Value(pas)), Value(ZERO)))`. Elle tient parce que
`Lookup.conditional` est une **propriété** — `isinstance(self.output_field,
BooleanField)` dans Django 6.1.1, vérifié en lisant la source du dépôt — donc un
`Exact` entre dans un `Q` comme un enfant à part entière. Le SQL produit passe par
`MOD(numeric, numeric)`, et `NULL % 0.25` valant `NULL`, une colonne vide satisfait la
contrainte sans clause supplémentaire. La clause `isnull` explicite est conservée **pour
le lecteur**, pas pour la base.

### Un champ `read_only` est toujours `required` dans le schéma

Mesuré en régénérant `schema.yml` : `signe_obligatoire` et `convention`, déclarés
`required=False`, sont sortis **`required`** — drf-spectacular traite tout champ
`read_only` comme garanti en sortie. Le type TypeScript promettait donc `convention` sur
la sphère et `signe_obligatoire` sur le cylindre, deux clés que la charge utile ne porte
pas. Corrigé par **une classe de sérialiseur par forme** : `BorneSimple`, `BorneSphere`,
`BorneCylindre`, `BorneEntiere`. Le contrat généré est maintenant exact, et
`BorneDecimale` — la classe unique et menteuse — n'existe plus.

## Commits par tâche

1. **Tâche 1 — les tests nommés, rouges d'abord** — `fb01bf7` (test)
   `tests/test_optique.py`, `tests/test_ordonnances.py`, `tests/factories.py`
2. **Tâche 2 — l'application, `BORNES`, `optique.py`, le modèle et ses contraintes** —
   `21bf4f9` (feat)
   `config/settings/base.py`, `plateforme/tenancy/router.py`, `domaine/ordonnances/*`,
   plus les deux fichiers de test amendés (la sonde du cylindre nul)
3. **Tâche 3 — les bornes voyagent sur l'amorçage** — `7eb472b` (feat)
   `plateforme/comptes/serializers.py`, `web/src/api/schema.yml`,
   `web/src/api/types.gen.ts`

## Tests au-delà du plan — les six, et ce que chacun ferme

| Test | Pourquoi il existe |
|---|---|
| `…la_canonicalisation_de_l_axe_ne_replie_pas_une_faute_de_frappe` | Le plan décrivait `canonicaliser_axe` sans la tester directement. La règle qu'elle porte **en creux** — ne pas replier 400° en 40° — est plus dangereuse que celle qu'elle porte en clair, et rien ne la tenait |
| `…l_axe_zero_saisi_est_canonicalise_en_180` | CLIENT-07 dit littéralement « 0–180 ». Sans ce test, l'acceptation de 0 à la saisie n'est écrite nulle part et un relecteur la prendrait pour un bug en lisant la contrainte `1..180` |
| `…la_garde_des_bornes_est_prouvee_sur_des_modules_synthetiques` (×4) | Un détecteur jamais éprouvé sur un cas fautif est vert et vide. Le quatrième cas prouve qu'une docstring citant les bornes n'est **pas** attrapée |
| `…la_garde_de_l_ecart_pupillaire_est_prouvee_sur_des_modules_synthetiques` (×3) | Idem, et le troisième cas est un contrôle : la **somme** des monoculaires est la forme correcte et doit rester autorisée |
| `…aucune_table_de_commande_speciale_n_est_creee` | La frontière avec STOCK-08 était en prose dans le plan et dans une docstring. Une frontière de périmètre que rien ne tient se franchit à la phase suivante sans que personne le remarque |

## Décisions prises

1. **`transposer` n'impose aucun signe au cylindre.** C'est ce qui la rend réciproque, et
   la réciprocité est sa propriété testée. Le refus du cylindre positif est une règle de
   **stockage** ; l'imposer dans la fonction rendrait impossible le second aller,
   c'est-à-dire précisément l'usage — ramener dans la convention de stockage une valeur
   saisie en positif.

2. **`canonicaliser_axe` ne replie pas un axe hors plage.** L'arithmétique existe
   (`04-RESEARCH.md` §6.2) mais l'appliquer transformerait une faute de frappe en valeur
   plausible, ce que tout ce plan combat. Hors plage, la valeur passe intacte à la
   contrainte, qui la refuse et fait relire l'ordonnance.

3. **`created_par` est une chaîne d'adresse, pas une clé étrangère.** Les comptes vivent
   dans le plan de contrôle (CLAUDE.md #11) et `TenantRouter.allow_relation` refuse la
   relation ; c'est le même choix que `AccesMagasin.magasin_code`, dans l'autre sens. La
   chaîne reste lisible dix ans plus tard (art. 211 CGI), même compte désactivé.

4. **La garde des littéraux cliniques exclut `optique.py`**, qui porte le quart de tour
   et la période de l'axe. Ce sont des constantes **géométriques** : elles ne changent
   pas quand le propriétaire change d'avis sur ce qu'un opticien peut taper, et les faire
   passer par `BORNES` mélangerait une mathématique avec un jugement révisable. La
   distinction est écrite dans la garde elle-même.

5. **La garde exclut aussi les mots-clés de forme** (`max_digits`, `decimal_places`,
   `max_length`). Sans cette exclusion, `DecimalField(max_digits=4, decimal_places=1)`
   déclenche sur `4` (l'addition maximale) et sur `1` (l'axe minimal), et la garde serait
   désactivée dans la semaine. Avec, elle reste stricte : tout autre littéral numérique
   qui recopie une valeur de `BORNES` — y compris écrit en chaîne, forme normale d'un
   `Decimal` — est refusé.

6. **`save()` canonicalise, la contrainte refuse, et les deux ne font pas double emploi.**
   `save()` **accepte et range** une saisie légitime que la contrainte refuserait (un axe
   de 0, un cylindre de 0) ; la contrainte **refuse** ce qu'aucun chemin ne doit écrire.
   Les tests tiennent les deux moitiés séparément.

7. **L'immuabilité n'est pas imposée dans `save()`.** La décision Q5 du propriétaire
   autorise explicitement la photo à passer de `null` à posée sur une version existante,
   donc un refus global d'écriture la contredirait. L'immuabilité est tenue par l'absence
   de route de modification, qui est le périmètre du plan 04-05.

## Déviations du plan

### 1. [Décision d'exécution] `npm --prefix web run build` n'a pas été lancé

Le plan l'exige dans la tâche 3. La contrainte d'exécution ajoutée à
`04-VALIDATION.md` le 2026-09-18 dit l'inverse pour une vague parallèle : `tsc -b` écrit
un `.tsbuildinfo` partagé et `vite build` un `dist/` partagé, aucun n'est cloisonné par
plan, et **`04-07` en est propriétaire dans cette vague**. La consigne d'orchestration
reprenait la même règle. Le build reste donc à lancer par `04-07` ou par
l'orchestrateur en fin de vague ; `schema.yml` et `types.gen.ts` sont régénérés et
committés, donc la seule chose que le build ajouterait est la vérification de typage du
client généré.

**Ce qui a été fait à la place :** `npm --prefix web run api:types` (qui n'invoque pas
`tsc`) puis relecture directe de `types.gen.ts` — `Amorcage` porte bien
`readonly bornes_ordonnance: components["schemas"]["BornesCliniques"]`, et les bornes
décimales y sont typées `string`.

### 2. [Écart mineur] `plateforme/comptes/views.py` n'a pas été modifié

Le plan le liste dans `files_modified`. Il n'y avait rien à y changer :
`charge_utile_moi` vit dans `serializers.py`, et `_amorcage` de `views.py` l'appelle
sans connaître ses clés. Ajouter la clé au seul endroit qui la construit suffit, et
toucher `views.py` pour respecter la liste aurait été du bruit.

### 3. [Correction de test] Le refus du cylindre nul n'éprouvait pas sa contrainte

Décrit en détail dans « Les mesures faites plutôt que recopiées » ci-dessus. Trouvé par
la sonde, corrigé dans le commit de la tâche 2, avec le raisonnement en commentaire
au-dessus de l'assertion.

### 4. [Choix de forme, contre la lettre du plan] Quatre sérialiseurs de bornes au lieu d'un

Le plan écrivait une unique `BornesCliniquesSerializer` avec des sous-champs
facultatifs. Mesuré : un champ `read_only` est toujours `required` en sortie, donc le
contrat aurait menti sur deux clés. Corrigé par une classe par forme.

---

**Total des déviations :** 1 décision d'exécution (le build, imposée par la discipline de
vague), 1 écart mineur de périmètre, 2 corrections trouvées à l'exécution.
**Effet sur le périmètre :** aucun élargissement. Aucune table `CommandeSpeciale`, aucune
route, aucun sérialiseur d'ordonnance — les trois appartiennent aux plans 04-05 et 05.

## Problèmes rencontrés

- **La migration générée est une seule ligne de 12 000 caractères.** `makemigrations`
  sérialise les vingt-six contraintes dans le `options` de `CreateModel`, sans retour à
  la ligne. Elle est correcte et illisible. Non reformatée : un fichier de migration
  réécrit à la main est un fichier qu'une regénération future contredira, et le contenu
  est de toute façon dérivé de `BORNES`, qui est lisible.
- **`LookupError` au lieu de `ModuleNotFoundError` sur les tests à base.** Décrit
  ci-dessus : une chaîne `Meta.model` de factory_boy se résout à la définition de la
  classe, donc une fabrique cassée casse l'import de tout le fichier de fabriques.

## Configuration utilisateur requise

Aucune. `migrate_all` a été lancé et les deux clients de développement portent la
nouvelle table.

## État pour la suite

**Prêt :**

- **`04-05` (versionnement)** trouve `Ordonnance` avec `version`, `supersede`,
  `type_revision` et `motif_revision` déjà en colonnes, l'unicité `(client, version)` en
  base, et `OrdonnanceFactory`. Il lui reste l'émission de la version **sous verrou** et
  la surface en lecture/création seule.
- **`04-08` (saisie)** trouve `bornes_ordonnance` sur `/api/auth/moi/`, en chaînes pour
  les décimaux et en entiers pour l'axe, et `transposer` côté serveur pour la bascule
  « saisir en cylindre positif ».
- **Phase 5 (STOCK-08)** trouve `snapshot_pour_fournisseur` et la place laissée libre
  pour sa table.

**À ne pas manquer :**

- **La garde positive de non-scoping est la seule protection de D-4a.**
  `vues_sans_portee_magasin` est structurellement aveugle ici. Si un plan ultérieur fait
  hériter `Ordonnance` de `MagasinScopedModel`, tout le reste de la suite reste vert.
- **Le sérialiseur d'ordonnance du plan 04-05 doit lire `BORNES`**, jamais recopier un
  nombre : la garde AST scanne déjà `domaine/ordonnances/serializers.py` s'il existe, et
  rougira au premier littéral.
- **Ne pas ajouter de contrainte de pas sur l'axe** en constatant qu'elle manque : elle
  serait toujours vraie. La raison est dans `BORNES_ENTIERES`.
- **`ep_saisi` ne se déduit pas** et aucun monoculaire ne se calcule : une garde AST le
  tient sur tout `plateforme/` et `domaine/`.

**Non coché, délibérément :** aucune exigence n'est marquée complète par ce plan.
CLIENT-03, CLIENT-04, CLIENT-05 et CLIENT-07 ont ici leur moitié serveur ; leur moitié
comptoir est le plan 04-08, et le projet tient le précédent des plans 03-05 à 03-10 —
une exigence n'est cochée que par le plan où un opticien peut réellement l'accomplir.
CLIENT-08 n'est pas cochable en phase 4 du tout (décision Q2 du propriétaire), et ne
doit **pas** être déplacée dans `REQUIREMENTS.md`. C'est `04-09` qui coche.

---
*Phase : 04-clients-ordonnances*
*Terminé : 2026-09-18*

## Self-Check: PASSED

Les quinze fichiers annoncés existent sur le disque et les trois commits `fb01bf7`,
`21bf4f9` et `7eb472b` existent dans l'historique. Deux affirmations vérifiées plutôt
que supposées :

- **Le décompte de tests.** `grep -c '^def test_'` rend **7** dans `tests/test_optique.py`
  et **13** dans `tests/test_ordonnances.py`, soit les 20 `def` annoncés ; et
  `pytest --collect-only` sur les deux fichiers rend **36 tests collected**, soit
  exactement le delta 213 → 249 de la porte rapide.
- **Le nombre de contraintes.** `len(Ordonnance._meta.constraints)` rend **26** :
  25 `CheckConstraint` — 20 de bornes et de pas, 4 croisées, 1 de prescripteur — plus
  l'unicité `(client, version)`. La migration en porte le même nombre.

Aucun de mes trois commits ne touche un fichier sous `web/src/pages/` ni
`web/src/champs/`, vérifié commit par commit.
