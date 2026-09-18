---
phase: 04-clients-ordonnances
type: context
status: accepted-by-default — le propriétaire a dit « continue » sans corriger
created: 2026-09-17
---

# Contexte de la phase 4 — Clients & Ordonnances

> **Statut : ACCEPTÉ PAR DÉFAUT, pas ratifié.** Les quatre zones grises ont été présentées
> au propriétaire le 2026-09-17. Il n'y a pas répondu, puis a dit « continue » — ce qui est
> lu comme *avance sur tes recommandations*, et non comme *je les ai lues et approuvées*.
> La distinction est écrite parce qu'elle change ce qu'on peut affirmer plus tard.
>
> **Un plan les applique en les NOMMANT**, de sorte qu'un désaccord se voie et coûte un mot.
> Aucune ne doit être enterrée dans une ligne de code sans trace.
>
> **La plus chère à corriger tard est la convention de signe du cylindre** (zone grise 1) :
> elle est dans le modèle, pas dans l'affichage. Le plan qui la pose doit la mettre à un
> endroit unique et nommé, et l'écran de saisie doit la dire à l'utilisateur, pour qu'une
> erreur se voie au premier essai plutôt qu'à la première paire de verres fausse.
>
> Ce qui est écrit sous « Acquis » l'est réellement : cela vient du dépôt, de la feuille de
> route ou des phases déjà livrées.

## Acquis — ce que la phase hérite et ne rediscute pas

- `domaine/` porte déjà `magasins`, `stock`, `caisse`. La phase 4 ajoute ses applications
  métier et **chacune doit entrer dans `BUSINESS_APPS` de `plateforme/tenancy/router.py`
  dans le même commit** — une application non classée fait échouer `manage.py check` avec
  `tenancy.E001`, ce qui est voulu (Pitfall 12).
- La couche de projection existe et **`CHAMPS_PROTEGES` est encore vide**. Le plan 03-06
  désignait la phase 8 comme celle qui la remplirait. **C'est probablement faux : les
  ordonnances arrivent maintenant.** Voir zone grise 5.
- Les droits `ordonnance.voir` et `ordonnance.saisir` existent déjà au catalogue depuis la
  phase 3, avec leur explication : « une donnée de santé. À n'accorder qu'aux personnes qui
  en ont besoin. »
- Toute nouvelle `APIView` porte son `@extend_schema` dans le plan qui la crée, et tout
  changement de vue, sérialiseur ou route régénère `web/src/api/schema.yml` **et** le client
  TypeScript dans le même commit.
- Tout nouveau paramètre de requête entre dans `PARAMETRES_RESERVES` dans le même commit.
- `MagasinScopedViewSet` s'hérite **en première position** ; la garde vérifie l'ordre du MRO.

## Zone grise 1 — les règles cliniques de l'ordonnance (CLIENT-03, CLIENT-07)

**Ce qu'il faut trancher :** la convention de signe du cylindre, les bornes admises, et la
forme de l'écart pupillaire.

**Recommandation.**

| Champ | Proposition | Raison |
|---|---|---|
| Convention du cylindre | **cylindre négatif** (« minus-cyl »), refusé si positif | C'est la convention de prescription dominante en France et au Maroc. **Les deux ne sont pas interchangeables** : la même correction s'écrit `+2,00 −1,00 × 90` ou `+1,00 +1,00 × 180`. Accepter les deux sans le dire produit des verres faux. |
| Axe | entier, **0–180** inclus | Déjà écrit dans CLIENT-07. Au-delà de 180 l'axe se replie, il ne s'étend pas. |
| Sphère | **−30,00 à +30,00**, pas de 0,25 | Couvre tout ce qu'un opticien voit ; hors de là c'est une faute de saisie. |
| Cylindre | **−10,00 à 0**, pas de 0,25 | Idem. |
| Addition | **+0,50 à +4,00**, pas de 0,25 | Une addition hors de cette plage n'existe pas en pratique. |
| Écart pupillaire | **les deux formes, explicitement distinguées** | CLIENT-07 l'exige déjà : « monocular and binocular EP distinguished ». Le monoculaire (par œil) est nécessaire aux progressifs ; beaucoup d'ordonnances marocaines ne donnent que le binoculaire. Stocker **laquelle a été saisie**, et ne jamais dériver l'une de l'autre en silence. |

**Le mode de défaillance à concevoir contre** n'est pas une valeur hors bornes — c'est une
valeur **plausible et fausse**. Un axe de 90 saisi pour 9 passe toutes les bornes. La
validation attrape l'impossible ; elle n'attrape pas la faute de frappe crédible. D'où
l'importance de CLIENT-06 : la version précédente reste lisible, donc l'erreur est
rattrapable.

**Si le propriétaire dit le contraire** — notamment si le cylindre positif doit être accepté
— c'est un changement de modèle, pas d'affichage : il faut alors stocker la convention avec
la valeur, et toute lecture ultérieure doit la consulter.

## Zone grise 2 — CLIENT-08 ne peut pas être satisfaite dans cette phase

**Ce n'est pas une question, c'est un conflit de périmètre.**

CLIENT-08 : « A commande spéciale carries its ordonnance values through to the fournisseur
order. » Or **les fournisseurs et les bons de commande sont la phase 8.** Le destinataire
n'existe pas.

**Recommandation : la phase 4 construit la moitié qu'elle peut, et CLIENT-08 reste ouverte
jusqu'à la phase 8**, où elle est vérifiée de bout en bout. Concrètement, la phase 4 livre
la commande spéciale rattachée à une ordonnance et portant ses valeurs ; la phase 8 branche
le bon de commande dessus.

**Ce qu'il ne faut pas faire :** cocher CLIENT-08 en phase 4 au motif que la structure
existe. La traçabilité des exigences ne vaut que si une case cochée signifie « un opticien
peut le faire ». C'est la même discipline que les phases 03-05 à 03-10 ont tenue en ne
cochant pas PERM-02/03 avant que leur moitié interface existe.

**Alternative, si le propriétaire préfère :** déplacer CLIENT-08 vers la phase 8 dans
`REQUIREMENTS.md`, ce qui est plus honnête qu'une exigence ouverte pendant quatre phases.

## Zone grise 3 — où vit la photo de l'ordonnance (CLIENT-09)

**Ce qu'il faut trancher :** le support de stockage, et son isolement par client.

**La contrainte qui domine :** c'est l'image d'un document médical, donnée sensible au sens
de la loi 09-08, et **la phase 1 n'a pas tranché la juridiction d'hébergement.** Le critère
3 de la phase 1 dit que l'infrastructure doit vivre dans la juridiction choisie *avant*
qu'une donnée client réelle y soit stockée.

**Recommandation : définir l'interface maintenant, différer le back-end.**

- Un `Storage` Django nommé, injecté par réglage, jamais un chemin en dur.
- **Pas d'image en base.** Une colonne binaire de plusieurs Mo par ordonnance rend les
  sauvegardes par client (TENANT-09) et la rétention à 10 ans (art. 211 CGI) coûteuses.
- **Le chemin porte le client**, et une lecture ne résout jamais un chemin venu du client —
  sinon c'est une fuite inter-opticiens par traversée de chemin, exactement la famille de la
  non-négociable #12.
- En développement, système de fichiers local. **Le choix de production est une sortie de la
  phase 1**, pas de celle-ci, et doit être écrit comme tel.
- L'accès à l'image passe par le **même droit** que l'ordonnance structurée
  (`ordonnance.voir`). Une URL signée qui contourne la permission ferait de la projection un
  théâtre.

## Zone grise 4 — la recherche tolérante aux translittérations (CLIENT-10)

**Ce qu'il faut trancher :** jusqu'où aller.

CLIENT-10 : « Mohamed », « Mohammed » et « Mhamed » trouvent la même personne.

**Recommandation, en deux couches :**

1. **`unaccent` + `pg_trgm`** de PostgreSQL, avec un index GIN sur le nom normalisé. Cela
   règle les accents, la casse, et une bonne part des variantes par similarité
   trigrammes — « Mohamed » / « Mohammed » sont à une lettre l'un de l'autre.
2. **Une table d'équivalences curée**, amorcée avec les variantes marocaines courantes, pour
   les cas que les trigrammes ne rapprochent pas assez (« Mhamed » perd deux caractères sur
   sept). C'est de la donnée, pas du code : elle s'enrichit sans redéploiement.

**Ce qu'il faut refuser :** une normalisation phonétique générique de type Soundex ou
Metaphone. Elles sont réglées sur l'anglais, et sur des noms arabes translittérés en français
elles rapprochent des noms distincts autant que des variantes du même — un faux positif au
comptoir, c'est la fiche du voisin.

**À vérifier avant de s'engager :** `unaccent` et `pg_trgm` sont des extensions, donc une
migration `CREATE EXTENSION` par base client. Avec une base par client et un
`migrate_all` qui éventaille, cela doit fonctionner sur un rôle non superutilisateur —
**à prouver tôt**, comme PgBouncer l'a été.

## Zone grise 5 — la phase 4 est probablement le premier vrai client du registre de projection

Non présentée au propriétaire : c'est une décision d'ingénierie, consignée pour que le plan
la prenne sciemment.

`CHAMPS_PROTEGES` est vide et le plan 03-06 désignait la phase 8 (`prix_achat`) comme celle
qui le remplirait. **Les ordonnances arrivent avant.** La question à trancher dans le plan :

- Une ordonnance est-elle un **champ** protégé ou une **ligne** protégée ? Le droit
  `ordonnance.voir` gouverne l'accès à un objet entier, pas à une colonne — ce qui relève de
  `MagasinScopedViewSet` et du filtrage de queryset (03-07), pas de `CHAMPS_PROTEGES` (03-06).
- Mais la fiche client affiche-t-elle un **résumé** de la dernière ordonnance ? Si oui, ce
  résumé est un champ protégé sur un objet visible, et le registre s'applique.

**La règle de 03-06 vaut ici :** un nouveau rendu doit être ajouté à la liste `RENDUS` de
`tests/test_projection.py` **dans le plan qui le crée**, avec sa branche d'assertion. Il y en
a quatre aujourd'hui (JSON, CSV, HTML, catalogue).

## Rappel légal, à ne pas confondre avec un blocage

Construire le module d'ordonnances est possible dès maintenant. **Le verrou légal porte sur
le stockage de données patient réelles**, pas sur l'écriture du code : le critère 3 de la
phase 1 exige que l'infrastructure soit dans la juridiction choisie avant qu'une donnée
réelle y arrive, et l'autorisation CNDP est annoncée à 2–4 mois.

**La phase 1 n'a pas commencé.** Si ce module atteint un opticien réel avant que la phase 1
n'aboutisse, l'exposition est celle du client, causée par notre logiciel. À redire au moment
du déploiement, pas à chaque plan.

## Ce que le plan doit produire en plus du code

- Une **UI-SPEC** : la feuille de route marque la phase 4 « UI hint: yes », et l'écran de
  saisie d'ordonnance est le plus dense du produit après `Comptes et droits`.
- Les **quatre pièges payés en phase 3**, à ne pas redécouvrir : un critère qui grep un mot
  nu attrape sa propre prose (huit fois) ; `mutate()` rend la main avant l'appel réseau ;
  jsdom ne calcule pas le CSS ; les listes d'origines de confiance du CSRF sont des
  `cached_property`.
- Le solde de **18 vérifications manuelles de la phase 3** est ouvert. La phase 4 ne doit pas
  en ajouter sans que quelqu'un ait l'intention de les faire.

---

## Décisions du propriétaire — 2026-09-18

Prises après la recherche de phase (`04-RESEARCH.md`), qui a **infirmé trois des
recommandations ci-dessus**. Ces décisions-ci priment sur les zones grises 1 et 5.

### D-4a — l'ordonnance est à l'échelle du CLIENT, pas du magasin

**Tranché par le propriétaire.** Un gérant qui voit le client voit tout son historique
d'ordonnances, quel que soit le magasin qui l'a saisie.

**La raison est clinique, pas ergonomique.** Scoper l'ordonnance au magasin produit le
danger que la recherche a nommé : un gérant de Maârif qui ne voit pas l'ordonnance saisie à
Anfa **en saisit une seconde**, et le client se retrouve avec deux historiques divergents
pour un seul œil. Une duplication d'historique de prescription n'est pas une gêne
d'interface.

**Conséquence pour le plan :** `Ordonnance` **n'hérite pas** de `MagasinScopedViewSet`. Ce
sera la première entité métier de la phase 4 à ne pas le faire, donc **l'exception doit être
écrite à côté du modèle**, avec cette raison — sinon un relecteur de la phase 7 la prendra
pour un oubli et « corrigera » le danger dans le code.

**Ce qui reste vrai :** l'accès passe par le droit `ordonnance.voir`, et l'ordonnance
**porte le magasin qui l'a saisie**, pour la traçabilité et pour les rappels de la phase 10.
Porter la provenance n'est pas filtrer dessus.

### D-4b — les bornes cliniques, arrêtées

Trois jeux de chiffres coexistaient : ceux de `PITFALLS.md`, les miens (zone grise 1), et la
mesure de la recherche. Le propriétaire a demandé qu'on tranche. Retenu :

| Champ | Borne | D'où elle vient |
|---|---|---|
| Sphère | **−20,00 à +20,00**, pas de 0,25 | `PITFALLS.md:449`, recherche antérieure du projet. Mon ±30 n'avait aucune source. Au-delà de ±20 c'est du domaine spécialisé ; au comptoir, un −24 est bien plus souvent une faute de frappe qu'un patient |
| Cylindre | **−10,00 à 0**, pas de 0,25 | Inchangé, non contesté |
| Axe | **entier, 1 à 180** | La recherche a vérifié que l'axe s'écrit 1–180 : 180 s'emploie là où 0 serait, donc accepter 0 accepte une valeur qu'aucune ordonnance ne porte |
| Addition | **+0,75 à +4,00**, pas de 0,25 | `PITFALLS.md:449`. Mon plancher à +0,50 admettait une valeur qui ne se prescrit pratiquement pas |

**Et le contrôle qu'aucun des trois jeux ne portait :** l'addition est **normalement
identique aux deux yeux**. Une addition différente est la signature de la faute de frappe
plausible, celle qu'aucune borne n'attrape. **Avertissement, pas refus** — le cas légitime
existe.

**Les bornes vivent à UN endroit nommé**, pas dispersées dans des validateurs de champ. Le
propriétaire a déjà changé d'avis une fois sur ces chiffres ; le prochain changement doit
coûter une ligne.

### Ce que la recherche a infirmé, et qui ne doit pas ressurgir

1. **`unaccent` ne peut pas servir dans une expression d'index** — elle est `STABLE`, pas
   `IMMUTABLE` (`42P17`), colonne générée comprise. Une normalisation NFKD côté Python dans
   une colonne ordinaire fait le travail **et supprime le besoin de l'extension**.
2. **Le rejet de Metaphone (zone grise 4) était faux**, et la mesure le dit :
   `metaphone(n,8)` groupe `MHMT = {Mhamed, Mohamed, Mohammed, Mouhamed}` — exactement
   l'exigence CLIENT-10 — tout en gardant *Abdelkader* et *Abdelkrim* séparés, ce que
   soundex, dmetaphone **et** les trigrammes échouent tous à faire. La longueur de code ≥ 6
   porte le résultat. **Prévoir une garde pour l'écriture arabe**, qui rend une clé vide et
   collerait alors tous les noms entre eux.
3. **Le trigramme seul échoue sur l'exemple de CLIENT-10** : `%` au défaut de 0,3 ne rend pas
   *Mohammed*. Et aucun seuil ne sauve la méthode — `mohammed↔mhamed` = **0,333** passe
   *sous* `fatima↔fatiha` = **0,400**. Le trigramme sert au rappel et au classement, **jamais
   au filtrage**.
4. **La transposition minus-cyl ↔ plus-cyl appartient à la phase 4**, en fonction pure. Les
   ophtalmologistes prescrivent en cylindre négatif, **mais les opticiens et les labos
   travaillent en positif et transposent quotidiennement** — et CLIENT-08 envoie ces valeurs
   au fournisseur. Cela manquait entièrement à la zone grise 1.
5. **`CREATE EXTENSION` doit être une migration, pas du provisionnement** :
   `provision_client()` sort tôt sur `status == ACTIVE`, donc une création au
   provisionnement sauterait en silence tous les clients existants.
6. **La phase 4 est la première à toucher le danger PgBouncer T-02-02** : un `SET` nu a été
   observé **fuyant vers une connexion fraîche du pool**. `SET LOCAL` dans un `atomic()`
   revient correctement.
7. **`FileField(storage=callable)` n'évalue son appelable qu'une fois**, à la construction du
   champ : pas d'instance de stockage par locataire par ce chemin.

### Trois points soulevés par la recherche, non tranchés, à traiter dans le plan

- `date_naissance` est nécessaire sur `Client` (règle des moins de 16 ans, et RAPPEL-04 en
  phase 10) alors qu'aucune exigence CLIENT ne la nomme.
- `telemetry.SENSITIVE_KEY` ne couvre ni `photo`, ni `image`, ni `fichier`, ni `scan` — or un
  nom de fichier téléversé porte couramment le nom du patient.
- La sauvegarde par client de TENANT-09 ne couvre peut-être pas un magasin de fichiers vivant
  hors de la base.

---

## Les six questions ouvertes de l'UI-SPEC §28 — tranchées, 2026-09-18

### Q1 — les bornes sont **servies**, pas compilées. Retenu.

L'argument de l'UI-SPEC tient et découle de D-4b : les bornes vivent à **un** endroit nommé.
Une constante TypeScript en serait un second, et deux sources dérivent — c'est le mode de
défaillance que PERM-06 combat pour les champs, appliqué ici aux nombres. Elles voyagent
avec l'amorçage que l'application fait déjà, pas par un aller-retour supplémentaire.

### Q2 — CLIENT-02 et CLIENT-08 restent dans la phase 4, **non cochées**

Ni l'une ni l'autre n'est satisfaisable ici : CLIENT-02 veut l'historique d'achats, qui
suppose les ventes (phase 6) ; CLIENT-08 veut le bon de commande fournisseur (phase 8).

**Ne pas les déplacer dans `REQUIREMENTS.md`.** Le projet a déjà un précédent, tenu par les
plans 03-05 à 03-10 : une exigence reste rattachée à la phase qui construit sa structure, et
n'est **cochée** que par la phase où un opticien peut réellement l'accomplir. Déplacer la
ligne perdrait la trace de qui a posé les fondations.

La phase 4 livre donc la structure des deux et n'en coche aucune.

### Q3 — pas de sélecteur de calendrier. Masque `jj/mm/aaaa` seul.

Conforme au report déjà décidé dans l'UI-SPEC. Un opticien qui recopie une date depuis une
ordonnance papier tape plus vite qu'il ne clique.

### Q4 — **le discriminant 45 mm devient un AVERTISSEMENT, pas un refus**

C'est le seul point où je renverse l'UI-SPEC.

Elle fait du dépassement monoculaire/binoculaire un **refus**, en marquant les deux seuils
`[JUGEMENT — sans source]`. Or :

- Un **refus fondé sur un nombre deviné bloque une saisie légitime au comptoir.** Le coût
  d'un faux refus est un opticien qui ne peut pas enregistrer une ordonnance réelle ; le coût
  d'un faux avertissement est une phrase à lire.
- Cela **contredit le principe que l'UI-SPEC applique partout ailleurs** : avertir, pas
  refuser, dès qu'un seuil n'a pas de source.
- Le critère 3 de la feuille de route dit « refused at entry » pour « a monocular value
  entered where a binocular écart pupillaire is expected ». Le mécanisme de détection est
  conservé et le critère reste servi ; c'est sa **sévérité** qui attend une source.

**Le mécanisme ne change pas, la sévérité seule change** — et elle redevient un refus en une
ligne le jour où un opticien confirme le seuil. Les deux messages restent ceux de l'UI-SPEC
§20.5, qui nomment déjà la correction plutôt que la règle.

**À poser à un opticien**, avec les quatre questions de facturation déjà en attente dans
CLAUDE.md : *à partir de quel écart un nombre saisi comme binoculaire est-il certainement
monoculaire, et réciproquement ?*

### Q5 — la photo peut passer de `null` à posée sur une version immuable. Retenu.

La photo est une **pièce jointe de preuve**, pas une valeur clinique. L'ordonnance papier est
souvent scannée après la saisie, au comptoir suivant. Interdire l'ajout obligerait à créer une
version qui ne change aucune valeur, ce qui polluerait l'historique que CLIENT-06 protège.

**La règle qui tient l'immuabilité : on attache une fois.** Pas de remplacement, pas de
suppression. Une photo posée sur la mauvaise version se corrige par une nouvelle version,
comme tout le reste.

### Q6 — la mesure du nom accessible est adoptée

L'infrastructure de test `computeAccessibleName` que cette phase introduit attraperait le
manquement D-1 déjà consigné (`03.1/deferred-items.md` : le sélecteur de magasin du shell n'a
aucun nom accessible, `combobox` étant un rôle *name from author*). **La phase 4 ne le corrige
pas** — hors périmètre — mais elle doit poser la mesure de sorte que le correctif soit
trivial quand il viendra, et n'introduire aucun nouveau `combobox` sans nom.
