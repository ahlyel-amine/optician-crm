---
phase: 04-clients-ordonnances
plan: 08
status: PARTIEL — tâche 1 sur 3
completed: null
requirements-completed: []
---

# 04-08 — état partiel, à reprendre

**Ce plan n'est pas terminé.** La tâche 1 est livrée et vérifiée ; les tâches 2 et 3 n'ont
pas commencé. Ce document existe pour que la reprise parte d'un état connu plutôt que d'une
inspection.

## Ce qui est fait — commit `f633041`

Les quatre modules **sans rendu**, et leurs tests :

| Fichier | Lignes | Rôle |
|---|---|---|
| `web/src/pages/clients/ordonnances/verifier.ts` | 769 | les onze avertissements et les refus |
| `web/src/pages/clients/ordonnances/messages.ts` | 291 | la copie, en constantes nommées |
| `web/src/pages/clients/ordonnances/optique.ts` | 145 | la transposition minus-cyl ↔ plus-cyl |
| `web/src/pages/clients/ordonnances/LigneDeCorrection.tsx` | 84 | la ligne de correction |
| `web/tests/ordonnance-saisie.test.tsx` | 467 | 36 tests |

**Portes relevées à la clôture partielle :** web **196 passed** (ligne de base 160, soit +36),
`build` **exit 0**, `audit:format`, `audit:clinique` et `audit:projection` **exit 0** chacune.

`audit:clinique` est celle qui compte ici : **aucun nombre clinique n'a atteint le
TypeScript**, les bornes venant de l'amorçage servi par `04-04`.

L'`04-UI-SPEC.md` est **amendé en place et daté** : les deux discriminants d'écart
pupillaire **absorbent** les avertissements A8 et A9 au lieu d'en ajouter, de sorte que le
compte reste à onze comme §16.3 l'exige, et leur sévérité passe de refus à avertissement,
leurs deux seuils étant marqués `[JUGEMENT — sans source]`.

## Ce qui reste — tâches 2 et 3

**L'écran n'existe pas.** Aucun de ces fichiers n'est écrit :

- `web/src/pages/clients/ordonnances/SaisieOrdonnance.tsx`
- `web/src/pages/clients/ordonnances/GrilleOdOg.tsx`
- `web/src/pages/clients/ordonnances/BlocEcartPupillaire.tsx`
- `web/src/pages/clients/ordonnances/PanneauRelecture.tsx`
- la `Route` dans `web/src/App.tsx`

Donc, et il faut le dire plutôt que le laisser découvrir : **les critères de succès qui
portent sur le rendu ne sont pas tenus.** Ni le panneau de relecture en notation papier, ni
les assertions sur la forme d'un avertissement (`role="status"`, aucune couleur, au blur,
sans `aria-invalid`), ni le test d'atteignabilité par navigation. Les onze avertissements
existent **en logique**, vérifiés par les tests des modules purs ; aucun n'est encore rendu.

## Pourquoi ce plan s'est arrêté

L'agent d'exécution s'est arrêté **deux fois sans jamais commiter** : une première fois par
blocage du flux à « now the UI-SPEC amendment », une seconde sur une erreur réseau après
reprise. Les deux causes sont d'infrastructure, aucune ne vient du plan ni du code.

L'orchestrateur a **vérifié puis commité** le travail existant plutôt que de le perdre, et
n'a pas écrit l'écran : le faire aurait dépassé le budget de contexte restant, et un écran à
moitié écrit coûte plus cher qu'un écran absent.

## Honnêteté sur les tests

**L'arc rouge-puis-vert n'est pas dans l'historique.** Rien n'avait été commité avant la
reprise, donc la discipline test-first de ce plan ne peut pas être prouvée par les commits —
seulement constatée sur le résultat : les 36 tests passent et les quatre gardes sont vertes.

Le dire vaut mieux que l'impliquer. Une reprise qui écrit les composants devra, elle, tenir
l'arc pour sa propre part.

## Pour reprendre

Relancer `04-08` sur ses tâches 2 et 3 avec `04-08-PLAN.md`, en lui disant que la tâche 1
est déjà commitée en `f633041` et qu'il ne doit ni la réécrire ni la recommiter. Le reste du
contrat est inchangé : `04-UI-SPEC.md` §16 et §20, les bornes servies, l'avertissement qui
n'est pas un refus, et la transposition montrée sans être stockée deux fois.

`04-09` **ne peut pas commencer avant** : il construit la fiche, l'historique et l'impression
par-dessus cet écran.
