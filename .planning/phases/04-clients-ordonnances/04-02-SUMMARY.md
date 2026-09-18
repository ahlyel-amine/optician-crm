---
phase: 04-clients-ordonnances
plan: 02
subsystem: ui
tags: [react, typescript, vitest, shadcn, accessibilite, formats, saisie]

requires:
  - phase: 03-comptes-permissions-app-shell
    provides: "src/format/ (montant, date), le baril de formats, l'audit anti-locale, les blocs shadcn input/label, les cinq etats globaux"
provides:
  - "formaterTelephone — le troisieme format du produit, U+00A0 entre les paires, verbatim sur l'inconnu"
  - "src/champs/nombres.ts — normalisation, bornes et pas en fonctions pures, parametres, arithmetique entiere"
  - "src/champs/dates.ts — masque, regle de siecle parametree, ISO en transport seulement"
  - "ChampDate — le masque jj/mm/aaaa sans calendrier, vrai label, normalisation au blur"
  - "ChampNombre — saisie textuelle au clavier decimal, aria-invalid sur le refus et jamais sur l'avertissement"
  - "web/tests/nomAccessible.ts — la mesure du nom accessible, partagee par la phase"
  - "les blocs shadcn radio-group, textarea et alert"
affects: [04-07, 04-08, 04-09, 06-facturation, 11-mobile]

tech-stack:
  added: ["dom-accessibility-api 0.5.16 (devDependency, version deja installee)", "shadcn radio-group, textarea, alert"]
  patterns:
    - "Un format du produit vit dans src/format/ et nulle part ailleurs — le telephone rejoint le montant et la date"
    - "La logique de saisie vit dans des modules PURS, testes sans rendu ; le composant n'appelle que des fonctions"
    - "Les valeurs cliniques sont des ARGUMENTS : ni borne, ni pas, ni nombre dans web/src/"
    - "Les copies d'ecran sont des constantes de module nommees a cote du module, jamais dans etats/messages.ts"
    - "Une revendication de visibilite dans jsdom est une assertion de CLASSE ou d'ATTRIBUT, et son intitule le dit"

key-files:
  created:
    - web/src/format/telephone.ts
    - web/src/champs/nombres.ts
    - web/src/champs/dates.ts
    - web/src/champs/ChampDate.tsx
    - web/src/champs/ChampNombre.tsx
    - web/tests/champs.test.tsx
    - web/tests/nomAccessible.ts
    - web/src/components/ui/radio-group.tsx
    - web/src/components/ui/textarea.tsx
    - web/src/components/ui/alert.tsx
  modified:
    - web/src/format/index.ts
    - web/tests/format.test.ts
    - web/package.json
    - web/tsconfig.test.json

key-decisions:
  - "04-UI-SPEC.md 15.4 renverse partiellement 03-UI-SPEC.md 8.2 : le masque est livre, le calendrier ne l'est pas. La question 28-Q3 reste OUVERTE et le renversement est additif"
  - "normaliserNombre refuse une saisie plus precise que le champ au lieu de la tronquer — meme regle que le pas : jamais d'arrondi silencieux"
  - "Un signe contraire a la convention est refuse, jamais retourne en silence"
  - "Les comparaisons de bornes et de pas passent par BigInt sur les chiffres mis a la meme echelle, jamais par un flottant"
  - "dom-accessibility-api est fige a 0.5.16, la version DEJA dans l'arbre ; sa carte exports ne declare pas ses types, donc la declaration est designee par un paths du seul projet de test"

patterns-established:
  - "Chargement paresseux par import.meta.glob dans les suites : un module absent rend un echec lisible au lieu d'emporter la collecte du fichier"
  - "Un outil de test se prouve dans les DEUX sens dans le meme it — un controle positif et un negatif"

requirements-completed: []

duration: 22min
completed: 2026-09-18
---

# Phase 4 Plan 02 : Les primitives d'interface — Résumé

**Un troisième formateur (`formaterTelephone`, U+00A0 entre les paires, verbatim sur l'inconnu), deux champs de saisie adossés à quatre fonctions pures sans un seul nombre clinique, trois blocs shadcn, et la mesure `computeAccessibleName` qui transforme le manquement D-1 en assertion.**

## Performance

- **Durée :** ~22 min
- **Débuté :** 2026-09-18T14:53Z
- **Terminé :** 2026-09-18T15:15Z
- **Tâches :** 3
- **Fichiers touchés :** 14 (tous sous `web/`)

## Décompte des tests — écrit vs emplacements neufs

La phase 03.1 s'est trompée deux fois pour avoir confondu les deux. Ici ils coïncident,
et c'est dit plutôt que supposé : **aucun `it.each` n'a été ajouté**, donc un `it` écrit
vaut exactement un emplacement.

| Moment | Fichiers | Tests | Échecs |
|---|---|---|---|
| Ligne de base mesurée | 6 | **133** | 0 |
| Après la tâche 1 (rouge attendu) | 7 | 148 | **15** |
| Après la tâche 2 | 7 | 148 | 3 |
| Fin de plan | **7** | **149** | **0** |

- **16 `it` écrits**, 16 emplacements neufs : 4 (téléphone) + 4 (nombres) + 4 (dates) + 1 (`ChampDate`) + 2 (`ChampNombre`) + 1 (`nomAccessible`, ajouté en tâche 3).
- `133 + 16 = 149`. Le décompte ferme.
- `npm --prefix web run build` : **sortie 0** (`tsc -b`, `tsc -p tsconfig.test.json`, `vite build`). L'avertissement de taille de paquet est antérieur à ce plan.
- `npm --prefix web run audit:format` : **sortie 0**, silencieux.
- `pytest` n'a **pas** été exécuté : le socle backend changeait sous le plan, en vague parallèle.

## Le rouge observé, et ce que chaque test attrape

Le message d'échec exact, avant la tâche 2 :

    Error: src/format/telephone.ts n'existe pas encore — il est ecrit par le plan
    qui le livre. Modules trouves : ["../src/format/date.ts",
    "../src/format/index.ts","../src/format/montant.ts"]

    Error: src/champs/nombres.ts n'existe pas encore. Modules trouves : []

**Pourquoi c'était rouge :** les modules n'existaient pas, et le chargement paresseux
par `import.meta.glob` l'a dit en une phrase au lieu de faire échouer la transformation
du fichier. C'est ce qui a permis à la tâche 2 de virer au vert **par moitié** — 145 verts,
3 rouges, exactement les trois tests de rendu qui attendaient la tâche 3.

Ce que les tests attrapent, ligne par ligne :

| Test | Ce qu'il attrape |
|---|---|
| `rend un numero marocain par paires…` | Un U+00A0 dégénéré en espace ordinaire — invisible à l'œil, invisible à jsdom, et le numéro se coupe en fin de ligne au milieu d'une paire. L'assertion porte sur les **points de code** |
| `rend verbatim ce qu'il ne reconnait pas` | Un formateur qui lèverait sur une fiche importée d'un tableur mettrait la **liste entière** en erreur (T-04-12, accepté) |
| `ne consulte aucune locale` | La réécriture « simplifiée » par `Intl`. `Intl` est **piégé** pendant l'appel : toute consultation lève |
| `refuse un pas hors grille, et n_arrondit jamais` | L'assertion **jumelle** exclut une implémentation qui refuserait tout ; l'assertion sur la valeur inchangée exclut l'arrondi silencieux (T-04-07) |
| `le pas et les bornes sont des arguments` | Une constante clinique glissée dans le module : les deux verdicts deviendraient identiques (T-04-10) |
| `complete au blur` | Une règle de siècle adossée à `new Date()` — rouge un 1er janvier (T-04-11). L'année est un argument, et le test en passe **deux** différentes |
| `insere le slash apres le deuxieme et le quatrieme chiffre…` | Le masque naïf qui mutile la saisie de qui tape lui-même ses slashes. **Ce test a trouvé un vrai bug** — voir déviation 3 |
| `n_est jamais type=number` | Les molettes, le défilement qui change la valeur, `valueAsNumber = NaN` sur une virgule française (T-04-08). Assertion d'**attribut** |
| `un avertissement ne porte pas aria-invalid et n_est pas role=alert` | L'attribut qui rendrait un avertissement indiscernable d'un refus **pour exactement l'utilisateur qui ne voit pas la couleur** (T-04-09) |
| `mesure un nom vide sur un combobox sans etiquette et un nom non vide avec` | Un outil de mesure qui rendrait toujours la chaîne vide — le contrôle positif et le négatif sont dans le **même** `it` |

## Commits par tâche

1. **Tâche 1 — les tests, rouges d'abord** : `17b3519` (test)
2. **Tâche 2 — le formateur et les deux modules purs** : `c5baa9e` (feat)
3. **Tâche 3 — les deux champs, trois blocs shadcn, la mesure** : `235b6eb` (feat)

Chemins nommés à chaque commit, conformément à la discipline de vague parallèle.
`2262149` (plan 04-01) s'est intercalé entre les commits 2 et 3 **sans mélange** :
`git show --stat 235b6eb` ne porte que des fichiers sous `web/`.

## Fichiers créés / modifiés

- `web/src/format/telephone.ts` — trois formes, U+00A0, aucune locale, verbatim sur l'inconnu
- `web/src/format/index.ts` — le baril réexporte `formaterTelephone` et `SEPARATEUR_PAIRES`
- `web/src/champs/nombres.ts` — `normaliserNombre`, `fauteDeSigne`, `verifierBornes`, `verifierPas`, les gabarits de refus ; **aucun nombre clinique**
- `web/src/champs/dates.ts` — `masquerDate`, `normaliserDate`, `versISO`, `depuisISO`, `estDansLeFutur`
- `web/src/champs/ChampDate.tsx` — masque, vrai label, normalisation au blur, refus de futur **paramétré**
- `web/src/champs/ChampNombre.tsx` — saisie textuelle au clavier décimal, suffixe hors de l'entrée et `aria-hidden`
- `web/src/components/ui/{radio-group,textarea,alert}.tsx` — CLI shadcn, preset inchangé
- `web/tests/champs.test.tsx`, `web/tests/format.test.ts`, `web/tests/nomAccessible.ts`
- `web/package.json`, `web/package-lock.json`, `web/tsconfig.test.json`

## Décisions prises

- **`04-UI-SPEC.md` §15.4 renverse partiellement `03` §8.2** — le masque est livré, le calendrier ne l'est pas. Le renversement est **signalé, pas enterré** : il est écrit dans la docstring de `ChampDate.tsx`, avec sa raison (neuf frappes contre quatre clics et un défilement mois par mois ; et un calendrier importe `react-day-picker`, `date-fns` et une surface de locale dans un produit qui épingle ses formats précisément pour les tenir hors du chemin de décision). **La question ouverte §28-Q3 reste OUVERTE** : si le propriétaire veut le calendrier, il est additif et le masque reste le contrôle primaire.
- **`normaliserNombre` refuse une saisie plus précise que le champ** plutôt que de la tronquer. Même règle que le pas : un nombre tronqué est un nombre faux sans message.
- **Un signe contraire à la convention est refusé, jamais retourné en silence.** `fauteDeSigne` rend la phrase exacte de §23 correspondante, écrite une seule fois dans le produit.
- **`SEPARATEUR_DECIMAL` est importé de `@/format`** au lieu d'être redéfini : une seule virgule décimale dans la SPA.
- **Le bloc `alert` vendu par shadcn code en dur `role="alert"`** — il n'est donc **pas** le conteneur d'un avertissement (§16.4, §27). La note d'avertissement de `ChampNombre` est un `<p role="status">` écrit à la main.
- **Aucune exigence n'est cochée.** CLIENT-01/03/04 sont dans l'en-tête du plan, mais ce plan ne rend aucun écran : aucun opticien ne peut rien accomplir avec ces primitives seules. C'est le précédent que les plans 03-05 à 03-10 ont tenu, et que §28-Q2 réaffirme.

## Écarts au plan

### Corrections automatiques

**1. [Règle 3 — Bloquant] La commande de relevé de version prescrite par le plan échoue**
- **Trouvé pendant :** tâche 3
- **Problème :** `node -p "require('dom-accessibility-api/package.json').version"` lève `ERR_PACKAGE_PATH_NOT_EXPORTED` — la carte `exports` du paquet n'expose pas son propre `package.json`
- **Correction :** version lue par `node:fs` sur `node_modules/dom-accessibility-api/package.json`, **recoupée** avec l'entrée du `package-lock.json`. Les deux disent **0.5.16**. La règle du plan est respectée : la version est **relevée dans l'arbre installé, jamais devinée**
- **Vérification :** `npm install --save-dev --save-exact dom-accessibility-api@0.5.16` n'ajoute qu'une ligne au `package.json` et une au `package-lock.json`

**2. [Règle 3 — Bloquant] `TS7016` sur un paquet pourtant typé**
- **Trouvé pendant :** tâche 3, au `npm run build`
- **Problème :** `dom-accessibility-api@0.5.16` **expédie** `dist/index.d.ts`, mais sa carte `exports` ne déclare aucune condition `types`, et `moduleResolution: bundler` la respecte. `tsc -p tsconfig.test.json` échoue. Prendre une version plus récente (0.7.1) contournerait le problème mais **dupliquerait la bibliothèque dans l'arbre**, `@testing-library/dom` exigeant `^0.5.9`
- **Correction :** une entrée `paths` dans `tsconfig.test.json` — **le seul projet qui l'utilise** — désigne la déclaration expédiée. La raison est écrite dans le fichier
- **Fichiers :** `web/tsconfig.test.json` (**hors de la liste `files_modified` du plan**)
- **Vérification :** `npm run build` sort à 0

**3. [Règle 1 — Bogue] `masquerDate` perdait le premier chiffre de l'année**
- **Trouvé pendant :** tâche 3, par le test de frappe chiffre à chiffre
- **Problème :** un segment plein ne débordait pas sur le suivant. `14/09` puis la frappe `2` rendait `14/09` — **le chiffre disparaissait sous les doigts de l'opticien**
- **Correction :** les chiffres cascadent d'un segment plein vers le suivant, ce qui unifie du même coup les deux branches de la fonction
- **Vérification :** `14092026` frappé chiffre à chiffre rend `14/09/2026` ; `14/9/2026` reste intact
- **Ce que cela dit du test :** une seule frappe de la chaîne complète n'aurait **jamais** vu ce bogue. C'est la raison d'être de la frappe simulée touche par touche
- **Commit :** `235b6eb`

**4. [Règle 1 — Bogue d'outillage] Les séquences d'échappement Unicode se sont muées en caractères littéraux**
- **Trouvé pendant :** tâche 2, en exécutant la garde `grep -q 'u2212'`
- **Problème :** le chemin d'écriture par document en ligne a converti chaque séquence « backslash-u-XXXX » en son caractère. `SEPARATEUR_PAIRES`, `SIGNE_MOINS`, deux classes de caractères d'expression régulière **et trois assertions de test** portaient donc un U+00A0 ou un U+2212 **littéral et invisible**
- **Pourquoi cela compte ici plus qu'ailleurs :** un U+00A0 littéral dans une assertion est exactement le mode de défaillance que ce projet nomme depuis la phase 3 — il se lit comme une espace ordinaire et personne ne le voit en relecture
- **Correction :** réécriture en séquences d'échappement dans les cinq fichiers concernés, en laissant les caractères littéraux là où ils sont lisibles (prose française d'un commentaire)
- **Vérification :** `grep -P '[\x{00a0}\x{2212}]'` ne trouve plus qu'une occurrence, dans un commentaire ; `grep -q 'u2212' web/src/champs/nombres.ts` passe ; les 149 tests passent
- **Commit :** `c5baa9e`

### Ajouts au titre de la règle 2

**5. [Règle 2 — Registre des menaces] Le test nommé de l'avertissement**
- La tâche 1 ne listait, pour `ChampNombre`, que l'assertion de type. Or **T-04-09 est `mitigate` dans le registre de ce plan**, et §25.1 nomme le test. Ajouté : `un avertissement ne porte pas aria-invalid et n_est pas role=alert`, avec les quatre assertions d'attribut (`role="status"`, présence dans `aria-describedby`, absence d'`aria-invalid`, absence de tout `role="alert"`)

**6. [Règle 2] Le test pur de `masquerDate`**
- Non demandé par le plan. Ajouté parce que le masque est la seule partie de `ChampDate` qui décide quelque chose. **C'est lui qui a trouvé l'écart 3**

**7. [Règle 2] `fauteDeSigne` dans `nombres.ts`**
- `normaliserNombre` rend `null` pour plusieurs raisons. Sans cette fonction, chaque écran rededuirait laquelle, et les deux phrases de §23 seraient recopiées. Elles sont écrites **une** fois

### Ajustements de signature

**8.** Le plan décrit `ReglesNombre` avec `signe` obligatoire, puis appelle `normaliserNombre("31.5", {decimales: 1})` dans son propre texte de test. `signe` est donc **optionnel**, de défaut `aucun`. De même, `verifierBornes` prend `BornesMinMax` (`{min, max}`) — la forme que le plan lui passe — plus une `PresentationBornes` optionnelle qui porte le sujet et le rendu des bornes. C'est ce qui permet au gabarit de refus de **ne contenir aucun chiffre** tout en produisant les quatre phrases exactes de §23, dont trois rendent leurs bornes différemment.

**9.** Une ligne de clarté dans `web/tests/format.test.ts` : le message du chargeur nommait « le plan 03-11 » pour n'importe quel module absent, ce qui était faux dès le premier module de la phase 4.

---

**Total des écarts :** 4 corrections automatiques (2 bloquantes, 2 bogues), 3 ajouts règle 2, 2 ajustements de signature.
**Effet sur le plan :** aucun dépassement de périmètre. Rien hors de `web/`, aucun fichier sous `web/src/pages/`, aucune route, aucun appel d'API.

## Problèmes rencontrés

- Le préfixe `timeout` n'existe pas sur macOS ; le CLI shadcn a été lancé sans lui.
- Le CLI shadcn a créé les trois blocs **sans toucher** `package.json` : `radix-ui` 1.6.7 était déjà installé et porte `RadioGroup`.

## Vérifications manuelles

**Ce plan n'en ajoute aucune.** Les cinq de §25.5 portent sur des écrans, qui appartiennent aux plans 04-07 à 04-09. Le solde de 18 vérifications ouvertes de la phase 3 est inchangé.

## Ce qui reste ouvert, et pour qui

- **§28-Q3 reste ouverte** : pas de sélecteur de calendrier. Additif le jour où quelqu'un le veut.
- **D-1 n'est pas corrigé** — hors périmètre, ce n'est pas le fichier de cette phase. La mesure est posée : `attendUnNomAccessible(element)` rend désormais un échec qui **nomme le piège** au lieu de dire « attendu non vide ». Aucun nouveau `combobox` sans nom n'a été introduit ; le seul de ce plan vit dans un test et sert de contrôle négatif.
- **Les bornes ne sont nulle part dans `web/src/`.** Elles arrivent au plan 04-04 ; la garde CI complète sur `web/src/pages/clients/` est posée au plan 04-08, où ce répertoire existera.
- Les plans 04-07, 04-08 et 04-09 importent `ChampDate`, `ChampNombre` et `tests/nomAccessible.ts` tels quels. La grille OD/OG passe `labelMasque` et une des largeurs fixes de §17.1.

## Stubs connus

Aucun. Aucune valeur vide codée en dur, aucun texte d'attente, aucun composant sans source de données — ce plan ne rend aucun écran.

## Configuration utilisateur requise

Aucune.

---
*Phase : 04-clients-ordonnances · Plan 02*
*Terminé : 2026-09-18*

## Self-Check: PASSED

Les dix fichiers annoncés existent sur le disque ; les trois empreintes de commit
(`17b3519`, `c5baa9e`, `235b6eb`) existent dans l'historique ; `npm --prefix web test`
rend 149 verts sur 7 fichiers, `run build` sort à 0 et `run audit:format` est silencieux.

## Note de vague parallèle — attribution du commit de métadonnées

`.planning/STATE.md` est partagé avec le plan 04-01, qui tourne en même temps sur le même
index. Le commit de métadonnées de ce plan porte donc, **en plus** de sa ligne de métrique
et du recalcul de la barre d'avancement, une réécriture des champs `stopped_at` et
`last_updated` que **ce plan n'a pas faite** : elle vient de 04-01. L'historique n'est pas
réécrit pour le corriger — la correspondance est consignée ici, comme CLAUDE.md le demande.

`state advance-plan` n'a **pas** été exécuté : deux agents incrémentant un compteur le
laissent faux. L'avancement est recalculé depuis les résumés présents sur le disque.
