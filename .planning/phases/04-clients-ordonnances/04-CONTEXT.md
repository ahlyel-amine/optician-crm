---
phase: 04-clients-ordonnances
type: context
status: proposed — quatre décisions attendent la confirmation du propriétaire
created: 2026-09-17
---

# Contexte de la phase 4 — Clients & Ordonnances

> **Statut : PROPOSÉ, pas verrouillé.** Les quatre zones grises ci-dessous ont été
> présentées au propriétaire, qui n'a pas répondu. Chacune porte une **recommandation
> argumentée** plutôt qu'un blanc, pour que le travail puisse avancer et qu'une correction
> coûte un mot. **Un plan ne doit pas traiter ces quatre points comme verrouillés** — il les
> applique en les nommant, de sorte qu'un désaccord se voie.
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
