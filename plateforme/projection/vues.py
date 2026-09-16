"""La portée magasin : la moitié **lignes** de la garantie. PERM-04 et PERM-05.

La projection du plan 03-06 caviarde des **champs**. Elle ne peut caviarder ni une
**ligne**, ni un **agrégat**. Un gérant qui n'a qu'un magasin mais qui reçoit encore un
`SUM(montant)` sur toute l'affaire s'est fait dire le chiffre d'affaires que PERM-05
interdit, alors même que chaque champ était « masqué ». Le total n'est le champ de
personne.

> **C'est un vrai défaut dans la manière dont la feuille de route formule PERM-05, et il
> est écrit ici plutôt que contourné : le chiffre d'affaires global n'est pas un problème
> de visibilité de champ.** On ne caviarde pas un scalaire déjà calculé ; il faut ne pas
> le calculer. L'agrégat se prend sur le queryset **déjà restreint**, avant qu'aucun
> sérialiseur ne le voie. Tout point de terminaison de tableau de bord qui calcule puis
> caviarde est faux par construction.

**Deux couches, jamais confondues.** Le routeur de locataire lie *quelle base* — une
frontière inter-clients, qui échoue fermée et que `REVOKE CONNECT` soutient sous
l'application. La portée magasin choisit *quelles lignes dedans* — une colonne, en Python
seulement. Le filtre magasin ne doit **jamais** servir d'isolation inter-clients, et le
routeur ne doit **jamais** servir de portée magasin.

**L'admission qui va avec, et elle est la vérité de ce module.** Il n'existe aucune couche
en dessous : tous les utilisateurs d'un client partagent un seul rôle PostgreSQL. Là où
l'isolation entre clients repose sur un `REVOKE`, la portée des lignes ne repose que sur
ce fichier. Le contrôle compensatoire est **l'énumérabilité** — `plateforme/projection/checks.py`
et les tests qui l'appliquent — pas la profondeur.

**La non-convention de `domaine/magasins/models.py` est respectée, pas contournée.** Ce
module ne pose ni gestionnaire par défaut filtré, ni contextvar magasin. La docstring de
`MagasinScopedModel` les refuse avec la bonne raison : les lectures inter-magasins sont
légitimes et constantes — le tableau de bord du propriétaire, la réappro — et un filtre
implicite renverrait *un nombre faux sans erreur*, ce qui est pire qu'un plantage. La
portée est donc écrite **à la vue**, explicitement, et une vue qui l'oublie est rouge en CI
plutôt que silencieuse en production.

---

## La déclaration de portée de route, que la phase 7 consommera

`03-UI-SPEC.md` 5.4 l'exige et elle se pose maintenant, pas au moment où la caisse en aura
besoin. **Chaque route déclare `scope: "magasin" | "multi"`.** Certains écrans sont
intrinsèquement mono-magasin — la caisse, l'inventaire, les mouvements de stock — et
d'autres sont légitimement inter-magasins — le tableau de bord du propriétaire, la
réappro.

Quand la portée active est « Tous les magasins » et que la route en exige **un**,
l'interface affiche une invite de choix :

    ### Choisissez un magasin
    La caisse est propre à chaque magasin. Sélectionnez-en un pour continuer.
    [ Anfa ]  [ Maârif ]  [ Californie ]

Elle ne devine **jamais**. Choisir en silence le premier magasin et afficher son solde de
caisse est exactement le « nombre faux sans erreur » que la couche ORM refuse déjà — la
même erreur, un étage plus haut, et cette fois avec un chiffre à l'écran que personne ne
soupçonnera.

## La règle que la phase 10 devra suivre

**Une valeur dérivée protégée vit derrière une méthode de queryset qui prend l'accès**, par
exemple ::

    class VenteQuerySet(MagasinScopedQuerySet):
        def avec_marge(self, acces):
            if not acces.peut(Permission.VENTE_VOIR_MARGE):
                return self
            return self.annotate(marge=F("prix_vente") - F("prix_achat"))

et non une `annotate()` posée dans la vue « parce que c'est là qu'on en a besoin ». Une
`annotate()` qui produit de la monnaie ne touche aucun sérialiseur : la projection n'y est
pas contournée, elle est **absente** (`03-RESEARCH.md` A-03-04). Une `annotate()` qui
produit de la monnaie est une question de registre, pas une commodité locale.
"""

from __future__ import annotations

from rest_framework import serializers

from plateforme.comptes.acces import Acces
from plateforme.projection.serializers import acces_du_contexte


def acces_de_la_requete(requete) -> Acces:
    """L'`Acces` porté par une requête, ou `Acces.ANONYME`.

    Le pendant de `acces_du_contexte` pour les vues, et il a le même défaut pour la même
    raison : `getattr(request, "acces", None)` suivi de « si `None`, ne pas filtrer »
    rendrait **toutes** les lignes sur tout chemin où `AccesMiddleware` n'a pas tourné.
    CLAUDE.md #8 une couche plus haut ; `03-RESEARCH.md` P2.
    """
    acces = getattr(requete, "acces", None)
    return Acces.ANONYME if acces is None else acces


class MagasinScopedViewSet:
    """Le mixin de portée. **Le filtre est dans `get_queryset()`, jamais dans `list()`.**

    `GenericAPIView.get_object()` passe par `get_queryset()`, donc filtrer là restreint
    aussi la route de détail `/ventes/42/`. **Filtrer dans `list()` laisse la route de
    détail grande ouverte, ce qui est l'IDOR classique de cette forme de code** — la liste
    est propre, le détail répond sur un petit entier deviné, et la revue de code ne voit
    rien parce que la vue *a l'air* protégée. Cette phrase est ici parce que c'est la
    ligne que quelqu'un déplacera un jour « pour optimiser » (`03-RESEARCH.md` P4, menace
    T-03-39).

    **Un mixin, et non une sous-classe de `ModelViewSet`.** La recherche l'écrit comme une
    sous-classe ; c'est refusé sur un motif concret plutôt que par goût : la caisse de la
    phase 7 est un registre en ajout seul (CLAUDE.md #4), donc ses vues sont des
    `ReadOnlyModelViewSet` plus une route de création — hériter d'un `ModelViewSet`
    complet leur donnerait `update` et `destroy` par défaut. Un mixin compose avec les
    deux.

    Le prix de ce choix est un mode de défaillance silencieux, donc il est gardé :
    `class Vue(ModelViewSet, MagasinScopedViewSet)` — l'ordre inverse — laisse
    `GenericAPIView.get_queryset` gagner le MRO et **la portée disparaît sans erreur**.
    `plateforme/projection/checks.py` vérifie donc l'ordre, pas seulement l'héritage.
    """

    def get_queryset(self):
        """Le queryset de la vue, restreint aux magasins de l'appelant.

        Court-circuité pour la génération du schéma : `Acces.SCHEMA` ne porte aucun
        magasin réel (plan 03-05, `MAGASIN_DU_SCHEMA`), donc appliquer la portée y rendrait
        zéro ligne et ferait dépendre le document OpenAPI de son lecteur. Le drapeau est lu
        **ici**, où la portée est écrite — `Acces.peut()` ne le lit pas et ne doit pas
        apprendre à le lire.
        """
        queryset = super().get_queryset()
        acces = acces_de_la_requete(self.request)
        if acces.pour_le_schema:
            return queryset
        return queryset.for_magasins(acces.magasins_ids)


class MagasinAutoriseField(serializers.PrimaryKeyRelatedField):
    """Le champ lié dont le queryset est restreint. **Jamais tous les magasins.**

    La forme interdite est `PrimaryKeyRelatedField(queryset=<le gestionnaire complet de
    Magasin>)`. Elle n'est pas écrite littéralement ici : le plan en fait un critère
    grepable sur `plateforme/` et `domaine/`, donc la citer dans une docstring rendrait le
    critère rouge sur le fichier qui l'interdit.

    C'est celui que tout le monde oublie. Une vue qui restreint `get_queryset()` protège
    la lecture, la modification et la suppression — mais **pas la création** : un POST qui
    nomme `{"magasin": 7}` ne consulte aucun queryset de vue. DRF valide la clé primaire
    contre le queryset **de ce champ**, donc le restreindre transforme l'écriture
    inter-magasins en erreur de validation : un **400**, pas un 201 (`03-RESEARCH.md` P5,
    menace T-03-40).

    Écrire la règle comme une contrainte sur le queryset plutôt que comme une validation
    ajoutée après coup n'est pas une préférence de style : une validation se pose champ par
    champ et s'oublie, un queryset restreint est le seul chemin que DRF emprunte.

    Le message d'erreur produit est celui de DRF — « Invalid pk "7" - object does not
    exist. » — et il ne dit **pas** que le magasin existe ailleurs. Un 400 qui
    distinguerait « n'existe pas » de « existe mais pas pour vous » serait un oracle
    d'énumération de magasins (A-03-13).
    """

    def get_queryset(self):
        from domaine.magasins.models import Magasin

        acces = acces_du_contexte(self.context)
        return Magasin.objects.filter(id__in=acces.magasins_ids)


def agreger_dans_la_portee(queryset, acces, **agregations):
    """Agréger sur le queryset **déjà restreint**, jamais sur le manager par défaut.

    L'aide existe parce que l'espoir ne suffit pas. `Model.objects.aggregate(Sum(...))`
    repart de zéro et ignore le queryset que la vue vient de construire ; le résultat est
    un scalaire juste pour l'entreprise et faux pour l'appelant, et **on ne peut pas ne
    pas voir un scalaire déjà calculé**. Il n'y a pas de caviardage possible en aval : la
    seule défense est de ne pas l'additionner.

    Elle **prend l'accès** et applique la portée elle-même, plutôt que de faire confiance à
    l'appelant pour lui passer un queryset déjà filtré. La différence compte : un appelant
    qui se trompe obtient alors un nombre restreint, pas un nombre global.

    Même court-circuit de schéma que `MagasinScopedViewSet.get_queryset`, et pour la même
    raison.
    """
    if not acces.pour_le_schema:
        queryset = queryset.for_magasins(acces.magasins_ids)
    return queryset.aggregate(**agregations)
