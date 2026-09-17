# JWT contre session Django — document de décision

**Date** : 2026-09-17
**Origine** : le propriétaire annonce vouloir passer à JWT, motif donné « c'est plus sécurisé », et
demande une investigation avant toute implémentation.
**Statut** : document de décision. Aucun code, aucun réglage, aucun plan n'a été produit.

Chaque affirmation porte son étiquette : **[repo]** vérifié dans ce dépôt, **[paquet]** vérifié
contre le paquet installé ou publié, **[raisonné]** déduit, non mesuré.

---

## Recommandation en trente secondes

**Garder la session pour le web. Ajouter une classe de jeton pour le mobile en phase 11.**

Pour une SPA de même origine, le cookie de session tel qu'il est **déjà configuré ici** est plus
résistant que JWT, pas moins : il est `HttpOnly`, donc une faille XSS ne peut pas l'exfiltrer, alors
qu'un JWT en `localStorage` se lit en une ligne de JavaScript et reste valide depuis la machine de
l'attaquant jusqu'à son expiration. S'ajoute une exigence propre à ce produit : **PERM-02 et PERM-03
sont des exigences de révocation** — un JWT reste valide après la désactivation d'un compte.

Et un fait qui tranche à lui seul, indépendamment de l'argument de sécurité :
**`djangorestframework-simplejwt` ne déclare pas Django 6.1, et ce projet tourne sur Django 6.1.1.**

---

## 1. « C'est plus sécurisé » — l'affirmation ne tient pas pour cette configuration

### Ce qui est réellement en force aujourd'hui **[repo]**

| Réglage | Valeur | Fichier |
|---|---|---|
| `SESSION_COOKIE_HTTPONLY` | `True` | `config/settings/base.py:429` |
| `SESSION_COOKIE_SECURE` | `True` (prod) | `config/settings/base.py:428` |
| `SESSION_COOKIE_SAMESITE` | `"Lax"` | `config/settings/base.py:432` |
| `SESSION_COOKIE_AGE` | 30 jours | `config/settings/base.py:442` |
| `SESSION_ENGINE` | backend base de données | `config/settings/base.py:453` |
| `CSRF_COOKIE_HTTPONLY` | `False` | délibéré — le double-submit exige que le JS le lise |
| CSRF sur la connexion | `csrf_protect` explicite | ajouté au plan 03-08 |

C'est une configuration durcie, pas une configuration par défaut.

### La comparaison, menée contre cette configuration

| Vecteur | Session ici | JWT en `localStorage` | JWT en cookie |
|---|---|---|---|
| **Exfiltration par XSS** | **Impossible** — `HttpOnly`. Un XSS agit dans la page mais ne peut pas lire le cookie ni l'emporter. | **Triviale** — `localStorage.getItem()`. L'attaquant obtient un porteur utilisable depuis **sa** machine jusqu'à expiration. | Impossible si `HttpOnly` — mais on a alors exactement un cookie de session, en moins révocable. |
| **CSRF** | Double-submit + `SameSite=Lax` + `csrf_protect` | Non applicable (en-tête explicite) — **le seul point où JWT simplifie** | Identique à la session : même surface, mêmes protections nécessaires |
| **Révocation** | `DELETE` d'une ligne, effectif à la requête suivante | Valide jusqu'à expiration, sauf liste de révocation | Idem |
| **Contenu lisible** | Identifiant opaque, ne dit rien | Revendications base64 : qui, quel client, quelle expiration | Idem |
| **Rejeu après vol** | Fenêtre = jusqu'à déconnexion ou suppression de la ligne | Fenêtre = jusqu'à expiration, **hors de votre contrôle une fois émis** | Idem |

**Conclusion [raisonné, sur des faits [repo]]** : sur cinq vecteurs, JWT est à égalité ou moins bon,
et gagne sur un seul — CSRF, que la session traite déjà par un mécanisme en place et testé.

### Là où JWT est réellement meilleur — et ce n'est pas rien

Ces avantages sont réels ; ils ne s'appliquent simplement pas à une SPA de même origine :

- **Clients natifs.** Un en-tête `Authorization` est plus simple qu'un magasin de cookies dans Expo.
  C'est le besoin de la **phase 11**, et il est légitime. **[raisonné]**
- **Origines distinctes.** Si la SPA était servie depuis un autre domaine, le cookie deviendrait
  pénible (CORS, `SameSite=None`, cookies tiers de plus en plus bloqués). **[raisonné]**
- **Fédération entre services.** Un jeton signé qu'un service tiers vérifie sans appeler le nôtre.
  Sans objet aujourd'hui : il n'y a qu'un service. **[raisonné]**
- **Absence de magasin partagé.** Utile pour monter en charge horizontalement sans base de sessions
  commune. Ce projet a déjà PostgreSQL partagé pour le plan de contrôle. **[raisonné]**

### L'argument « sans état » est plus faible qu'il n'y paraît ici

`JWTAuthentication.get_user` recharge l'utilisateur en base et vérifie `is_active` à chaque requête.
Le gain « zéro accès base » n'existe donc pas dès qu'on veut qu'une désactivation morde — ce que
PERM-02 exige. **[raisonné ; recensé au plan 03-08, non re-mesuré, le paquet n'étant pas installé]**

---

## 2. Le fait qui tranche : Django 6.1 n'est pas supporté

**[paquet]** — interrogé sur PyPI le 2026-09-17 :

| | |
|---|---|
| Dernière version de `djangorestframework-simplejwt` | **5.5.1**, publiée **2025-07-21** |
| Django déclaré supporté | `4.2`, `5.0`, `5.1`, `5.2` — **pas 6.0, pas 6.1** |
| `requires_dist` | `django>=4.2` (borne basse seulement) |
| Installé dans ce projet | **non** |

**[repo]** Ce projet tourne sur **Django 6.1.1** et **DRF 3.18.1**.

La borne `django>=4.2` signifie que le paquet **s'installerait** sans protester. Cela ne veut pas
dire qu'il est testé : la dernière version est antérieure de plus d'un an à Django 6.1, et aucune
version ne déclare 6.x. Adopter une bibliothèque d'**authentification** non testée contre sa version
majeure de Django est précisément le genre de pari que la non-négociable **#12** de CLAUDE.md
décrit — une garantie écrite une couche au-dessus, invisible à la revue de code.

Ce point est indépendant de l'argument de sécurité. Même si vous décidiez que JWT vous convient
mieux, **il faudrait d'abord prouver simplejwt sur Django 6.1 en bac à sable**, ou retenir une autre
bibliothèque, ou écrire la classe d'authentification à la main.

---

## 3. Ce que coûterait réellement le remplacement

### Le point dur : la liaison au locataire

**[repo]** `plateforme/tenancy/middleware.py:25-27` le documente dans le code :

> Django populates `request.user` from the session *before* this middleware runs, whereas DRF's
> [authentication runs inside `APIView.initial()`] … token authenticated by DRF, `request.user` here
> would be `AnonymousUser` on every request

Conséquence mécanique : sous JWT, `resolve_client(request)` ne résout rien, le contexte de locataire
ne se lie pas, et **toute requête métier lève `NoTenantBound`**. Ce n'est pas une préférence, c'est
l'ordre d'exécution de Django et de DRF.

C'est réparable — décoder le jeton dans un middleware maison, ou déplacer la liaison dans la couche
vue — mais la réparation touche **la couche de tenancy**, c'est-à-dire :

- la non-négociable **#8** (le contexte se vide dans un `finally`, jamais `reset()`), décrite dans
  CLAUDE.md comme « the single highest-risk line in the layer » ;
- le routeur qui **lève** quand rien n'est lié, parce que retourner `None` est une fuite entre
  clients silencieuse.

**Une erreur ici n'est pas un bug d'authentification, c'est une fuite de données entre opticiens.**

### L'inventaire **[repo]**

| Ce qui change | Détail |
|---|---|
| Couche tenancy | liaison du locataire déplacée ou middleware de décodage ; tests de non-fuite à réécrire |
| 5 points de terminaison `/api/auth/` | `csrf`, `connexion`, `deconnexion`, `moi`, `mot-de-passe` (plan 03-08) |
| CSRF | `csrf_protect`, en-tête `X-CSRFToken`, `ensure_csrf_cookie`, `CSRF_TRUSTED_ORIGINS` |
| Politique de session | `SESSION_*`, `clearsessions` sur Celery Beat |
| Limitation de débit | `NUM_PROXIES = 0` et l'étranglement par portée |
| SPA | `web/src/api/client.ts` (intergiciel CSRF, gestion du 401), `web/src/auth/AuthProvider.tsx`, stockage du jeton, rafraîchissement, course au rafraîchissement |
| Contrat OpenAPI | schéma + client TS régénérés |
| Tests | `tests/test_comptes_auth.py` (19), plus le test d'origine CSRF du quick 260917-04r, plus les suites web qui simulent la session |

**Taille [raisonné]** : une phase entière, de l'ordre de **4 à 6 plans**, dont au moins un sur la
couche de tenancy. Comparable à la phase 3 elle-même. Ce n'est pas une tâche rapide.

---

## 4. Faire tenir la révocation sous JWT

**[repo]** Les exigences, mot pour mot :

- **PERM-02** : « An owner can create a gérant account … and **deactivate it later** »
- **PERM-03** : « An owner can grant or **revoke** individual permissions for a specific gérant »

Ce sont des exigences de révocation. Un JWT est un laissez-passer signé : une fois émis, il vaut
jusqu'à son expiration. Les options :

| Option | Latence de révocation | Coût par requête | Remarque |
|---|---|---|---|
| Expiration courte (5 min) + rafraîchissement | ≤ 5 min | 1 accès base par rafraîchissement + `get_user` | Un gérant désactivé travaille encore jusqu'à 5 minutes. Pour un **droit** révoqué, l'écran ment pendant ce temps. |
| Liste de révocation | Immédiate | **1 accès base par requête** | Rend le gain « sans état » nul : c'est une session, avec plus de pièces. |
| Jeton opaque en base | Immédiate | 1 accès base par requête | C'est exactement une session, sous un autre nom. |
| Session (aujourd'hui) | **Immédiate** | 1 accès base par requête | Déjà construit, déjà testé. |

**[raisonné]** Une fois la révocation exigée, les quatre lignes convergent vers le même coût. La
différence n'est plus technique, elle est en travail à faire et en risque à prendre.

Nuance honnête : cinq minutes de latence de révocation sont acceptables dans beaucoup de produits.
Ici, la révocation d'un droit comme `article.voir_prix_achat` touche une donnée commerciale que
PERM-05 protège explicitement — c'est au propriétaire de dire si la fenêtre est tolérable.

---

## 5. Le mobile en phase 11 — la conception additive, à écrire de toute façon

**[repo]** `DEFAULT_AUTHENTICATION_CLASSES` est une **liste**. Ajouter une classe de jeton n'oblige à
toucher aucune vue, aucun sérialiseur, aucune permission, ni la couche de projection.

Mais la constatation de la section 3 vaut pour **toute** authentification par jeton de DRF, y compris
additive : un client mobile authentifié par jeton arrive au middleware en `AnonymousUser`, donc le
locataire ne se lie pas.

**Trois conceptions possibles [raisonné]** :

1. **Décoder dans le middleware de tenancy.** Le middleware lit lui-même l'en-tête `Authorization`,
   valide, en tire l'identité, et lie. La liaison reste au même endroit pour les deux chemins.
   Le risque est de dupliquer la validation faite ensuite par DRF, donc de la laisser diverger.
2. **Lier dans `APIView.initial()`**, après l'authentification de DRF, via une classe de base ou un
   mixin. Le contrat « une requête métier sans contexte lève » est conservé, mais la liaison n'est
   plus garantie par le middleware pour tout le monde — il faut une garde qui refuse une vue métier
   qui aurait oublié le mixin.
3. **Session pour le web, jeton pour le mobile, deux chemins de liaison explicites.** Plus de code,
   mais chaque chemin est lisible isolément.

**Cette question doit être tranchée avant la phase 11 quoi qu'il arrive.** C'est la partie de ce
document qui sert même si JWT ne remplace jamais la session.

---

## 6. Quand remplacer la session deviendrait le bon choix

Déclencheurs concrets, à relire à ce moment-là plutôt qu'à en débattre maintenant **[raisonné]** :

1. **La SPA passe sur une origine distincte** du backend. Le cookie devient alors un combat
   (`SameSite=None`, CORS, blocage des cookies tiers). Aujourd'hui le proxy Vite garde une origine
   unique, et `web/vite.config.ts` porte un commentaire qui interdit explicitement de remplacer ce
   proxy par une origine séparée plus CORS.
2. **Des consommateurs d'API tiers** apparaissent — un logiciel de comptabilité marocain, une
   centrale d'achat — à qui l'on ne peut pas donner un cookie de session.
3. **Une fédération entre services** : un second service doit vérifier l'identité sans appeler le
   premier.
4. **Une montée en charge** où la table de sessions devient un point chaud mesuré. À vérifier par la
   mesure, pas par anticipation : PgBouncer et une base par client changent ce calcul.
5. **Une contrainte réglementaire ou d'audit** exigeant une identité signée et portable.

Aucun de ces cinq n'est vrai aujourd'hui.

---

## 7. Les options, avec leur taille et leur conséquence

| Option | Taille | Conséquence |
|---|---|---|
| **A. Garder la session, ajouter un jeton en phase 11** *(recommandée)* | ~1 plan, en phase 11 | Rien de la phase 2 ni de la phase 3 n'est touché. Le web garde `HttpOnly` et la révocation immédiate. La question de liaison de la section 5 est tranchée à ce moment-là. |
| **B. Trancher maintenant la liaison sous jeton, implémenter en phase 11** | ~0,5 plan maintenant + 1 plan en phase 11 | Même résultat, mais le point dur est résolu pendant que la couche de tenancy est fraîche. Coût : un peu de travail sur une phase lointaine. |
| **C. Remplacer la session par JWT partout** | **4 à 6 plans**, dont un sur la couche de tenancy | Exige d'abord de prouver simplejwt sur Django 6.1, ou de choisir autre chose, ou de l'écrire à la main. Exige de re-répondre à PERM-02/PERM-03. Dégrade la résistance au XSS pour le web. Amende la table de pile de CLAUDE.md. |
| **D. Prouver simplejwt sur Django 6.1 en bac à sable, puis décider** | ~0,5 plan | Lève le seul point factuellement bloquant sans rien engager. Utile si vous voulez décider sur pièce plutôt que sur ce document. |

---

## Ce que ce document ne prétend pas

- Il **ne mesure pas** simplejwt sur Django 6.1 : le paquet n'est pas installé ici. Il rapporte ce
  que le paquet **déclare**. Un essai en bac à sable (option D) le trancherait.
- Il **ne dit pas que JWT est mauvais**. Il dit que pour *une SPA de même origine, avec un cookie
  `HttpOnly` déjà en place et deux exigences de révocation*, il est plus faible et plus cher.
- La décision appartient au propriétaire. Si l'option C est retenue, elle doit l'être comme un
  **amendement daté et motivé** de la ligne `Auth` de CLAUDE.md, pas comme une dérive.
