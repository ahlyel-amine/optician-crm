---
status: partial
phase: 03-comptes-permissions-app-shell
source:
  - 03-12-SUMMARY.md
  - 03-13-SUMMARY.md
  - 03-14-SUMMARY.md
  - ../../quick/260917-04r-corriger-l-echec-csrf-d-origine-qui-bloq/260917-04r-SUMMARY.md
  - ../../quick/260917-l7l-rendre-l-octroi-par-magasin-visible-et-c/260917-l7l-SUMMARY.md
  - ../../quick/260917-lhq-une-requete-avortee-n-est-pas-une-coupur/260917-lhq-SUMMARY.md
started: 2026-09-17
updated: 2026-09-17
---

## Current Test

number: 6
name: Le dialogue de désactivation, et l'absence du mot « supprimer »
expected: |
  Statut → Désactivé ouvre un dialogue dont la seconde phrase est
  « Ses ventes et ses saisies restent enregistrées à son nom. »
  Une recherche du mot « supprimer » dans tout l'écran ne trouve rien.
awaiting: user response

## Tests

<!--
  Les huit étapes du point de contrôle 03-14 (écran `Comptes et droits`).
  Le propriétaire les a parcourues le 2026-09-17 dans un vrai navigateur.
  Six passent, deux restent ouvertes.
-->

### 1. Créer un compte gérant, et la bannière « aucun droit »
expected: |
  `Créer un compte gérant` puis `Générer un mot de passe` fait atterrir
  DIRECTEMENT sur la fiche du nouveau compte, avec la bannière disant qu'il
  pourra se connecter mais ne verra rien.
result: pass
note: le propriétaire a créé le compte `aymane` (id 8) pendant la passe.

### 2. La cascade de prérequis, dans les deux sens, avec UN SEUL `Annuler`
expected: |
  Activer `Ajuster le stock / inventaire` active seul `Consulter le stock`,
  avec sa note en ligne. Retirer `Consulter le stock` emporte le dépendant
  avec la note symétrique. Un seul `Annuler` (toast, 10 s) restaure tout.
result: pass

### 3. La surcharge par magasin, l'état mixte et `Uniformiser`
expected: |
  Sur un compte à deux magasins : éteindre un seul magasin rend le parent
  mixte, l'aide devient `Personnalisé : 1 magasin sur 2`, et `Uniformiser`
  DEMANDE avant de remplacer.
result: pass
note: |
  Vérifié pour le COMPORTEMENT seulement. La phase 03.1 remplace ce contrôle
  par un sélecteur de magasin en tête de section ; le comportement sous-jacent,
  lui, est conservé, d'où l'intérêt de cette vérification.

### 4. Un compte mono-magasin n'affiche aucun contrôle par magasin
expected: |
  Connecté sur l'affaire `rabat` (un seul magasin, AGDAL), aucune ligne de
  droit ne porte `Par magasin` — la sous-liste n'aurait qu'une entrée possible.
result: pass
note: affaire de développement `rabat` provisionnée au plan 03-14 pour rendre cette étape vérifiable.

### 5. La réinitialisation du mot de passe demande confirmation
expected: |
  `Réinitialiser le mot de passe` ouvre un dialogue nommant la personne et
  disant que son mot de passe actuel cesse immédiatement de fonctionner.
  `Retour` ne fait rien. `Réinitialiser` affiche le mot de passe provisoire.
result: pass
note: |
  Défaut trouvé par le propriétaire pendant cette même passe — la réinitialisation
  partait au clic, sans confirmation et sans `Annuler`. Corrigé par la tâche
  rapide 260917-l7l, puis revérifié ici.

### 6. Le dialogue de désactivation, et l'absence du mot « supprimer »
expected: |
  Statut → Désactivé : la seconde phrase est « Ses ventes et ses saisies
  restent enregistrées à son nom. » Le mot « supprimer » n'existe nulle part
  dans l'écran.
result: pending
note: |
  Non exécutée. Le versant automatisé existe — `grep -rni 'supprimer'` sur
  `web/src/pages/comptes/` retourne 0 au plan 03-14 — mais la lecture de la
  phrase à l'écran, elle, n'a pas été faite.

### 7. L'absence au niveau du fil, dans l'onglet réseau
expected: |
  En `salma@optiqueanfa.ma` (gérante-gestionnaire sans `article.voir_prix_achat`),
  la fiche d'un collègue n'affiche NI la ligne `Voir le prix d'achat` NI la
  section `Ventes et factures` — absentes, pas grisées. Et dans l'onglet
  réseau, la chaîne `article.voir_prix_achat` n'apparaît dans AUCUNE des
  réponses `/api/comptes/catalogue/` et `/api/comptes/{id}/`.
result: pending
severity_if_failed: critical
note: |
  **La plus importante des huit, et celle qui reste ouverte.** C'est la
  garantie « au niveau du fil » de `03-UI-SPEC.md` 7.7, sur laquelle repose
  tout l'argument de PERM-05/PERM-06 : si le code est dans la réponse et
  seulement masqué par l'interface, la garantie est fausse et un devtools la
  démonte. Vérifiée par `curl` au plan 03-14 (4 sections, 5 codes, chaîne
  absente des octets) et par un test nommé qui affirme sur `rendered_content`
  — mais **pas** par une personne devant l'onglet réseau, qui est la forme
  que l'étape demande.

### 8. Clavier seul, VoiceOver, et le lexique
expected: |
  `Tab` atteint chaque interrupteur, anneau de focus visible partout.
  VoiceOver annonce le libellé, l'état (`coché` / `non coché` /
  `partiellement coché`) et, dans une sous-liste, le magasin.
  Lexique de 9.3 : magasin, gérant, droits, désactiver, enregistrer.
result: pass
note: |
  C'est la vérification manuelle nommée dans `03-VALIDATION.md`. vitest rend
  dans jsdom et ne peut rien dire de ce qu'annonce un lecteur d'écran.

## Summary

total: 8
passed: 6
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps

<!-- Aucun échec. Les deux items ouverts n'ont pas été exécutés, ce qui n'est pas un échec. -->

## Reste ouvert ailleurs dans la phase

Cette passe couvre les huit étapes du point de contrôle **03-14 uniquement**.
Restent non effectuées, et suivies dans `STATE.md` → Blockers/Concerns :

- **7 étapes du point de contrôle 03-12** (`/connexion`) — connexion sans
  clignotement, stabilité de la carte à l'erreur, compte à rebours à la onzième
  tentative, atterrissage forcé sans issue, clavier seul, lecture en français
  contre 9.3, bannière de connexion perdue.
- **1 étape de la tâche rapide 260917-04r** — la connexion réussie au navigateur
  et `Host: localhost:5173` dans les en-têtes reçus par Django. Le correctif est
  prouvé par reproduction HTTP, pas par une personne.
- **8 étapes du point de contrôle 03-13** (app shell) — densité sous
  `VITE_NAV_COMPLET=1`, application visiblement plus petite d'un gérant, absence
  de contrôle en mono-magasin, changement de portée sans changement de route,
  clavier puis VoiceOver, `Ctrl+P`, zoom à 200 %.

**Total restant : 18 vérifications** (16 ci-dessus + les 2 de cette passe).

## Ce que cette passe a produit

Elle n'a pas seulement coché des cases : elle a trouvé **cinq défauts réels**
pendant que 303 tests automatisés étaient au vert.

| Défaut | Corrigé par |
|---|---|
| 403 CSRF au navigateur — `Origin` refusé, connexion impossible | quick 260917-04r |
| `/parametres/comptes` inatteignable par l'interface | plan 03-14 (continuation) |
| Le changement de mot de passe forcé redemandait le mot de passe actuel | plan 03-13 (décision 6) |
| `Par magasin` invisible hors survol | quick 260917-l7l |
| La réinitialisation du mot de passe partait sans confirmation | quick 260917-l7l |
| La bannière « Connexion perdue » clignotait à chaque navigation | quick 260917-lhq |

Trois d'entre eux sont **mécaniquement rattrapables** par un outillage qui
n'existe pas encore (double de `fetch` différé, une passe Playwright étroite).
Deux ne le seront **jamais** : un test survole, parce qu'un test sait où est le
contrôle — la découvrabilité est un jugement humain, et « cette action mérite
une confirmation » est un jugement de conception.
