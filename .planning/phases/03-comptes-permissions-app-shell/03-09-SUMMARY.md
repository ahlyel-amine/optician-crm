---
phase: 03-comptes-permissions-app-shell
plan: 09
subsystem: surface-decriture-des-comptes-et-des-droits
tags: [PERM-02, PERM-03, PERM-06, octroi, cascade, journal, catalogue, drf, T-03-57, T-03-58, T-03-59, T-03-60, T-03-61, T-03-62, T-03-63, T-03-64, T-03-65, A-03-05]
requires:
  - 03-04 (Permission, SECTIONS, EXPLICATIONS, PREREQUIS, fermeture_prerequis, dependants, AccesMagasin, DroitAccorde, JournalDroit)
  - 03-05 (Acces, acces_pour, magasins_pour, l'etiquette `catalogue` de peut_quelque_part, AccesMiddleware)
  - 03-06 (SerializerProjete, CHAMPS_PUBLICS, le test de conformite parametre et sa liste RENDUS)
  - 03-07 (acces_de_la_requete, la regle « la portee est dans get_queryset »)
  - 03-08 (session, contrat de statuts, AUTH_PASSWORD_VALIDATORS, extend_schema obligatoire, fixture affaire_reelle)
  - 03-01 (Utilisateur et sa contrainte operateur, filet de la creation de compte)
provides:
  - "GET/POST /api/comptes/ — la liste et la creation d'un compte gerant"
  - "GET/PATCH /api/comptes/{id}/ — la fiche et la correction de l'identite"
  - "POST /api/comptes/{id}/statut/ — activation et desactivation"
  - "POST /api/comptes/{id}/mot-de-passe/ — reinitialisation, secret montre une fois"
  - "POST /api/comptes/{id}/droits/ — la bascule d'un droit, cascade comprise"
  - "POST /api/comptes/{id}/droits/uniformiser/ — replier une ligne personnalisee"
  - "POST /api/comptes/{id}/magasins/ — accorder ou retirer l'acces a un magasin"
  - "GET /api/comptes/catalogue/ — le catalogue deja intersecte (PERM-06, wire-level)"
  - "plateforme/comptes/services.py — accorder, revoquer, uniformiser, accorder_magasin, retirer_magasin, resume_des_droits, mot_de_passe_provisoire"
  - "plateforme/comptes/serializers.py:catalogue_offrable et charge_utile_resultat"
  - "le contrat de reponse d'une bascule : lignes / cascade / magasins_accordes / magasins_etendus"
affects:
  - 03-10 (schema commite : neuf operations et sept composants nouveaux y entrent)
  - 03-14 (l'ecran de droits se construit contre le contrat de reponse decrit plus bas)
  - phase 8 (une ligne de CHAMPS_PROTEGES produit desormais QUATRE assertions, catalogue compris)
  - phase 12 (l'inscription en libre service appelle le service, pas la vue)
tech-stack:
  added: []
  patterns:
    - "la regle vit dans le service, la vue ne fait que traduire — une commande de gestion obtient la meme regle"
    - "un champ d'elevation ne se refuse pas par une liste d'exclusions, qui se perime ; il se refuse par une liste d'inclusions"
    - "une reponse de bascule porte de quoi redessiner chaque ligne touchee, sinon « sauvegarde immediate » veut dire « recharge la page »"
    - "l'union `peut_quelque_part` propose, la conjonction `peut(code, magasin_id)` dispose"
    - "une section vide n'est pas servie : un titre sans ligne est un grisage typographique"
key-files:
  created:
    - plateforme/comptes/services.py
  modified:
    - plateforme/comptes/serializers.py
    - plateforme/comptes/views.py
    - plateforme/comptes/urls.py
    - config/urls.py
    - plateforme/projection/registre.py
    - tests/test_comptes_droits.py
    - tests/test_projection.py
key-decisions:
  - "`PeutGererLesComptes` lit `acces.peut(compte.gerer)` et rien d'autre : pas de `or est_proprietaire`. L'acces du proprietaire est materialise depuis 03-05, donc il passe par le meme chemin ; ajouter la branche rouvrirait le privilege que ce plan-la a supprime"
  - "`peut()` etant une conjonction, un gerant doit detenir `compte.gerer` dans TOUS ses magasins pour atteindre cette surface. Administrer des comptes n'est pas une action de magasin, et l'union n'autorise jamais rien"
  - "Une seule route par interrupteur, avec un booleen `accorde`, plutot que deux routes opposees : c'est un seul controle a l'ecran, et 7.8 exige une ecriture par bascule"
  - "Le service leve les exceptions de Django et la vue les traduit : DRF ne convertit pas `django.core.exceptions.ValidationError`, et le service doit rester appelable sans HTTP"
  - "La cible d'une gestion n'est jamais le proprietaire ni soi-meme (7.7) — ce qui ferme l'auto-promotion d'un gerant-gestionnaire et la prise de controle du compte du proprietaire par reinitialisation"
  - "Le dernier magasin d'un compte n'est PAS refuse cote serveur : un compte neuf en a legitimement zero, donc « au moins un » est un garde-fou d'interface et non un invariant"
  - "`resume_des_droits` passe par `acces_pour` plutot que par un comptage SQL : la liste ne peut donc pas afficher autre chose que ce que le compte obtient, et il n'y a pas de seconde branche proprietaire a tenir"
  - "`catalogue` rejoint RENDUS : le test de conformite parametre lit desormais le registre par l'autre bout, ce que 03-UI-SPEC 7.7 demande nommement"
patterns-established:
  - "Toute route d'ecriture de compte force le `client` depuis `request.acces`, jamais depuis le corps"
  - "Tout nouveau champ de modele expose rejoint CHAMPS_PUBLICS ou CHAMPS_PROTEGES dans le meme commit (is_active et last_login, ici)"
  - "Une reponse d'action porte l'etat reconstruit de ce qu'elle a change, pas seulement un 200"
requirements-completed: []
duration: ~85 min
completed: 2026-09-16
---

# Phase 3 Plan 09 : la surface d'écriture des comptes et des droits — Summary

**Neuf points de terminaison sous `/api/comptes/`, une règle d'octroi qui vit dans un
service appelable sans HTTP, une cascade de prérequis appliquée dans les deux sens côté
serveur, et un catalogue dont les codes non détenus sont absents du fil — pas grisés,
pas filtrés dans le navigateur : absents.**

## Performance

- **Durée :** ~85 min
- **Tâches :** 3 sur 3
- **Fichiers :** 1 créé, 7 modifiés — 2 358 lignes ajoutées
- **Suite :** 148 → **162** tests rapides au vert ; **192 passed** suite complète
  (`slow` compris). Les `pending` de ce plan passent de 3 à **0** ;
  `tests/test_comptes_droits.py` n'en porte plus aucun.

## Task Commits

1. **Tâche 1 : création et désactivation d'un compte gérant** — `49b1c72` (feat)
2. **Tâche 2 : octroi par magasin, cascade côté serveur, journal** — `82c3242` (feat)
3. **Tâche 3 : le catalogue servi déjà intersecté** — `c4f7357` (feat)
4. Reformulation d'une docstring pour le critère `supprimer` — `4448dac` (chore)

Chaque commit nomme explicitement ses chemins (`git commit -F - -- <chemins>`).

---

## Le contrat de réponse d'une bascule — ce que le plan 03-14 doit lire

C'est la raison d'être de cette section : l'écran de droits **n'a pas de bouton
Enregistrer** (`03-UI-SPEC.md` 7.8), donc chaque interrupteur écrit immédiatement et
redessine sa ligne depuis la réponse. Si cette réponse ne suffit pas, « sauvegarde
immédiate » veut dire « recharge la page », et l'écran devient ce que 7.8 refuse.

Les trois routes de bascule — `droits/`, `droits/uniformiser/`, `magasins/` — rendent
**la même forme** :

```json
{
  "code": "caisse.saisir",
  "action": "accorde",
  "lignes": [
    { "code": "caisse.saisir", "etat": "mixte",  "magasins": ["ANFA"] },
    { "code": "caisse.voir",   "etat": "mixte",  "magasins": ["ANFA"] }
  ],
  "cascade": ["caisse.voir"],
  "magasins_accordes": ["ANFA", "MAARIF"],
  "magasins_etendus": []
}
```

| Champ | Ce que l'interface en fait |
|---|---|
| `lignes` | redessine **chaque** interrupteur touché, le demandé en tête puis la cascade |
| `etat` | `actif`, `inactif` ou **`mixte`** — le tri-état, `aria-checked="mixed"` |
| `magasins` | le numérateur de « Personnalisé : 2 magasins sur 3 » |
| `magasins_accordes` | son dénominateur |
| `cascade` | la note en ligne (« … a été activé automatiquement ») **et** le toast d'annulation unique qui couvre tout l'ensemble |
| `magasins_etendus` | la note « Californie a été ajouté. Vérifiez les 2 droits personnalisés. » |

**« Uniforme » veut dire « tous les magasins accordés sont d'accord »**, donc `actif` et
`inactif` sont tous deux uniformes et `mixte` est l'unique état personnalisé. C'est
exactement la définition de 7.5, et elle est celle du serveur : l'interface ne recalcule
rien.

**`cascade` existe comme liste séparée alors qu'elle est dérivable de `lignes`**, et
c'est délibéré : l'interface en fait deux choses que `lignes` ne distingue pas — une note
par ligne emportée, et **un seul** toast d'annulation. Un `Annuler` par code produirait
trois toasts pour une seule action de l'utilisateur.

### Les trois bascules

| Route | Corps | Effet |
|---|---|---|
| `POST /api/comptes/{id}/droits/` | `{code, accorde, magasins?}` | `magasins` absent = **tous les magasins accordés**, le comportement uniforme par défaut |
| `POST /api/comptes/{id}/droits/uniformiser/` | `{code, accorde}` | aligne tous les magasins sur une valeur — le bouton `Uniformiser` |
| `POST /api/comptes/{id}/magasins/` | `{magasin_code, accorde}` | accorde ou retire l'accès, avec ses effets de bord ci-dessous |

Une seule route par interrupteur, avec un booléen, plutôt que deux routes opposées : à
l'écran c'est **un seul contrôle**, et une interface qui devrait choisir sa route à
chaque clic finit par se tromper de sens sur le chemin d'erreur.

---

## Les trois règles que le serveur applique et que l'interface se contente d'expliquer

### 1. La fermeture des prérequis, dans les deux sens

`03-UI-SPEC.md` 7.6 l'écrit en toutes lettres — « la note de l'interface est une
explication, pas la règle » — et c'est une phrase qu'il est facile de lire en diagonale.
Elle est appliquée dans `plateforme/comptes/services.py` :

- accorder `stock.ajuster` accorde `stock.voir`, transitivement (`fermeture_prerequis`) ;
- révoquer `stock.voir` révoque `stock.ajuster`, transitivement (`dependants`).

Un `curl` obtient donc exactement le résultat d'un clic (menace T-03-61).

**Et la cascade n'est pas une porte de service.** L'appelant doit détenir **chaque** code
de la fermeture, pas seulement celui qu'il demande : sans cela, un gérant-gestionnaire
qui ne détient pas `article.voir_prix_achat` l'accorderait indirectement en accordant
`vente.voir_marge`. Le refus porte sur l'octroi **entier** plutôt que de le servir à
moitié — un octroi partiel serait un état que ni l'interface ni le journal ne savent
décrire.

### 2. Un magasin ajouté étend les lignes uniformes, et **jamais** les personnalisées

C'est la règle de 7.5 la plus facile à écrire de travers, et son mode de défaillance est
une élévation silencieuse : le propriétaire avait délibérément refusé `caisse.saisir` à
Maârif, il ajoute Californie six mois plus tard pour une raison sans rapport, et
l'extension automatique lui accorde à Californie le droit qu'il avait refusé (menace
T-03-62).

Le calcul est fait sur l'état **d'avant** l'ajout, ce qui est le détail d'implémentation
qui décide de la correction : calculé après, le magasin qu'on vient d'ajouter rend toute
ligne mixte et plus rien ne s'étend jamais.

Le retrait est symétrique et emporte les droits qui visaient ce magasin, ce que le
dialogue de 7.9 annonce mot pour mot. La raison de le faire vraiment est la menace
T-03-18 : une ligne laissée derrière est inerte aujourd'hui et **redevient active** le
jour où le magasin est réaccordé.

### 3. On ne donne que ce qu'on détient, code par code et magasin par magasin

`compte.gerer` sans cette règle serait un droit d'auto-promotion par procuration, et le
chemin tient en quatre gestes : créer un compte, lui accorder `article.voir_prix_achat`,
s'y connecter (on en a posé le mot de passe), lire les marges. Le service refuse hors de
l'intersection des droits **et** des magasins de l'appelant, en interrogeant
`peut(code, magasin_id)` — la question précise, jamais l'union.

---

## L'union propose, la conjonction dispose

Ce plan est le **second et dernier** appelant sanctionné de `peut_quelque_part`, étiquette
`catalogue`. La séparation mérite d'être écrite parce que les deux appels sont à quelques
lignes l'un de l'autre dans le même fichier :

| Question | Outil | Où |
|---|---|---|
| « cette case a-t-elle un sens pour lui ? » | `peut_quelque_part` (union) | `catalogue_offrable` |
| « a-t-il le droit d'accorder ceci, ici ? » | `peut(code, magasin_id)` | `services._verifier_le_pouvoir` |

Un gérant qui détient `article.voir_prix_achat` à Anfa doit voir la case — sinon il ne
peut pas l'accorder à un collègue d'Anfa, ce qu'il a pourtant le droit de faire. Mais la
case visible ne l'autorise à rien : le refus par magasin est appliqué à l'octroi. Le
garde source de `tests/test_magasin_acces.py` accepte exactement deux étiquettes, et les
deux sont maintenant prises — un troisième appelant est rouge à la seconde où il est
écrit, non parce qu'il déborde un compteur mais parce qu'il n'a plus d'étiquette libre.

---

## Le catalogue intersecté, et pourquoi il est dans `RENDUS`

`03-UI-CHECK.md` finding 2 est la seule recommandation de fond de la revue d'interface, et
elle tient en une phrase : « absent, pas désactivé » est **mécanique** pour les champs
(§8.3) et n'était qu'une **convention** pour l'écran de droits (§7.7). Elle cesse de
l'être ici.

`GET /api/comptes/catalogue/` sert à chaque appelant les droits qu'il peut accorder et les
magasins qu'il détient. L'intersection est faite **avant** la sérialisation :

- un code non détenu est **absent du JSON**, pas grisé, pas filtré côté client ;
- les magasins non détenus sont absents — un menu qui les nommerait serait une
  énumération ;
- la carte des prérequis est restreinte aux codes visibles **des deux côtés** : une entrée
  nommant un code absent réintroduirait par la porte de service ce que l'intersection
  retire ;
- une section vide n'est pas servie. Un titre sans ligne dirait « il y a des droits ici,
  mais pas pour vous » — le grisage, en typographie.

Le test affirme sur `rendered_content`, c'est-à-dire sur les **octets**. Une assertion sur
`reponse.data` laisserait passer un filtrage appliqué au rendu, qui est exactement le mode
de fuite que la recommandation existe pour fermer.

**Deux catalogues coexistent, et les confondre serait une régression silencieuse :**

| Route | Question | Réponse |
|---|---|---|
| `/api/auth/moi/` (03-08) | quels droits **existent** ? | les 21, identiques pour toute la flotte |
| `/api/comptes/catalogue/` | lesquels **puis-je accorder** ? | l'intersection, propre à l'appelant |

### `catalogue` est le quatrième rendu du test de conformité

`03-UI-SPEC.md` 7.7 le demande nommément : « The same parametrized conformance test that
covers field projection covers this catalogue. » `RENDUS` passe donc de trois à quatre.

Il n'est pas un rendu de *champ* comme les trois autres — il ne sert pas une ressource —
mais **il lit le même registre par l'autre bout** : une clé de `CHAMPS_PROTEGES` nomme un
champ, sa valeur nomme le code qui le garde, et un éditeur qui ne détient pas ce code ne
doit pas le lire dans son catalogue. Une ligne ajoutée au registre en phase 8 produit donc
désormais **quatre** assertions au lieu de trois, sans qu'aucun développeur n'y pense.

---

## Ce que la permission ne fait pas, et pourquoi c'est le bon choix

`PeutGererLesComptes` lit `acces.peut(Permission.COMPTE_GERER)`. **Il n'y a pas de
`or acces.est_proprietaire`**, et c'est la décision la plus contre-intuitive du plan.

Le propriétaire passe quand même : son accès est **matérialisé** depuis le plan 03-05 — le
catalogue complet, pour chacun de ses magasins actifs — donc il emprunte le même chemin
qu'un gérant à qui tout aurait été accordé à la main. Écrire la branche rouvrirait
précisément le second chemin de code que 03-05 a fermé, et une branche qui saute la
vérification pour un propriétaire est une branche qu'un bug peut atteindre pour un
non-propriétaire (`03-RESEARCH.md` P3).

**Deux conséquences sont assumées et écrites plutôt que découvertes :**

1. `peut()` sans magasin étant une **conjonction**, un gérant doit détenir `compte.gerer`
   dans *tous* ses magasins pour atteindre cette surface. Administrer des comptes n'est
   pas une action de magasin, l'union n'autorise jamais rien, et le sens de l'erreur est
   fail-closed.
2. Un propriétaire dont l'affaire n'a **aucun magasin actif** est refusé ici. Il l'est
   déjà partout ailleurs — `Acces` ne lui résout alors aucun droit — et un cas particulier
   masquerait une affaire à moitié provisionnée au lieu de la signaler.

---

## Rouge → vert

| Test | Rouge, pour quelle raison | Vert |
|---|---|---|
| `..._un_proprietaire_ne_cree_un_compte_que_dans_son_propre_client` | `404` : aucune route `/api/comptes/` | après `VueComptes` (tâche 1) |
| `..._la_suppression_dun_compte_nexiste_nulle_part` | idem | idem |
| `..._seul_un_appelant_habilite_atteint_la_gestion_des_comptes` | idem | après `PeutGererLesComptes` |
| `..._le_mot_de_passe_provisoire_nest_montre_quune_seule_fois` | idem | après `mot_de_passe_provisoire` et `CompteCreeSerializer` |
| `test_perm06_tout_champ_de_modele_expose_est_classe` (03-06) | `is_active` et `last_login` non classés | après les deux lignes de `CHAMPS_PUBLICS` |
| `..._un_octroi_ecrit_une_ligne_par_magasin_accorde` | `ImportError` : pas de `services.accorder` | après `accorder` / `revoquer` (tâche 2) |
| `..._la_cascade_des_prerequis_est_appliquee_cote_serveur` | idem | après `fermeture_prerequis` / `dependants` dans le service |
| `..._un_magasin_ajoute_etend_les_lignes_uniformes_et_pas_les_personnalisees` | idem | après `accorder_magasin` / `retirer_magasin` |
| `..._un_gerant_gestionnaire_ne_donne_que_ce_quil_detient` | idem | après `_verifier_le_pouvoir` |
| `..._la_revocation_par_lapi_prend_effet_sans_reconnexion` | `404` sur `/droits/` | après l'action `droits` |
| `..._un_proprietaire_ne_peut_pas_accorder_a_un_utilisateur_dun_autre_client` | `pending` depuis 03-02 | après `_verifier_la_cible` |
| `..._le_service_journalise_chaque_octroi_et_chaque_revocation` | vérifié par mutation (journal retiré de `_poser`) | rouge à la mutation, vert sans |
| `..._les_trois_bascules_repondent_le_contrat_de_lecran_de_droits` | `404` sur `/droits/uniformiser/` | après les trois actions |
| `..._le_catalogue_servi_a_un_gerant_manager_est_deja_intersecte` | `pending` depuis 03-02 | après `catalogue_offrable` + `VueCatalogue` (tâche 3) |
| `..._champ_protege_absent_...[catalogue]` (nouveau cas) | `ImportError: catalogue_offrable` | idem |

---

## Critères d'acceptation, tels qu'exécutés

### Tâche 1

| Critère | Résultat |
|---|---|
| aucun champ d'élévation en **entrée** de `serializers.py` | **satisfait** — les occurrences restantes sont des sorties et de la prose ; les sérialiseurs d'écriture sont des `Serializer` nus |
| `grep -c 'acces.client_id' views.py` ≥ 1 | **3** |
| `grep -ci 'def destroy\|DestroyModelMixin\|supprimer' views.py` → 0 | **0** — voir déviation 1 |
| `grep -c 'doit_changer_mot_de_passe' views.py` ≥ 1 | **7** |
| `pytest -k "propre_client or suppression or provisoire"` | **3 passed** |
| `<verify>` (`… or 403`) | **4 passed** |

### Tâche 2

| Critère | Résultat |
|---|---|
| `grep -c 'fermeture_prerequis' services.py` ≥ 1 | **3** |
| `grep -c 'dependants' services.py` ≥ 1 | **2** |
| `grep -c 'JournalDroit' services.py` ≥ 2 | **13** |
| `grep -c 'def accorder\|def revoquer\|def uniformiser' services.py` → 3 | **4** — voir déviation 2 |
| `pytest -k "revocation or journal or autre_client or cascade or uniforme"` | **passed** |
| `grep -c 'pytest.mark.pending' tests/test_comptes_droits.py` → 0 | **0** |
| `<verify>` : `pytest tests/test_comptes_droits.py -x -q` | **21 passed** |

### Tâche 3

| Critère | Résultat |
|---|---|
| `grep -c 'peut_quelque_part' views.py` ≥ 1 | **1** — mais c'est de la prose ; voir déviation 3 |
| `grep -c 'catalogue' urls.py` → 1 | **1** |
| `pytest tests/test_projection.py -k catalogue`, contrôle positif inclus | **2 passed** |
| un test affirme que le JSON brut ne contient pas `article.voir_prix_achat` | **oui**, sur `rendered_content` |
| `spectacular --fail-on-warn` → 0 | **exit 0** |

### Vérification du plan

| Critère | Résultat |
|---|---|
| `pytest tests/test_comptes_droits.py -q`, aucun `pending` | **21 passed, 0 pending** |
| `pytest tests/test_projection.py -q -k catalogue` | **2 passed** |
| `spectacular --fail-on-warn` | **exit 0** |
| `manage.py check` | **no issues (0 silenced)** |
| `pytest -x -q -m "not slow and not pending"` | **vert** |
| `pytest -q` (tout, `slow` compris) | **192 passed**, 6 échecs appartenant à d'autres plans (`test_locale.py` ×5, `test_schema_contrat.py` ×1 — plan 03-10) |
| `grep -rni 'supprimer' plateforme/comptes/` | **4 lignes**, aucune de ce plan — voir déviation 1 |

---

## Déviations du plan

### 1. [signalé] `grep -rni 'supprimer' plateforme/comptes/` ne peut pas retourner zéro, et ne doit pas

Quatre occurrences subsistent, **toutes** de la prose des plans 03-01 et 03-04 :

| Fichier | Ce que la phrase dit |
|---|---|
| `models.py:58` | `PROTECT` : supprimer un client dont des comptes dépendent doit échouer |
| `models.py:351` | `PROTECT` : supprimer un compte dont le journal parle doit échouer |
| `acces.py:202` | les magasins se désactivent sans jamais se supprimer |
| `permissions_catalogue.py:243` | la classe d'appels que la carte des prérequis existe pour supprimer |

Une cinquième existait, et c'était la seule de ce plan : elle a été reformulée (`4448dac`).
Les quatre restantes disent toutes **l'inverse** de ce que le critère veut interdire —
elles expliquent pourquoi une suppression est refusée. Les réécrire pour satisfaire un
`grep` appauvrirait des docstrings qui portent le raisonnement d'une contrainte de base.

Et une cinquième, inaccessible : `EXPLICATIONS[FACTURE_AVOIR]` contient « Une facture
n'est jamais supprimée, elle est compensée », qui est de la **copie d'interface** affichée
au propriétaire. Elle ne peut pas être reformulée sans changer ce que l'écran dit.

La règle réelle de `03-UI-SPEC.md` 7.8 est plus étroite que le critère : « There is no
`Supprimer` in the account UI and the word never appears ». Elle porte sur les **libellés
et les routes** de l'écran de comptes, pas sur les commentaires de code d'un autre plan.
Le test livré affirme donc la règle réelle — 405, pas d'action `destroy`, pas de mixin de
retrait dans le MRO — et le critère grepable est satisfait dans `views.py`, où il a du
sens.

C'est le sixième critère de cette phase à correspondre à sa propre prose plutôt qu'au
fichier livré (03-04 en a signalé deux, 03-05 un, 03-06 un, 03-07 un).

### 2. [signalé] `grep -c 'def accorder\|def revoquer\|def uniformiser'` retourne 4, pas 3

Le critère compte trois définitions ; le même plan en demande **cinq** dans son action
(`accorder`, `revoquer`, `uniformiser`, `accorder_magasin`, `retirer_magasin`). Le motif
`def accorder` capture aussi `def accorder_magasin`, d'où 4. Le compte est bon, le motif
est incomplet. Un critère durable s'écrirait `def accorder(`, avec la parenthèse.

### 3. [signalé] `peut_quelque_part` est appelé depuis `serializers.py`, pas depuis `views.py`

Le critère demande au moins une occurrence dans `views.py`, et il y en a une — mais c'est
une phrase de docstring, pas le site d'appel. L'appel vit dans
`serializers.py:catalogue_offrable`, **à côté de son jumeau** : le premier usage
sanctionné, étiquette `navigation`, est `charge_utile_moi`, dans le même fichier, posé par
le plan 03-08. Les deux constructeurs de charge utile sont donc lisibles l'un au-dessus de
l'autre, ce qui est exactement ce qu'on veut d'une échappatoire gardée par une énumération
de deux entrées.

Le garde source de `tests/test_magasin_acces.py` ne regarde pas le fichier : il parcourt
tout `plateforme/` et exige une étiquette. Il passe, avec ses deux étiquettes prises.

### 4. [Rule 3 — bloquant] `is_active` et `last_login` rejoignent `CHAMPS_PUBLICS`

Non listé dans `files_modified`, et conséquence directe du choix `ModelSerializer` pour
`CompteSerializer` : `test_perm06_tout_champ_de_modele_expose_est_classe` rougit sur tout
champ de modèle exposé et non classé. Observé, pas anticipé — la suite est devenue rouge
au moment où la liste de comptes a servi son premier statut.

C'est le geste que la docstring du registre prévoit (« les phases 4 à 10 la remplissent au
fur et à mesure, dans le même commit que leurs sérialiseurs »), et le commentaire écrit à
côté nomme les deux décisions plutôt que de les laisser passer pour un défaut :
`last_login` est une donnée de présence sur un collègue, publiée parce qu'un propriétaire
qui se demande si un compte sert encore n'a pas d'autre réponse ; `derniere_connexion_ip`
reste **non classé**, donc refusé.

### 5. [Rule 3 — bloquant] `config/urls.py` monte un second préfixe

Non listé dans `files_modified`. `include()` prend l'attribut `urlpatterns` d'un module,
donc servir deux préfixes depuis `plateforme/comptes/urls.py` demande une seconde liste
nommée et importée explicitement. Trois lignes, aucune règle touchée.

### 6. [Rule 3] Le service leve les exceptions de Django, et la vue les traduit

DRF convertit `django.core.exceptions.PermissionDenied` en 403 — en conservant le message
— mais **pas** `django.core.exceptions.ValidationError`, qui remonterait en **500** avec
sa trace en développement. Le service doit rester appelable par une commande de gestion,
donc il lève les exceptions de Django ; la traduction vit dans un gestionnaire de contexte
de trois lignes, `_erreurs_de_service`, à la frontière HTTP et nulle part ailleurs.

### 7. [Rule 2 — fonctionnalité critique manquante] La cible d'une gestion n'est ni le propriétaire ni soi-même

Le plan ne le demande pas ; `03-UI-SPEC.md` 7.7 le dit ligne par ligne, et l'absence
ouvrait deux élévations directes :

- un gérant-gestionnaire **réinitialise le mot de passe du propriétaire** et prend son
  compte — le point de terminaison de réinitialisation le lui rend en clair ;
- un gérant-gestionnaire **révoque ses propres** contraintes, ou s'octroie ce qu'il
  détient déjà ailleurs, en se prenant lui-même pour cible.

La règle est écrite une fois, dans `_refuser_si_non_gerable` (vue) et
`_verifier_la_cible` (service), et les deux couches ne se remplacent pas : la vue refuse
avant d'agir, le service refuse même appelé sans HTTP.

La modification de l'identité suit la même table : le propriétaire corrige la sienne, un
gérant-gestionnaire ne corrige pas la sienne (il n'a que son mot de passe, par
`/api/auth/mot-de-passe/`), et personne ne touche à la fiche du propriétaire à sa place.

### 8. [Rule 2] L'adresse e-mail déjà prise ne confirme pas qu'un compte existe

L'adresse de connexion est unique sur toute la flotte (CLAUDE.md #11). Le message par
défaut de Django — « un utilisateur avec cette adresse existe déjà » — dirait à un
opticien qu'un compte existe chez un concurrent, c'est-à-dire le même oracle d'énumération
que la vue de connexion refuse d'être (T-03-48). Le message livré est
« Cette adresse e-mail n'est pas disponible. »

**Le résidu est admis et écrit** : le refus lui-même apprend que l'adresse est prise
*quelque part*, et il est inévitable puisque la création doit échouer. Ce qui est évitable
est de nommer la cause. Il faut de plus être authentifié et détenir `compte.gerer` pour
poser la question, donc ce n'est pas un oracle ouvert.

### 9. [Rule 2] Le mot de passe provisoire fourni passe par `AUTH_PASSWORD_VALIDATORS`

Le plan demande un mot de passe généré ; `03-UI-SPEC.md` 7.2 montre un **champ** avec un
bouton `Générer`, donc l'appelant peut en fournir un. Un mot de passe posé par un tiers
n'a aucune raison d'échapper à la politique — au contraire : c'est celui que le gérant
recevra. Même chemin que `ChangementMotDePasseSerializer` (plan 03-08), comme la note de
ce plan-là le demandait.

### 10. [signalé] Le dernier magasin n'est pas refusé côté serveur, et c'est une décision

`03-UI-SPEC.md` 7.3 B refuse en ligne le décochage du dernier magasin. La règle **n'est
pas** appliquée par le serveur, pour une raison qui se vérifie dans la spécification
elle-même : un compte fraîchement créé n'a légitimement aucun magasin (7.2 : « la route va
droit au détail parce qu'un compte neuf n'a ni droit ni magasin »). « Au moins un » n'est
donc pas un invariant du modèle — zéro est un état atteignable et normal — mais un
garde-fou d'interface.

Le contourner produit un compte qui résout `Acces` sans aucun magasin, c'est-à-dire qui ne
voit rien : fail-closed, sans conséquence à fermer côté serveur. L'appliquer aurait créé
l'incohérence inverse — zéro atteignable par la création, interdit par le retrait.

### 11. [signalé] `test_perm03_la_revocation_prend_effet_sans_reconnexion` n'a pas été réécrit

Le plan nomme ce test pour la tâche 2 ; il existe et il est **vert depuis le plan 03-05**,
au niveau de la résolution — c'est là, et seulement là, qu'un `lru_cache` ou un `Acces`
posé en session se verrait. Le comportement que le plan décrit — « révoquer, puis la
requête suivante du gérant, sans nouvelle connexion » — demande deux vraies requêtes HTTP,
donc il est livré comme un test **distinct** :
`test_perm03_la_revocation_par_lapi_prend_effet_sans_reconnexion`, avec la docstring qui
dit pourquoi il échouerait sous un jeton porteur. Les deux moitiés sont nécessaires et se
citent mutuellement.

Même arbitrage pour le journal : `..._qui_a_accorde_quoi_et_quand` reste le test du
modèle, et `..._le_service_journalise_chaque_octroi_et_chaque_revocation` est la moitié
service.

### 12. [signalé] Deux tests de la tâche 2 ont été écrits après leur implémentation

`..._le_service_journalise_chaque_octroi_et_chaque_revocation` et
`..._les_trois_bascules_repondent_le_contrat_de_lecran_de_droits` ont été ajoutés après
coup, pour couvrir des comportements que les tests écrits d'abord ne fixaient pas (l'ordre
et l'acteur du journal ; la forme exacte de la réponse, dont dépend le plan 03-14). Ils
n'ont donc jamais été rouges par construction.

Plutôt que de le taire, le premier a été **éprouvé par mutation** : en retirant l'écriture
du journal de `_poser`, il devient rouge et l'autre reste vert. C'est une vérification
plus faible que le rouge d'origine, et elle est signalée comme telle.

### 13. [signalé] `REQUIREMENTS.md` n'est pas coché

Même arbitrage qu'aux plans 03-05, 03-06 et 03-07. **PERM-02** et **PERM-03** ont leur
moitié API ici ; leur moitié interface est le plan **03-14**, qui n'existe pas encore.
**PERM-06** attend sa vérification vivante en phase 8, quand `prix_achat` et `marge`
seront des colonnes. Cocher ici dirait au verrou de phase que l'exigence est faite alors
que son écran n'a pas une ligne.

`state advance-plan` n'a pas été exécuté non plus : CLAUDE.md l'interdit en vague
parallèle, et la progression est recalculée depuis les résumés sur disque.

---

**Total des déviations :** 13 — 6 signalements sans changement de code, 3 déblocages
(Rule 3), 3 fonctionnalités critiques manquantes (Rule 2), 1 décision de traçabilité.
Aucune n'élargit le périmètre du plan ; les trois ajouts Rule 2 servent tous une ligne
déjà écrite dans `03-UI-SPEC.md` 7.7 ou une menace déjà au registre.

---

## Ce qui coûte, et qui est assumé

**`resume_des_droits` fait une résolution complète par ligne de tableau.** Trois requêtes
par compte listé, parce qu'il passe par `acces_pour` plutôt que par une agrégation SQL. Le
bénéfice est qu'il n'existe pas de seconde vérité : la liste ne peut pas afficher un
nombre de droits que le compte n'obtient pas, et il n'y a pas de branche « propriétaire »
à maintenir en double. Le coût est borné — une affaire compte une poignée de comptes — et
un cache de contexte évite que les trois champs qui le lisent le résolvent trois fois.

Si une affaire atteignait la centaine de comptes, la forme à écrire serait une agrégation
qui réintroduirait la branche du propriétaire ; ce jour-là, il faudra un test qui compare
les deux chemins plutôt qu'un remplacement.

---

## Known Stubs

Aucun. Les neuf points de terminaison sont complets, servis et testés ; rien ne rend une
valeur vide ni un texte d'attente vers une interface.

Deux **absences délibérées**, ni l'une ni l'autre n'étant un stub :

1. **Le propriétaire ne modifie pas son propre statut ni son propre mot de passe ici** —
   le second passe par `/api/auth/mot-de-passe/` (plan 03-08), et un propriétaire qui
   oublie le sien est réinitialisé par l'opérateur via l'admin. C'est la conséquence de
   l'absence de fournisseur d'e-mail, déjà consignée par le plan 03-08.
2. **L'historique des droits (`03-UI-SPEC.md` 7.3 D) n'a pas de point de terminaison.**
   `JournalDroit` est écrit par le service et lisible, mais le `collapsible` de la fiche
   n'a pas encore de route pour l'alimenter. Elle appartient au plan qui construit l'écran
   (03-14) et se réduit à une liste filtrée sur `utilisateur`, ordonnée par `-le`, servie
   derrière la même permission. Écrit ici pour que 03-14 ne le redécouvre pas.

## Threat Flags

| Flag | Fichier | Description |
|------|---------|-------------|
| threat_flag: enumeration | `plateforme/comptes/serializers.py` | `CreationCompteSerializer.validate_email` refuse une adresse déjà prise **ailleurs dans la flotte**. Le message ne nomme pas la cause, mais le refus lui-même est un oracle d'existence, borné aux appelants authentifiés détenant `compte.gerer`. Inhérent à l'adresse de connexion unique de CLAUDE.md #11 ; accepté et documenté plutôt que masqué. |

Aucun rôle, aucune base et aucune fonction `SECURITY DEFINER` n'est ajouté : CLAUDE.md #12
ne s'applique pas. Les neuf routes nouvelles vivent toutes derrière
`IsAuthenticated + PeutGererLesComptes`.

## Notes pour les plans suivants

- **03-10** commite le schéma : **neuf opérations** et sept composants nouveaux y entrent
  (`Compte`, `CompteCree`, `CreationCompte`, `ModificationIdentite`, `Statut`,
  `BasculeDroit`, `BasculeMagasin`, `Uniformisation`, `ResultatOctroi`,
  `CatalogueOffrable`). `spectacular --fail-on-warn` est à zéro aujourd'hui.
- **03-14** construit l'écran contre le contrat de réponse décrit en tête de ce résumé.
  Les quatre champs `lignes` / `cascade` / `magasins_accordes` / `magasins_etendus` sont
  fixés par un test nommé ; les renommer rend la suite rouge.
- **03-14** devra aussi ajouter la route de l'**historique des droits** (7.3 D), qui
  n'existe pas — voir « Known Stubs ».
- **Phase 8** : une ligne dans `CHAMPS_PROTEGES` produit désormais **quatre** assertions,
  et la quatrième est le catalogue. Si le champ ajouté est gardé par un code que l'écran
  de droits doit offrir, elle passe toute seule ; sinon elle dira lequel.
- **Phase 12** : l'inscription en libre service appelle `plateforme.comptes.services` et
  non les vues. `accorder` et `accorder_magasin` prennent un `par` qui doit être un
  principal réel — le journal en dépend, et `accorde_par` est en `PROTECT`.

## Self-Check

`plateforme/comptes/services.py` est présent sur le disque (578 lignes) ; les sept
fichiers modifiés portent leurs changements ; les quatre commits existent dans
`git log` : `49b1c72`, `82c3242`, `c4f7357`, `4448dac`. Suite re-exécutée après le dernier
commit : **192 passed**, 6 échecs appartenant nommément à d'autres plans.

---
*Phase : 03-comptes-permissions-app-shell*
*Terminé : 2026-09-16*

## Self-Check: PASSED

Neuf chemins vérifiés présents sur le disque, quatre commits présents dans `git log`.
Vérifié après rédaction du résumé, pas avant.
