---
phase: 04-clients-ordonnances
plan: 05
status: complete
completed: 2026-09-18
requirements-completed: []
tasks: 3
autonomous: true
---

# 04-05 — le versionnement de l'ordonnance et les deux premières entrées du registre

## Ce que ce plan livre

CLIENT-06 : une nouvelle ordonnance est une **nouvelle version**, toutes les précédentes
restent lisibles **exactement telles qu'elles ont été saisies**, et aucune route ne modifie
ni ne supprime. Plus les deux premières entrées réelles de `CHAMPS_PROTEGES`, qui était vide
depuis le début du projet.

## Commits

| Commit | Contenu |
|---|---|
| `4a35e3d` | test — le versionnement et le résumé protégé, rouges d'abord |
| `ebfc06b` | feat — le versionnement sous verrou, et une surface sans modification |
| `96e52a6` | feat — les deux entrées du registre, le test porteur corrigé, schéma et client régénérés |

Chemins nommés à chaque commit, aucune mention de Claude.

## Portes, relevées à la clôture

| Porte | Relevé |
|---|---|
| `pytest -q -m "not slow"` | **264 passed, 33 deselected** |
| `npm --prefix web test` | **160 passed** |
| `npm --prefix web run build` | **exit 0** |
| `manage.py check` | **0 issues** |
| `spectacular --fail-on-warn` | **exit 0**, et le fichier commité est identique au servi |

Ligne de base à l'ouverture : backend 249, web 160.

## Le piège que ce plan existait pour désamorcer

`tests/test_projection.py` lisait :

```python
return sorted(CHAMPS_PROTEGES.items()) or [CHAMP_DE_REPLI]
```

`CHAMPS_PROTEGES` étant **vide depuis la phase 3**, la parametrisation du test porteur
tournait en réalité sur la ressource de fixture. **La première entrée réelle — c'est-à-dire
ce plan — aurait fait sortir ce cas de la parametrisation sans qu'aucune assertion ne
rougisse.** Quatre assertions auraient disparu en silence, et la suite serait restée verte
en couvrant strictement moins.

Corrigé en **concaténation dédupliquée** :

```python
return list(dict.fromkeys(sorted(CHAMPS_PROTEGES.items()) + [CHAMP_DE_REPLI]))
```

**Vérifié par un compte, pas par une impression**, comme le plan l'exigeait :

| Mesure | Valeur |
|---|---|
| Identifiants de nœud portant encore le sujet de fixture | **4** |
| Tests collectés dans `tests/test_projection.py` | **29** |
| Entrées réelles du registre | **2** |

`_sujet_pour` a été généralisée pour rendre la valeur attendue plutôt que d'affirmer contre
la constante de la fixture — sans quoi les deux nouvelles clés auraient comparé un vrai
résumé clinique à `VALEUR_PROTEGEE`.

## Les deux entrées, et pourquoi elles arrivent ici

```
clients.Client.derniere_ordonnance -> ordonnance.voir
clients.Client.resume_ordonnance   -> ordonnance.voir
```

Le plan 03-06 avait désigné la **phase 8** (`prix_achat`) comme premier client du registre.
Les ordonnances sont arrivées avant. `04-UI-SPEC.md` §15.5 tranche la zone grise 5 : la
fiche client porte un résumé de prescription, donc ce résumé est un **champ protégé sur un
objet visible** — la forme que le registre traite — et non une ligne à filtrer.

**La moitié cliente n'ajoute aucune branche.** `colonnesVisiblesSurLignes` gère déjà la
présence, et c'est exactement ce que la conception de la phase 3 promettait : le serveur
retire la clé, le client ne décide rien.

## Le contrat d'API a été régénéré parce qu'un test l'a exigé

Après les entrées du registre, `test_perm06_le_schema_servi_est_identique_pour_chaque_appelant`
et le test du contrat sont passés au rouge : les nouvelles routes
`/clients/{client_id}/ordonnances/` n'étaient pas dans le fichier commité. Le message du test
dit quoi faire et pourquoi il existe. Schéma et client TypeScript régénérés **dans le commit
de la cause**, pas dans un commit de rattrapage.

C'est la porte qui a signalé l'oubli — pas une relecture.

## Comment ce plan s'est terminé

**L'agent d'exécution s'est arrêté deux fois** : une première fois après `4a35e3d` avec 701
lignes non commitées, repris depuis son propre transcript pour ne pas perdre son
raisonnement ; une seconde fois après `ebfc06b`, avec `registre.py` et `test_projection.py`
modifiés mais non commités. **L'orchestrateur a terminé la tâche 3** — vérification, schéma,
commit, ce résumé.

Rien n'a été réécrit et rien n'a été perdu. Aucun second agent n'a été lancé sur les mêmes
fichiers, conformément à la leçon consignée en phase 03.1 : le coût de deux agents sur un
même plan n'est pas le double travail, c'est le document contradictoire.

## Exigences : aucune cochée

CLIENT-06 a ici sa moitié serveur ; son écran d'historique est `04-09`. Précédent du projet
tenu depuis les plans 03-05 à 03-10 : une case cochée signifie qu'un opticien peut le faire.
CLIENT-02 n'est pas cochable en phase 4 — l'historique d'achats suppose les ventes, phase 6.

## Self-Check

- [x] Les trois tâches livrées, test-first
- [x] Le cas de fixture toujours exercé, prouvé par un compte (4 nœuds, 29 tests)
- [x] Les deux clés du registre ont leur sujet dans `_sujet_pour`
- [x] Aucune route de modification ni de suppression sur une ordonnance
- [x] Schéma et client régénérés dans le commit de la cause
- [x] Portes relevées, pas recopiées
- [x] `state advance-plan` non exécuté ; rien fusionné vers `main`
