"""Les gardes d'énumération : faire échouer l'oubli en CI plutôt qu'en production.

`plateforme/tenancy/checks.py` a établi l'idiome, et il vaut la peine d'être répété :
`tenancy.E001` rend **impossible**, et non seulement improbable, l'oubli de classer une
application. Ce module fait la même chose pour les deux oublis de la phase 3 — le mixin de
portée magasin sur une vue, et la projection sur un sérialiseur — plus le garde source qui
énonce la limite structurelle du choix de conception.

---

## Pourquoi des tests, et pas (encore) des `system checks`

`03-RESEARCH.md` §3 le recommande explicitement, et sur un motif concret : un contrôle de
démarrage qui importe chaque `serializers.py` du dépôt est **fragile à cause des cycles
d'import**. `manage.py check` tourne pendant `AppConfig.ready()`, avant que tout soit
chargé ; un garde qui force l'import de modules de sérialiseurs à ce moment-là fait
apparaître des `ImportError` qui n'ont rien à voir avec ce qu'il vérifie, et le premier
réflexe sera de le désactiver.

Les fonctions ci-dessous sont donc **pures** — elles prennent une liste et rendent une
liste de fautes — et ce sont les tests qui les appellent. Le prix est qu'elles ne tournent
pas sur `runserver` ; le bénéfice est qu'elles tournent en CI sans rien importer de plus
que ce que la suite importe déjà.

> **La condition de promotion, écrite ici pour ne pas dépendre d'un souvenir.** Les
> promouvoir en `projection.E001` et `projection.E002` devient le bon choix le jour où les
> deux conditions suivantes sont vraies : (a) tous les modules de sérialiseurs et de vues
> du dépôt sont importés de manière fiable au moment de `ready()` — ce qui sera le cas dès
> qu'une `AppConfig` métier les importera pour enregistrer ses routes ; et (b) un plan a
> constaté au moins une fois qu'un oubli est passé entre deux exécutions de la suite.
> Tant que (a) est faux, un check de démarrage est une source de faux rouges, et un garde
> qui crie à tort finit désactivé.

---

## La limite structurelle, énoncée plutôt que dissimulée

`retours_values_queryset` compense une faiblesse réelle, et il faut la dire franchement :

> **Une projection portée par les sérialiseurs est absente de tout chemin qui n'emprunte
> pas de sérialiseur.** `Response(qs.values("prix_achat"))` en est un. La projection n'y
> est pas contournée — elle n'est simplement pas là. Aucune classe de base ne peut y
> remédier, parce qu'il n'y a aucune classe de base sur ce chemin.

Le garde est donc un test au **niveau du source**, dans l'idiome de
`tests/test_migration_conventions.py` : il lit l'AST plutôt que d'exécuter. C'est le bon
outil précisément parce que le chemin fautif ne s'exécute jamais dans la suite — personne
n'écrit un test pour la vue qu'il vient d'ajouter sans projection.

**La règle de revue qui va avec, et qui couvre ce que l'AST ne voit pas :** une
`annotate()` qui produit de la monnaie est une **question de registre**, pas une commodité
locale. `qs.annotate(marge=F("prix_vente") - F("prix_achat"))` ne nomme aucun champ
protégé, ne déclenche aucun garde, et sert une marge que l'appelant n'a pas le droit de
lire. La forme correcte est une méthode de queryset qui prend l'accès — `avec_marge(acces)`
— et qui ne pose l'annotation que si le droit est détenu (`plateforme/projection/vues.py`).
"""

from __future__ import annotations

import ast
from pathlib import Path

RACINE_DU_DEPOT = Path(__file__).resolve().parents[2]

#: Les paquets parcourus par le garde source. `tests/` en est volontairement absent : la
#: ressource de test *doit* pouvoir écrire la faute, c'est ainsi que le détecteur se
#: prouve.
PAQUETS_APPLICATIFS = ("plateforme", "domaine", "config")

#: Les noms de modules qui contiennent des vues. Les deux orthographes, parce que le dépôt
#: écrit `vues.py` et que `views.py` reste le nom que Django produit.
NOMS_DE_MODULES_DE_VUES = ("vues.py", "views.py")

#: Les appels qui enveloppent une charge utile de réponse. `JsonResponse` est là pour la
#: même raison que `Response` : elle sérialise ce qu'on lui donne, sans projection.
ENVELOPPES_DE_REPONSE = frozenset({"Response", "JsonResponse"})

#: Les méthodes de queryset qui court-circuitent entièrement le sérialiseur.
METHODES_SANS_SERIALISEUR = frozenset({"values", "values_list"})


# ======================================================================================
# Garde 1 — le values queryset servi tel quel (A-03-04, T-03-44)
# ======================================================================================
def modules_de_vues(racine: Path | None = None) -> list[Path]:
    """Tout module de vues des paquets applicatifs, `.venv` exclu."""
    racine = racine or RACINE_DU_DEPOT
    trouves: list[Path] = []
    for paquet in PAQUETS_APPLICATIFS:
        base = racine / paquet
        if not base.is_dir():
            continue
        for chemin in sorted(base.rglob("*.py")):
            if ".venv" in chemin.parts:
                continue
            if chemin.name in NOMS_DE_MODULES_DE_VUES:
                trouves.append(chemin)
    return trouves


def _source_de(entree) -> tuple[str, str]:
    """`(nom lisible, source)` — accepte un `Path` ou un couple `(nom, source)`.

    Les deux formes existent pour que le contrôle négatif du test passe par **le même
    code** que le parcours réel. Un détecteur éprouvé sur un chemin différent de celui
    qu'il emprunte en vrai n'est pas éprouvé.
    """
    if isinstance(entree, tuple):
        nom, source = entree
        return str(nom), source
    chemin = Path(entree)
    return str(chemin), chemin.read_text(encoding="utf-8")


def _est_appel_values(noeud: ast.AST) -> bool:
    """Vrai pour `<quelque chose>.values(...)` ou `.values_list(...)`, chaîné compris."""
    return (
        isinstance(noeud, ast.Call)
        and isinstance(noeud.func, ast.Attribute)
        and noeud.func.attr in METHODES_SANS_SERIALISEUR
    )


def _deballe(noeud: ast.AST) -> ast.AST:
    """Retire un `list(...)` / `tuple(...)` autour d'un argument.

    `Response(list(qs.values(...)))` est la même faute avec un appel de plus, et c'est
    la forme qu'on écrit sans y penser quand la réponse doit être indexable.
    """
    while (
        isinstance(noeud, ast.Call)
        and isinstance(noeud.func, ast.Name)
        and noeud.func.id in {"list", "tuple"}
        and noeud.args
    ):
        noeud = noeud.args[0]
    return noeud


def retours_values_queryset(entrees) -> list[str]:
    """Les endroits où une réponse est construite directement sur un values queryset.

    Trois formes sont reconnues, et ce sont les trois qui s'écrivent :

    1. `Response(qs.values("prix_achat"))` — directe, éventuellement chaînée ;
    2. `lignes = qs.values(...)` puis `Response(lignes)` — par variable locale ;
    3. `Response(list(qs.values(...)))` — enveloppée.

    Ce qu'elle ne voit **pas**, et qui est dit plutôt que caché : un values queryset qui
    traverse une fonction d'aide, ou une `annotate()` de monnaie. La seconde est couverte
    par la règle de revue de la docstring du module ; la première est le trou résiduel
    assumé de T-03-44, qui est marqué « mitigate **partiellement** » pour cette raison.
    """
    fautes: list[str] = []
    for entree in entrees:
        nom, source = _source_de(entree)
        arbre = ast.parse(source)

        # Les variables locales alimentées par un values queryset, par module. Suivre la
        # portée exacte coûterait un analyseur ; au niveau du module la sur-détection est
        # sans conséquence, parce que le nom réutilisé pour autre chose *dans une vue*
        # serait de toute façon une ligne à relire.
        noms_values = {
            cible.id
            for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Assign) and _est_appel_values(_deballe(noeud.value))
            for cible in noeud.targets
            if isinstance(cible, ast.Name)
        }

        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            appelee = getattr(noeud.func, "id", None) or getattr(noeud.func, "attr", None)
            if appelee not in ENVELOPPES_DE_REPONSE:
                continue
            for argument in noeud.args:
                argument = _deballe(argument)
                if _est_appel_values(argument) or (
                    isinstance(argument, ast.Name) and argument.id in noms_values
                ):
                    fautes.append(f"{nom}:{noeud.lineno}")
                    break
    return fautes


# ======================================================================================
# Garde 2 — le mixin de portée magasin oublié (T-03-45)
# ======================================================================================
def _modele_de_la_vue(vue):
    """Le modèle servi par une vue : son `queryset`, sinon le `Meta.model` du sérialiseur."""
    queryset = getattr(vue, "queryset", None)
    modele = getattr(queryset, "model", None)
    if modele is not None:
        return modele
    serialiseur = getattr(vue, "serializer_class", None)
    return getattr(getattr(serialiseur, "Meta", None), "model", None)


def _sous_classes(classe):
    for fille in classe.__subclasses__():
        yield fille
        yield from _sous_classes(fille)


def toutes_les_vues() -> list[type]:
    """Toute sous-classe d'`APIView` chargée, hors celles de DRF lui-même.

    « Chargée » et non « enregistrée dans un routeur » : une vue montée à la main dans un
    `urlpatterns` est tout aussi exposée qu'une vue de routeur, et l'énumération par
    `__subclasses__()` ne peut pas la manquer. Le prix est qu'une vue jamais importée
    échappe au garde — ce qui, pour une vue servie en production, ne peut pas arriver.
    """
    from rest_framework.views import APIView

    return [
        vue
        for vue in _sous_classes(APIView)
        if not vue.__module__.startswith("rest_framework")
        and not vue.__module__.startswith("drf_spectacular")
    ]


def vues_sans_portee_magasin(vues) -> list[str]:
    """Les vues qui servent un modèle magasin-scopé sans que la portée s'applique.

    **Deux fautes distinctes, et la seconde est la vicieuse.** L'absence du mixin se voit ;
    le mixin placé *après* `GenericAPIView` dans les bases ne se voit pas — la vue hérite
    bien de `MagasinScopedViewSet`, `issubclass` répond oui, et pourtant
    `GenericAPIView.get_queryset` gagne le MRO. La portée disparaît **sans erreur**, ce qui
    est exactement le mode de défaillance que toute cette phase refuse.

    C'est le prix du choix « mixin plutôt que sous-classe de `ModelViewSet` », fait pour
    que la caisse de la phase 7 — un registre en ajout seul, CLAUDE.md #4 — n'hérite pas
    d'un `update` et d'un `destroy` dont elle ne veut pas. Le prix est payé ici.
    """
    from rest_framework.generics import GenericAPIView

    from domaine.magasins.models import MagasinScopedModel
    from plateforme.projection.vues import MagasinScopedViewSet

    fautives: list[str] = []
    for vue in vues:
        modele = _modele_de_la_vue(vue)
        if modele is None or not issubclass(modele, MagasinScopedModel):
            continue
        etiquette = f"{vue.__module__}.{vue.__qualname__}"
        mro = vue.__mro__
        if MagasinScopedViewSet not in mro:
            fautives.append(f"{etiquette} : pas de MagasinScopedViewSet")
        elif GenericAPIView in mro and mro.index(MagasinScopedViewSet) > mro.index(
            GenericAPIView
        ):
            fautives.append(
                f"{etiquette} : MagasinScopedViewSet arrive après GenericAPIView dans le "
                "MRO, donc get_queryset() de DRF gagne et la portée ne s'applique pas"
            )
    return fautives


# ======================================================================================
# Garde 3 — la projection oubliée sur un sérialiseur (A-03-08)
# ======================================================================================
def tous_les_serializers() -> list[type]:
    """Toute sous-classe de `ModelSerializer` chargée, hors celles de DRF lui-même."""
    from rest_framework import serializers

    return [
        classe
        for classe in _sous_classes(serializers.ModelSerializer)
        if not classe.__module__.startswith("rest_framework")
    ]


def serializers_sans_projection(classes) -> list[str]:
    """Les sérialiseurs qui exposent un champ du registre sans hériter de `SerializerProjete`.

    Le jumeau de `vues_sans_portee_magasin`, côté champs. `ArticleSerializer` est sûr tout
    seul ; la phase 6 l'imbriquera dans `LigneVenteSerializer`, et un `ModelSerializer`
    ordinaire y ressusciterait `prix_achat` sans qu'une ligne change dans le registre
    (A-03-08). Le registre est clé par champ de modèle précisément pour que ce garde soit
    écrivable.

    Le contrôle porte sur `Meta.fields` et non sur les champs instanciés : instancier
    exigerait un contexte, et un sérialiseur interrogé sans contexte a déjà perdu ses
    champs protégés — le garde passerait en n'examinant que la moitié publique.
    """
    from plateforme.projection.registre import codes_proteges_de
    from plateforme.projection.serializers import SerializerProjete

    fautifs: list[str] = []
    for classe in classes:
        modele = getattr(getattr(classe, "Meta", None), "model", None)
        if modele is None:
            continue
        proteges = set(codes_proteges_de(modele))
        if not proteges:
            continue
        declares = getattr(getattr(classe, "Meta", None), "fields", None)
        if declares == "__all__" or declares is None:
            exposes = proteges
        else:
            exposes = proteges & set(declares)
        if not exposes:
            continue
        if not issubclass(classe, SerializerProjete):
            fautifs.append(
                f"{classe.__module__}.{classe.__qualname__} expose {sorted(exposes)} "
                "sans hériter de SerializerProjete"
            )
    return fautifs
