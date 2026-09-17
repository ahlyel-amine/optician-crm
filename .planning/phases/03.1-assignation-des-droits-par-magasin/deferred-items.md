# Reporté — trouvé pendant l'exécution, hors périmètre du plan

## D-1 · Le sélecteur de magasin du shell n'a **aucun** nom accessible

**Trouvé pendant :** plan `03.1-01`, tâche 2, en écrivant l'assertion « deux `combobox`
aux noms distincts » du test 1.

**Fichier :** `web/src/layout/SelecteurMagasin.tsx`, le `Button role="combobox"` du
déclencheur.

**Constat, mesuré et non supposé.** `computeAccessibleName()` de `dom-accessibility-api`
rend la chaîne vide sur ce bouton. Ce n'est pas un défaut de jsdom : **`combobox` est un
rôle « name from author », pas « name from author and content »** — le texte de l'élément
(`Tous les magasins`) ne devient donc jamais son nom accessible. Il lui faut un
`aria-label`, un `aria-labelledby` ou un `<label>`, et il n'en a aucun.

Conséquence : un lecteur d'écran annonce « liste déroulante » sans dire de quoi. C'est un
manquement à la section 10 du `03-UI-SPEC.md`.

**Pourquoi ce n'est pas corrigé ici.** Le fichier appartient à la surface 5.4 (plans 03-12
et suivants) ; le plan `03.1-01` ne touche que `web/src/pages/comptes/` et ne l'a pas causé.
Le corriger ici mélangerait deux changements dans un commit dont le message ne décrit que
l'un des deux.

**Ce que le plan `03.1-01` en a fait à la place.** Le sélecteur des droits, lui, porte son
nom (`Régler les droits pour`, via un `<label>` visible et un `aria-labelledby`), et le test
1 vérifie la distinction sans dépendre du nom manquant de celui du shell.

**À qui cela revient.** Une tâche rapide d'une ligne, ou la passe de vérification humaine
de la phase 3 restée due sur l'app shell (7 du 03-12).

## D-2 · Un `.gitkeep` vide traîne dans le répertoire de la phase

**Trouvé pendant :** plan `03.1-03`, tâche 1, au premier `git status --short`.

**Fichier :** `.planning/phases/03.1-assignation-des-droits-par-magasin/.gitkeep`, zéro
octet, horodaté 16:27 — c'est-à-dire la minute où le répertoire de la phase a été créé.

Le répertoire porte depuis dix fichiers ; le marqueur qui servait à le garder non vide ne
sert donc plus à rien. Il est resté **non indexé** : ni commité, ni supprimé. Le supprimer
est une ligne, mais ce n'est ni ce plan ni ce commit qui l'a produit, et l'indexer le
graverait dans l'historique pour rien.

**À qui cela revient.** Au ménage du plan `03.1-04`, ou à la première tâche rapide qui
passe par là.

## D-3 · Le mot réservé de 7.10 apparaît en minuscule dans un commentaire de `dialogues.tsx`

**Trouvé pendant :** plan `03.1-03`, tâche 2, en vérifiant la garde « le mot ne figure
nulle part dans ce fichier ».

**Fichier :** `web/src/pages/comptes/dialogues.tsx`, docstring de `DialogueMotDePasse` —
`il n'y a rien a annuler, l'action est deja faite`. Introduit par `a495cf5` (plan 03-14).

La garde du plan et celle du contrat portent sur le **libellé** — la chaîne capitalisée
entre guillemets — et elle est verte. L'occurrence restante est le verbe français employé
dans son sens ordinaire à l'intérieur d'une phrase explicative, pas un libellé de bouton.

**Pourquoi ce n'est pas corrigé ici.** Le bloc de tête du fichier formule la discipline
comme « un `grep` de ce mot dans ce fichier doit rester vide », ce qui est plus strict que
ce que le fichier tient réellement. Ou bien la phrase est reformulée, ou bien la discipline
est écrite telle qu'elle s'applique — le choix est un arbitrage de contrat, pas une
correction d'exécution, et il ne relève pas de la décision 2.
