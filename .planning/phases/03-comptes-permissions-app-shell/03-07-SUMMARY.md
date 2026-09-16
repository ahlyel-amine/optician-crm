---
phase: 03-comptes-permissions-app-shell
plan: 07
subsystem: portee-des-lignes-et-des-agregats
tags: [projection, portee-magasin, PERM-04, PERM-05, PERM-06, idor, oracle, drf, ast, T-03-39, T-03-40, T-03-41, T-03-42, T-03-43, T-03-44, T-03-45, A-03-04, A-03-07, A-03-13]
requires:
  - 03-06 (registre de projection, champs_interdits, SerializerProjete, acces_du_contexte, la ressource de test)
  - 03-05 (Acces.magasins_ids, Acces.pour_le_schema, Acces.ANONYME, Acces.SCHEMA, AccesMiddleware)
  - 03-04 (permissions_catalogue.Permission, AccesMagasin, DroitAccorde, leurs factories)
  - 02-02 (domaine.magasins.Magasin, MagasinScopedModel, MagasinScopedQuerySet et leur non-convention)
  - 02-03 (TenantRouter fail-closed, current_alias, les deux locataires de test)
provides:
  - plateforme/projection/vues.py — MagasinScopedViewSet (mixin), MagasinAutoriseField, agreger_dans_la_portee, acces_de_la_requete
  - plateforme/projection/filtres.py — ProjectedOrderingFilter, ProjectedFieldFilter, champs_de_tri_autorises, MESSAGE_DE_REFUS, PARAMETRES_RESERVES
  - plateforme/projection/checks.py — retours_values_queryset, modules_de_vues, vues_sans_portee_magasin, toutes_les_vues, serializers_sans_projection, tous_les_serializers
  - la declaration de portee de route `scope: "magasin" | "multi"`, ecrite dans vues.py pour la phase 7
  - tests/ressources_fixture.py — RessourceMagasin, son serialiseur, sa vue, ses aides, et VueRessourceFiltrable
affects:
  - phase 5 (stock — tout modele magasin-scope herite du mixin, en premiere base)
  - phase 6 (ventes et facturation — meme regle, plus la regle des serialiseurs imbriques)
  - phase 7 (caisse — le garde d'enumeration est ce qui rend cette phase sure)
  - phase 8 (achats — la premiere vraie ligne de CHAMPS_PROTEGES ; les gardes mordent ce jour-la)
  - phase 10 (tableau de bord — tout agregat passe par agreger_dans_la_portee ou une methode de queryset prenant l'acces)
  - 03-13 (le selecteur de magasin et l'invite de choix consomment la declaration de portee de route)
tech-stack:
  added: []
  patterns:
    - la portee des lignes est ecrite dans get_queryset(), jamais dans list() — get_object() y passe
    - un queryset de champ lie restreint transforme un IDOR d'ecriture en erreur de validation
    - on ne caviarde pas un scalaire deja calcule : l'agregat se prend sur le queryset deja restreint
    - une allowlist de tri ou de filtre est derivee de la projection, jamais tenue a la main
    - tous les refus d'un parametre de requete sont indiscernables — sinon le code de statut est l'oracle
    - une echappatoire se garde par une enumeration testee, et le garde porte son propre controle negatif
    - un garde d'heritage verifie l'ordre du MRO quand le mode de defaillance est silencieux
key-files:
  created:
    - plateforme/projection/vues.py
    - plateforme/projection/filtres.py
    - plateforme/projection/checks.py
  modified:
    - tests/ressources_fixture.py
    - tests/test_magasin_acces.py
    - tests/test_projection.py
key-decisions:
  - "MagasinScopedViewSet est un MIXIN, pas une sous-classe de ModelViewSet — la caisse de la phase 7 est un registre en ajout seul et ne veut ni update ni destroy. Le prix est un mode de defaillance silencieux (mauvais ordre de bases), paye par un garde qui verifie le MRO"
  - "Tout refus d'un parametre de requete produit le meme corps : champ protege, champ public non declare et nom inexistant sont indiscernables. Ne pas nommer le champ ne suffisait pas — le code de statut aurait ete l'oracle"
  - "django-filter n'est pas ajoute : une dependance qui entre dans la pile est une decision de PROJECT.md. ProjectedFieldFilter couvre le besoin de la phase 3"
  - "agreger_dans_la_portee PREND l'acces et applique la portee elle-meme, plutot que de faire confiance a l'appelant pour lui passer un queryset deja filtre : un appelant qui se trompe obtient alors un nombre restreint, pas un nombre global"
  - "Les gardes de checks.py sont des fonctions PURES prenant une liste, pas des boucles ecrites dans les tests — c'est ce qui permet de leur passer le cas fautif sans le declarer au niveau du module"
  - "Les gardes restent des tests, pas des system checks : la condition de promotion en projection.E001 est ecrite dans la docstring du module plutot que laissee a la memoire"
  - "REQUIREMENTS.md n'est pas coche : PERM-04 est encore reclamee par 03-13 et 03-14, PERM-05 par la verification vivante de la phase 8"
patterns-established:
  - "Portee de route : chaque route declare scope magasin | multi ; quand la portee active est « tous » et que la route en exige un, l'interface affiche une invite de choix, jamais un premier magasin devine"
  - "Valeur derivee protegee : elle vit derriere une methode de queryset prenant l'acces — avec_marge(acces) — qui ne pose l'annotation que si le droit est detenu"
  - "Regle de revue : une annotate() qui produit de la monnaie est une question de registre, pas une commodite locale"
requirements-completed: [PERM-04, PERM-05]
duration: ~75 min
completed: 2026-09-16
---

# Phase 3 Plan 07 : la portée des lignes et des agrégats — Summary

**La moitié « lignes » de la garantie existe : la portée est dans `get_queryset()` donc la
route de détail est couverte, le queryset du champ lié transforme une écriture
inter-magasins en 400, l'agrégat se prend sur le queryset déjà restreint, le tri et le
filtre ne sont plus un oracle, et trois gardes d'énumération font échouer en CI l'oubli que
la phase 7 commettra.**

## Performance

- **Durée :** ~75 min
- **Tâches :** 3
- **Fichiers :** 6 (3 créés, 3 modifiés), 1 472 lignes ajoutées
- **Suite :** 158 passed, 15 deselected (149 / 20 avant)

## Task Commits

1. **Task 1 : la portée magasin dans `get_queryset`, les champs liés, les agrégats** — `37b7208` (feat)
2. **Task 2 : l'oracle de tri et de filtre, fermé par des listes dérivées** — `9bc29f4` (feat)
3. **Task 3 : les gardes d'énumération** — `7fd0877` (feat)

Chaque commit nomme explicitement ses chemins (`git commit -F - -- <chemins>`), la forme
sûre en worktree partagé — et cette vague en est une : **03-08 est dans la vague 6 avec ce
plan**.

---

## Ce que les phases 5 à 10 doivent savoir, et qui ne se relit pas tout seul

Trois règles. La première est mécaniquement gardée, la deuxième l'est à moitié, la
troisième ne l'est pas du tout — et c'est pour la troisième que ce paragraphe existe.

| Règle | Ce qui la tient |
|---|---|
| **Tout nouveau modèle magasin-scopé a une vue qui hérite de `MagasinScopedViewSet`, en première base** | `vues_sans_portee_magasin` — rouge en CI, ordre du MRO compris |
| **Tout agrégat se prend sur le queryset déjà restreint**, via `agreger_dans_la_portee(qs, acces, ...)` ou une méthode de queryset prenant l'accès | rien d'automatique ; `retours_values_queryset` n'attrape que la forme `Response(qs.values(...))` |
| **Une `annotate()` qui produit de la monnaie est une question de registre, pas une commodité locale** | **rien** — c'est une règle de revue, écrite dans la docstring de `checks.py` |

La troisième est le trou résiduel, et il est nommé plutôt que masqué :
`qs.annotate(marge=F("prix_vente") - F("prix_achat"))` ne nomme aucun champ protégé, ne
déclenche aucun garde, et sert une marge que l'appelant n'a pas le droit de lire. La forme
correcte est ::

    class VenteQuerySet(MagasinScopedQuerySet):
        def avec_marge(self, acces):
            if not acces.peut(Permission.VENTE_VOIR_MARGE):
                return self
            return self.annotate(marge=F("prix_vente") - F("prix_achat"))

C'est pour cela que T-03-44 est marqué « mitigate **partiellement** » dans le registre de
menaces du plan, et non « mitigate ».

### La déclaration de portée de route, que la phase 7 consommera

`03-UI-SPEC.md` 5.4 l'exige et elle est posée maintenant, dans la docstring de
`plateforme/projection/vues.py`, pas au moment où la caisse en aura besoin.

**Chaque route déclare `scope: "magasin" | "multi"`.** Certains écrans sont
intrinsèquement mono-magasin — la caisse, l'inventaire, les mouvements de stock ; d'autres
sont légitimement inter-magasins — le tableau de bord du propriétaire, la réappro. Quand la
portée active est « Tous les magasins » et que la route en exige **un**, l'interface affiche
une invite de choix :

> ### Choisissez un magasin
> La caisse est propre à chaque magasin. Sélectionnez-en un pour continuer.
> `[ Anfa ]` `[ Maârif ]` `[ Californie ]`

Elle ne devine jamais. Choisir en silence le premier magasin et afficher son solde de caisse
est exactement le « nombre faux sans erreur » que `domaine/magasins/models.py` refuse déjà
au niveau ORM — la même erreur, un étage plus haut, et cette fois avec un chiffre à l'écran
que personne ne soupçonnera.

---

## Le défaut de PERM-05, écrit plutôt que contourné

La feuille de route range « le chiffre d'affaires global est caché à un gérant » avec le
prix d'achat et la marge, comme si c'était le même genre de problème. Ce n'en est pas un :

> **Le chiffre d'affaires global n'est pas un problème de visibilité de champ.** On ne
> caviarde pas un scalaire déjà calculé ; il faut ne pas le calculer.

Le total n'est le champ de personne. Il n'a pas de ligne de registre possible, pas de
`get_fields()` d'où le retirer, et aucun sérialiseur ne le voit avant qu'il n'existe. La
seule défense est l'ordre des opérations, et c'est pourquoi l'aide **prend l'accès** plutôt
que de recevoir un queryset supposé déjà filtré :

```python
def agreger_dans_la_portee(queryset, acces, **agregations):
    if not acces.pour_le_schema:
        queryset = queryset.for_magasins(acces.magasins_ids)
    return queryset.aggregate(**agregations)
```

La différence avec la signature « passe-moi un queryset déjà filtré » n'est pas de style :
un appelant qui se trompe obtient alors un nombre **restreint**, pas un nombre global. Le
sens de l'erreur est le bon.

Le test le prouve par un nombre, pas par une propriété : les deux magasins portent des
montants différents (1 800,00 et 2 500,00), la somme d'Anfa et celle de l'entreprise sont
assertées **différentes** avant l'appel, et le gérant doit recevoir la première. Une
implémentation qui calcule puis masque rend la seconde, et il n'y a pas de troisième
possibilité.

---

## Pourquoi un mixin, et ce que ce choix a coûté

`03-RESEARCH.md` §5 écrit `class MagasinScopedViewSet(viewsets.ModelViewSet)`. Ce plan livre
un **mixin sans classe de base DRF**, et le motif est concret plutôt que stylistique : la
caisse de la phase 7 est un registre en ajout seul (CLAUDE.md #4), donc ses vues sont des
`ReadOnlyModelViewSet` plus une route de création. Hériter d'un `ModelViewSet` complet leur
donnerait `update` et `destroy` par défaut — sur un registre où la correction est une
écriture compensatoire, c'est exactement le contraire de ce qu'il faut.

**Le mixin a un mode de défaillance que la sous-classe n'avait pas**, et il fallait le payer
avant de s'en servir :

```python
class Vue(ModelViewSet, MagasinScopedViewSet):   # hérite bien du mixin
    ...                                          # et la portée ne s'applique pas
```

`issubclass(Vue, MagasinScopedViewSet)` répond `True`. `GenericAPIView.get_queryset` gagne
le MRO. La portée disparaît **sans erreur**, la vue a l'air protégée, et la revue de code ne
voit rien. C'est précisément la classe de bug que cette phase entière refuse.

D'où un garde qui ne regarde pas l'héritage mais l'**ordre** :
`mro.index(MagasinScopedViewSet) > mro.index(GenericAPIView)` est une faute nommée, avec son
propre contrôle négatif. Le test passe deux vues fautives au garde — le mixin absent, et le
mixin dans le mauvais ordre — et exige qu'il en voie **deux**.

---

## L'oracle de tri et de filtre : ne pas nommer le champ ne suffisait pas

Le plan demande un 400 qui ne nomme pas le champ refusé. En l'écrivant, une propriété plus
forte s'est imposée, et elle change la conception :

> Si un champ protégé produisait un 400 là où un nom inexistant produit un 200, **le code
> de statut serait l'oracle**. « 400 » voudrait dire « ce champ existe », et l'attaque
> coûterait une requête au lieu d'être impossible.

La règle livrée est donc : **la chaîne de requête est une allowlist, et tout ce qui n'y
figure pas produit exactement la même réponse.** Un champ protégé, un champ public non
déclaré filtrable et un nom qui n'existe nulle part sont indiscernables — même statut, même
corps, même message, aucune clé de champ. Le test l'affirme par `assert inexistant.data ==
protege.data`, ce qui est une assertion plus forte que « le nom est absent du corps » et
plus difficile à affaiblir par inadvertance.

Conséquence pratique à connaître avant d'écrire une vue filtrable : `PARAMETRES_RESERVES`
énumère les paramètres non-filtres (`ordering`, `format`, `page`, `page_size`, `cursor`,
`search`). Une phase qui ajoute la pagination ou la recherche **ajoute son nom dans le même
commit**, sinon son propre paramètre sera refusé.

Et l'allowlist de la ressource de test déclare le champ protégé **exprès**. C'est tout
l'intérêt : une allowlist qui l'omettrait déjà à la main rendrait le test vert sans que
`champs_interdits` ait servi à quoi que ce soit. Ce qui ferme la porte est la **dérivation
depuis la projection**, pas la vigilance de celui qui écrit la liste.

---

## L'admission de la phase, répétée parce qu'elle est la vérité du module

Le filtre magasin est **entièrement en Python et rien ne le soutient en dessous**. Tous les
utilisateurs d'un client partagent un seul rôle PostgreSQL, donc la base ne sait pas
distinguer le gérant d'Anfa de celui de Maârif. Contrairement à la frontière inter-clients,
il n'y a **aucun `REVOKE` à écrire ici** — CLAUDE.md #12 ne s'applique pas à cette couche,
et prétendre le contraire serait la même erreur qu'à la phase 2, en costume neuf.

Le contrôle compensatoire est l'**énumérabilité**, construite à la tâche 3. Et les deux
couches ne se substituent jamais l'une à l'autre : le filtre magasin ne sert pas d'isolation
inter-clients, le routeur ne sert pas de portée magasin. La ressource de test est créée dans
les **deux** bases locataires précisément pour que l'assertion qui sépare les deux couches
reste écrivable par un plan ultérieur.

---

## Rouge → vert

| Test | Rouge, pour quelle raison | Vert |
|---|---|---|
| collecte de `tests/test_magasin_acces.py` | `ModuleNotFoundError: plateforme.projection.vues` | après `vues.py` (tâche 1) |
| `..._un_gerant_ne_voit_que_les_magasins_accordes_en_liste_et_en_detail` | `NoTenantBound` à l'import, puis `ImproperlyClassifiedApp` sur l'affectation de la clé étrangère | après la propriété `db` paresseuse et l'`__init__` de `RessourceMagasin` |
| `..._un_gerant_ne_peut_pas_ecrire_dans_un_magasin_non_accorde` | idem | après `MagasinAutoriseField` |
| `..._un_agregat_est_calcule_sur_le_queryset_deja_filtre` | idem | après `agreger_dans_la_portee` |
| `..._la_generation_du_schema_ne_subit_pas_la_portee_magasin` (neuf) | idem | après le court-circuit `pour_le_schema` |
| collecte de `tests/test_projection.py` | `ModuleNotFoundError: plateforme.projection.filtres` | après `filtres.py` (tâche 2) |
| `..._un_champ_protege_ne_peut_ni_trier_ni_filtrer` | idem | après `ProjectedOrderingFilter` + `ProjectedFieldFilter` |
| `..._le_400_de_tri_ne_nomme_pas_le_champ_protege` (neuf) | idem | après `MESSAGE_DE_REFUS` unique |
| `..._aucune_vue_ne_renvoie_un_values_queryset` | `ModuleNotFoundError: plateforme.projection.checks` | après `retours_values_queryset` (tâche 3) |
| `..._enumeration_tout_serializer_exposant_un_champ_protege_est_projete` (neuf) | idem | après `serializers_sans_projection` |
| `..._enumeration_toute_vue_magasin_scopee_herite_du_mixin` (neuf) | idem | après `vues_sans_portee_magasin` |

Marqueurs `pending` : **3 → 0** dans `tests/test_magasin_acces.py`, **3 → 1** dans
`tests/test_projection.py`. Le seul restant est
`test_perm06_le_catalogue_servi_a_un_gerant_manager_est_deja_intersecte`, qui appartient
nommément au plan **03-09**. Aucun marqueur d'un autre plan n'a été touché.

---

## Critères d'acceptation, tels qu'exécutés

### Tâche 1

| Critère | Résultat |
|---|---|
| `grep -c 'def get_queryset' vues.py` ≥ 2 | **2** |
| `grep -c 'def list' vues.py` → 0 | **0** |
| `grep -c 'Magasin.objects.all()' vues.py` → 0 | **0** — voir déviation 1 |
| `grep -c 'id__in' vues.py` ≥ 1 | **1** |
| `grep -c 'pour_le_schema' vues.py` ≥ 1 | **2** |
| `pytest -k "liste_et_en_detail or ecrire or agregat"` | **3 passed** |
| `grep -c 'pytest.mark.pending' tests/test_magasin_acces.py` a baissé de ≥ 3 | **3 → 0** |
| `<verify>` : `-k "... or schema"` | **4 passed** |

### Tâche 2

| Critère | Résultat |
|---|---|
| `grep -c 'champs_interdits' filtres.py` ≥ 1 | **7** |
| `grep -ci 'silenc' filtres.py` ≥ 1 | **6** |
| `pytest -k "trier_ni_filtrer"` contrôle positif inclus | **1 passed**, quatre contrôles positifs dedans |
| un test affirme que le corps du 400 ne nomme pas le champ | **`..._le_400_de_tri_ne_nomme_pas_le_champ_protege`, passed** |
| `<verify>` | **1 passed** |

### Tâche 3

| Critère | Résultat |
|---|---|
| `grep -c 'values_list\|\.values('` checks.py ≥ 1 | **7** |
| `grep -c 'MagasinScopedViewSet' checks.py` ≥ 1 | **6** |
| `grep -c 'SerializerProjete' checks.py` ≥ 1 | **4** |
| `pytest tests/test_projection.py -k "values_queryset or enumeration"` | **2 passed** |
| `pytest tests/test_magasin_acces.py -k enumeration` | **1 passed** |
| `grep -c 'pytest.mark.pending' tests/test_projection.py` ≤ 1 | **1** — voir déviation 2 |
| `<verify>` | **36 passed, 1 deselected** |

### Vérification du plan

| Critère | Résultat |
|---|---|
| `pytest tests/test_magasin_acces.py tests/test_projection.py -q` | **36 passed, 1 deselected** (le `pending` du plan 03-09) |
| `manage.py check` | **no issues (0 silenced)** |
| `pytest -x -q -m "not slow and not pending"` | **128 passed** |
| `pytest -q -m "not pending"` | **158 passed, 15 deselected** (149 / 20 avant) |
| `grep -rn 'Magasin.objects.all()' plateforme/ domaine/` | **1 ligne** — voir déviation 1 |
| `grep -rn 'def list(' plateforme/projection/` | **vide** |

---

## Déviations du plan

### 1. [signalé] `grep -rn 'Magasin.objects.all()' plateforme/ domaine/` retourne une ligne, et elle n'est pas de ce plan

`plateforme/comptes/models.py:320` — `acces = AccesMagasin.objects.all()`. C'est
**`AccesMagasin`**, une table du plan de contrôle qui n'a rien à voir avec `Magasin`, et le
critère l'attrape par sous-chaîne. Aucun `Magasin.objects.all()` n'existe dans le dépôt.
Vérifié ligne par ligne.

La forme durable de ce critère porte sur `\bMagasin\.objects\.all\(\)` avec une frontière de
mot, et les plans qui le réutiliseront devraient l'écrire ainsi.

Le critère de tâche `grep -c 'Magasin.objects.all()' plateforme/projection/vues.py → 0` est
en revanche satisfait : la phrase d'interdiction de la docstring a été **reformulée** pour
ne pas citer la forme interdite littéralement, avec une ligne qui explique pourquoi elle ne
la cite pas. Même arbitrage que la déviation 9 du plan 03-06, et même conclusion : un
critère grepable qui porte sur l'occurrence d'un mot plutôt que sur la ligne d'import
demande à la prose de se contorsionner.

C'est le cinquième critère de cette phase à correspondre à sa propre prose plutôt qu'au
fichier livré (03-04 en a signalé deux, 03-05 un, 03-06 un).

### 2. [signalé] Le `pending` restant appartient au plan 03-09, pas au 03-10

Le critère de la tâche 3 dit « seul le test de contrat de schéma du plan 03-10 reste en
attente ». Il en reste bien **un**, donc le compteur est satisfait, mais ce n'est pas
celui-là : `test_perm06_le_catalogue_servi_a_un_gerant_manager_est_deja_intersecte`
appartient au plan **03-09**, ce que `03-06-SUMMARY.md` dit déjà nommément. Le test de
contrat de schéma du plan 03-10 vit dans `tests/test_schema_contrat.py`, un autre fichier,
et il y est `pending` comme prévu. Le plan a confondu les deux fichiers ; le compte est bon.

### 3. [Rule 3 — bloquant] La ressource de test magasin-scopée a demandé trois pièces de plomberie que le plan ne prévoyait pas

Le plan demande « étendre `tests/ressources_fixture.py` d'une ressource magasin-scopée ».
La ressource porte une clé étrangère vers `magasins.Magasin`, qui vit dans la base du
locataire, et `tests` n'est **pas** une application classée dans `TenantRouter` — par une
décision du plan 03-06 qu'il n'était pas question de renverser ici pour le confort d'un
modèle fictif. Trois obstacles en ont découlé, tous résolus dans `tests/`, aucun dans le
code de production :

| Obstacle | Ce qui a été écrit |
|---|---|
| `VueRessourceMagasin.queryset` est construit à l'**import**, où aucun locataire n'est lié : `current_alias()` y levait `NoTenantBound` et la suite entière refusait de se collecter | une propriété `db` sur le queryset, qui résout l'alias à l'exécution — c'est le moment où Django la lit |
| `ForwardManyToOneDescriptor.__set__` appelle `router.db_for_write(RessourceMagasin, ...)` quand `_state.db` est encore `None`, et le routeur lève sur `tests` | un `__init__` qui retire le magasin des arguments, pose l'alias, puis affecte la relation — `allow_relation` compare alors deux instances du même alias |
| la table doit exister dans les bases locataires, où aucune migration n'est possible pour une application non installée | une fixture de session par `schema_editor`, dans **les deux** locataires |

La troisième va au-delà de ce qui était strictement nécessaire : `tenant_a` aurait suffi
pour les tests de ce plan. La table est créée dans les deux parce que le registre de menaces
exige qu'un plan ultérieur puisse écrire l'assertion « la portée magasin ne sert jamais
d'isolation inter-clients », et qu'une table absente chez le client B la ferait échouer pour
la mauvaise raison.

### 4. [Rule 2 — fonctionnalité critique manquante] L'indiscernabilité des refus, au-delà de « ne pas nommer le champ »

Le plan demande que le 400 ne nomme pas le champ. Pris à la lettre, cela laisse le **code de
statut** comme oracle : `?ordering=prix_achat` → 400 et `?ordering=zzz` → 200 répond « ce
champ existe » en une requête, sans qu'aucun nom n'ait été prononcé. La règle livrée est donc
plus forte — toute la chaîne de requête est une allowlist, tous les refus sont identiques —
et le test l'affirme par égalité de corps plutôt que par absence de sous-chaîne. Voir la
section « L'oracle de tri et de filtre » plus haut.

### 5. [Rule 2] Le garde d'héritage vérifie l'ordre du MRO

Le plan demande « tout `ViewSet` enregistré dont le modèle dérive de `MagasinScopedModel`
hérite de `MagasinScopedViewSet` ». Écrit tel quel, le garde déclare sûre une vue dont la
portée ne s'applique pas — voir « Pourquoi un mixin » plus haut. La vérification d'ordre et
son contrôle négatif sont ajoutés, et le coût du choix « mixin » est ainsi payé dans le même
commit que le choix lui-même.

### 6. [Rule 2] Chaque garde de la tâche 3 porte son contrôle négatif

Un détecteur de source qui ne détecte rien passe son test pour toujours — et il le passera
aussi le jour où la phase 8 écrit la ligne fautive. Les trois gardes sont donc éprouvés sur
des cas fautifs synthétiques, passés par **le même chemin de code** que le parcours réel :
quatre formes de values queryset, deux vues mal composées, un sérialiseur non projeté. C'est
ce qui a dicté la forme « fonction pure prenant une liste » plutôt qu'une boucle écrite dans
le test.

### 7. [signalé] `tests/test_magasin_acces.py` importe désormais un nom au niveau du module

Sa docstring promettait « aucun import du code en construction au niveau du module ». La
fixture pytest `table_ressource_magasin` doit être un nom du module de test pour que pytest
la résolve, donc elle est importée — et la docstring a été corrigée pour dire l'exception et
sa portée exacte plutôt que de laisser une promesse fausse. Tout le reste est toujours
importé dans le corps des tests. C'est la même exception que `tests/test_projection.py`
pratique depuis le plan 03-06.

### 8. [signalé] Une seconde vue de test, hors de `urlpatterns`

`VueRessourceFiltrable` et `urlpatterns_magasin` sont volontairement absents de
`urlpatterns`. Le test de schéma du plan 03-06 prend `tests/ressources_fixture.py` pour
`ROOT_URLCONF` ; y ajouter des routes changerait le document que ce plan-là a rendu
déterministe, pour une raison qui n'a rien à voir avec lui. Les tests de ce plan appellent
les vues directement, exactement comme ceux du 03-06.

### 9. [signalé] `REQUIREMENTS.md` n'est pas coché

Même arbitrage qu'aux plans 03-05 et 03-06. **PERM-04** est encore réclamée par 03-13 (le
sélecteur de magasin et l'invite de choix) et par 03-14 ; **PERM-05** attend sa vérification
vivante en phase 8, quand `prix_achat` et `marge` existeront comme colonnes. Cocher ici
dirait au verrou de phase que l'exigence est faite alors que sa moitié interface n'existe
pas.

---

**Total des déviations :** 9 — 4 signalées sur des critères ou des promesses de docstring,
1 bloquante (Rule 3), 3 fonctionnalités critiques manquantes (Rule 2), 1 décision de
traçabilité. Aucune n'élargit la portée du plan.

## Issues Encountered

Aucune au-delà des trois obstacles de plomberie documentés en déviation 3, tous résolus dans
`tests/` et sans toucher au routeur de production.

## Known Stubs

Aucun. Les trois modules sont complets et testés. Rien dans ce plan ne rend une valeur vide
ni un texte d'attente vers une interface.

Deux limites sont **assumées et écrites**, et ce ne sont pas des stubs :

1. `retours_values_queryset` ne voit pas un values queryset qui traverse une fonction
   d'aide, ni une `annotate()` de monnaie. C'est pourquoi T-03-44 est « mitigate
   partiellement » et pourquoi la règle de revue est écrite dans la docstring.
2. Les gardes sont des tests, pas des `system checks`. La condition de leur promotion en
   `projection.E001` est écrite dans la docstring de `checks.py` : tous les modules de vues
   et de sérialiseurs importés de façon fiable à `ready()`, **et** un oubli constaté au
   moins une fois entre deux exécutions de la suite.

## Threat Flags

Aucun. Aucune surface réseau, aucun chemin d'authentification et aucun changement de schéma
n'est introduit par ce plan ; les trois modules livrés **retirent** de la surface plutôt
qu'ils n'en ajoutent.

## Notes pour les plans suivants

- **03-08** (même vague) : rien de ce plan ne le gêne. `/api/auth/moi/` est le premier
  appelant sanctionné de `peut_quelque_part`, étiquette `navigation`.
- **03-09** : le dernier `pending` de `tests/test_projection.py` lui appartient.
- **03-13** : l'invite de choix de magasin et la déclaration `scope: "magasin" | "multi"`
  sont spécifiées dans la docstring de `plateforme/projection/vues.py`. Le serveur filtre
  de toute façon ; l'invite existe pour ne pas afficher un nombre juste pour le mauvais
  magasin.
- **Phases 5 à 7** : hériter de `MagasinScopedViewSet` **en première base**. Le garde dira
  laquelle est fautive et pourquoi, mais il ne l'écrira pas à votre place.
- **Phase 8** : c'est la phase où tous ces gardes mordent pour la première fois sur du vrai
  code. Une ligne dans `CHAMPS_PROTEGES`, une entrée dans `_sujet_pour`, et le tri, le
  filtre, le CSV, le HTML et le schéma se resserrent ensemble.
- **Phase 10** : `agreger_dans_la_portee` pour les agrégats, et une méthode de queryset
  prenant l'accès pour toute valeur dérivée protégée. Jamais une `annotate()` dans la vue.

## Self-Check

Les trois fichiers créés sont présents sur le disque
(`plateforme/projection/vues.py`, `plateforme/projection/filtres.py`,
`plateforme/projection/checks.py`), les trois fichiers de test portent les changements, et
les trois commits existent dans `git log` : `37b7208`, `9bc29f4`, `7fd0877`. Suite
re-exécutée après le dernier commit : **158 passed, 15 deselected**.

---
*Phase : 03-comptes-permissions-app-shell*
*Terminé : 2026-09-16*

## Self-Check: PASSED

Sept fichiers présents sur le disque, trois commits présents dans `git log`. Vérifié après
rédaction du résumé, pas avant.
