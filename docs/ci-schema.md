# La porte de schéma : le contrat d'API ne change pas en silence

`web/src/api/schema.yml` est **commité**. C'est ce fichier — pas l'API en cours
d'exécution — dont `npm run api:types` génère le client TypeScript de la SPA, et à partir
de la phase 11 celui de l'application Expo.

## Pourquoi commiter un fichier généré

Parce que c'est ce qui fait de « le contrat a-t-il changé ? » un **diff d'une ligne**, lu
dans la revue, à côté du code qui l'a causé. Généré au build, un champ qui apparaît ou
disparaît du client TypeScript n'apparaît nulle part : personne ne le voit, et il devient
visible trois phases plus tard sous la forme d'une colonne qui rend `undefined` — sans
qu'on puisse dire si c'est un bug de rendu, de droits ou de contrat.

C'est le niveau « contrat d'API » de `.planning/TESTING.md` §2, et c'est PERM-06 appliqué
aux **types** au lieu des valeurs.

## Régénérer

```bash
uv run python manage.py spectacular --file web/src/api/schema.yml --fail-on-warn
```

À faire **dans le même changement** que la modification de vue, de sérialiseur ou de
route qui l'a rendu nécessaire. `tests/test_schema_contrat.py` rend la suite rouge
autrement, avec cette commande dans son message.

Puis, si le client typé est régénéré dans la foulée :

```bash
cd web && npm run api:types
```

## La porte de CI

Deux lignes, à poser dans le job backend une fois que la CI existe (il n'y a pas encore de
`.github/workflows/` dans ce dépôt — c'est une décision de la phase 12) :

```yaml
- name: Le schéma OpenAPI commité est à jour
  run: |
    uv run python manage.py spectacular --file web/src/api/schema.yml --fail-on-warn
    git diff --exit-code web/src/api/schema.yml
```

La première ligne échoue sur un avertissement du générateur ; la seconde échoue si
l'arbre de travail est devenu sale, c'est-à-dire si le document régénéré diffère du
document commité. Le message d'échec de CI est alors le diff lui-même.

`git diff --exit-code` est volontairement limité à ce chemin : un job qui échoue sur
n'importe quel fichier sale attrape aussi les artefacts d'autres étapes et devient du
bruit qu'on finit par désactiver.

## Ce que la porte ne remplace pas

Le même contrôle existe dans la suite de tests
(`test_perm06_le_schema_committe_correspond_au_schema_genere`), et les deux sont utiles :
le test attrape l'écart sur la machine de qui écrit le code, la porte de CI l'attrape sur
une branche poussée depuis une machine où la suite n'a pas tourné.

Trois autres tests du même fichier gardent des propriétés que la porte ne voit pas :

- `--fail-on-warn` passe, donc aucune vue n'est ignorée par le générateur. La règle du
  plan 03-08 — toute `APIView` porte son `extend_schema` dans le plan qui la crée — n'est
  exécutable que grâce à cela : `AutoSchema` ignore une `APIView` nue en silence, et la
  route est alors absente du contrat TypeScript sans que rien ne le signale.
- le document **servi** par `/api/schema/` est identique pour chaque appelant et égal au
  document commité (menace T-03-70). Sans le crochet `GET_MOCK_REQUEST` du plan 03-06,
  `build_mock_request` recopie `request.user` et la projection s'appliquerait au schéma :
  comparer le sien à celui du propriétaire énumérerait les champs protégés.
- `/api/schema/` est fermé aux appelants anonymes. Le défaut de `SERVE_PERMISSIONS` chez
  `drf-spectacular` est `AllowAny`.
