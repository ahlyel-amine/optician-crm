"""Le corpus de noms marocains sur lequel les mesures de CLIENT-10 sont reproductibles.

Séparé des tests parce que le plan `04-07` le réutilisera pour l'écran, et parce qu'un
corpus recopié dans deux fichiers cesse d'être le même corpus au premier ajout.

---

## Ce que `04-RESEARCH.md` §5 énumère, et ce qu'il n'énumère pas

La recherche annonce « 30 distinct Moroccan first names » et une table de 20 400 lignes de
combinaisons prénom × nom, **mais elle n'écrit la liste nulle part**. Seuls les noms
qu'elle cite dans ses tableaux de mesure sont récupérables. Les vingt-huit premiers
prénoms ci-dessous sont exactement ceux-là, un par un ; les deux derniers sont marqués
comme des ajouts.

C'est une reconstruction, pas une recopie, et c'est écrit ici plutôt que dissimulé : les
nombres de §5 restent reproductibles pour **les paires qu'il cite** — qui sont toutes les
paires dont une décision dépend — et le corpus est désormais pinné, donc la prochaine
mesure sera comparable à celle-ci.

## Pourquoi les variantes accentuées ET non accentuées sont toutes deux présentes

`Aïcha` et `Aicha`, `Naïma` et `Naima`, `Zoubaïr` et `Zoubair` sont **deux entrées
chacune**. `normaliser_pour_recherche` les plie sur la même chaîne, ce qui est exactement
ce qu'un corpus doit permettre de vérifier : si quelqu'un retire le pliage NFKD, le
corpus contient encore les deux formes et la différence redevient visible.

## Les deux paires qui ne doivent JAMAIS fusionner

`Fatima` / `Fatiha` et `Abdelkader` / `Abdelkrim` sont dans le corpus **pour cela**. Ce
sont deux personnes distinctes dans chaque cas, et `04-RESEARCH.md` §5.2 mesure leur
similarité trigramme à 0,400 — au-dessus du 0,333 de `mohammed ↔ mhamed`, qui lui **doit**
correspondre. Aucun seuil scalaire ne sépare les deux exigences ; voir
`tests/test_recherche_clients.py`.
"""

from __future__ import annotations

#: Les trente prénoms. Les vingt-huit premiers sont cités nommément par
#: `04-RESEARCH.md` §5 ; `Karim` et `Nadia` sont des ajouts de ce fichier, signalés pour
#: qu'un lecteur ne les attribue pas au relevé.
PRENOMS: tuple[str, ...] = (
    # Le groupe MHMT de §5.5 — la famille que CLIENT-10 nomme.
    "Mhamed",
    "Mohamed",
    "Mohammed",
    "Mouhamed",
    # Cité par §5.4 comme la fusion que soundex commet et que metaphone évite.
    "Mahmoud",
    # La paire que §5.5 garde séparée (ABTLKTR / ABTLKRM) et que le trigramme fusionne.
    "Abdelkader",
    "Abdelkrim",
    # Le groupe FTM, et l'intruse qui n'en fait pas partie.
    "Fatima",
    "Fatma",
    "Fatiha",
    # Le groupe RXT — le seul faux positif reconnu de metaphone dans §5.5.
    "Rachid",
    "Rachida",
    # §5.2, les variantes d'orthographe qui doivent se retrouver.
    "Youssef",
    "Yousef",
    "Khadija",
    "Khdija",
    # §5.2, les voisins qui ne doivent pas se retrouver.
    "Mohcine",
    "Ahmed",
    "Hamed",
    # §5.5, l'accent latin plié par metaphone comme par la normalisation.
    "Aïcha",
    "Aicha",
    "Naïma",
    "Naima",
    "Zoubaïr",
    "Zoubair",
    # §5.5, l'échec anglo-saxon nommé : metaphone('ghali', 8) = 'FL'.
    "Ghali",
    # §5.2, l'espace interne.
    "Elhassan",
    "El Hassan",
    # Ajouts de ce fichier — non cités par §5.
    "Karim",
    "Nadia",
)

#: Vingt noms de famille marocains courants. `04-RESEARCH.md` n'en cite qu'un — `Alaoui`,
#: qui est le premier de la liste et celui que tous ses exemples emploient. Les dix-neuf
#: autres sont des ajouts de ce fichier : ils ne portent aucune mesure, ils fournissent la
#: masse sur laquelle l'index se prouve.
NOMS_DE_FAMILLE: tuple[str, ...] = (
    "Alaoui",
    "Bennani",
    "Idrissi",
    "Tazi",
    "Benjelloun",
    "Fassi",
    "Berrada",
    "Chraibi",
    "Lahlou",
    "Sqalli",
    "Amrani",
    "Bouazza",
    "Cherkaoui",
    "Naciri",
    "Ouazzani",
    "Sekkat",
    "Tahiri",
    "Zniber",
    "Mekouar",
    "Benkirane",
)

#: Le produit cartésien, dans un ordre stable. 30 × 20 = 600 noms complets.
NOMS_COMPLETS: tuple[str, ...] = tuple(
    f"{prenom} {famille}" for prenom in PRENOMS for famille in NOMS_DE_FAMILLE
)


def peupler_corpus(*, alias: str, limite: int | None = None) -> int:
    """Créer les fiches du corpus dans la base `alias`. Rend le nombre de lignes écrites.

    **`bulk_create` et non `Client()` + `save()`**, et la raison n'est pas la vitesse pour
    elle-même : `Client.save()` fait un aller-retour SQL par fiche pour calculer
    `metaphone`, donc six cents fiches feraient six cents allers-retours et le test qui
    prouve l'index passerait l'essentiel de son temps à peupler. Les trois colonnes
    dérivées sont donc calculées ici — les deux premières par les **mêmes** fonctions que
    `save()`, la troisième par **une seule** requête `unnest`.

    Le risque de cette optimisation est qu'elle duplique la règle de `save()`. Il est
    accepté parce qu'il est borné à trois lignes et qu'il est visible : les trois appels
    ci-dessous sont littéralement ceux du modèle, et `DERIVEES` les nomme.
    """
    from django.db import connections

    from domaine.clients import recherche
    from domaine.clients.models import Client

    noms = list(NOMS_COMPLETS if limite is None else NOMS_COMPLETS[:limite])
    normalises = [recherche.normaliser_pour_recherche(nom) for nom in noms]

    # `FROM unnest(...)` rend les lignes dans l'ordre du tableau, donc `zip` ci-dessous
    # est sûr. Une seule requête pour tout le corpus.
    with connections[alias].cursor() as curseur:
        curseur.execute(
            "SELECT metaphone(valeur, %s) FROM unnest(%s::text[]) AS valeur",
            [recherche.LONGUEUR_CODE_PHONETIQUE, normalises],
        )
        cles = [(ligne[0] or "") for ligne in curseur.fetchall()]

    fiches = [
        Client(
            nom=nom,
            nom_recherche=normalise,
            cle_phonetique=cle,
            telephone=f"06{index:08d}",
            telephone_normalise=f"06{index:08d}",
        )
        for index, (nom, normalise, cle) in enumerate(zip(noms, normalises, cles))
    ]
    Client.objects.using(alias).bulk_create(fiches)
    return len(fiches)
