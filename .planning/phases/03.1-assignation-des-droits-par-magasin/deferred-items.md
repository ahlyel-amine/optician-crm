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
