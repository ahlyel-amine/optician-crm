"""CLIENT-01 — la fiche client, et les trois colonnes que la recherche interroge.

Un seul modèle, et l'essentiel de ce fichier explique ce qu'il **refuse** d'être : une
entité magasin-scopée. Cette décision est clinique, pas ergonomique, et elle est invisible
dans le code une fois prise — d'où la longueur de la docstring qui la porte.
"""

from __future__ import annotations

from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db import models, router
from django.db.models import F, Q

from domaine.clients import recherche


class Client(models.Model):
    """Une personne qui achète chez cet opticien. **Pas magasin-scopée, délibérément.**

    `Client` n'hérite **pas** de `MagasinScopedModel`, et ce n'est pas un oubli : une
    personne appartient à l'affaire, pas à un point de vente. Elle achète à Anfa
    aujourd'hui et à Maârif dans six mois, et c'est la même personne. La scoper
    produirait deux fiches pour un humain, donc deux historiques de prescription
    divergents pour un seul œil — ce que la décision D-4a du propriétaire nomme comme un
    danger clinique et non comme une gêne d'interface.

    **Conséquence à ne pas manquer.** Le garde `vues_sans_portee_magasin` de
    `plateforme/projection/checks.py` ne se déclenche **que** sur un modèle héritant de
    `MagasinScopedModel`. Il est donc structurellement aveugle à celui-ci, dans un sens
    comme dans l'autre : il ne dira ni qu'il manque une portée, ni qu'il n'en faut pas.
    La garde positive — « ce modèle ne doit PAS être scopé » — est écrite au plan 04-04,
    à côté de `Ordonnance`, où elle porte exactement le même raisonnement.

    **`date_naissance`, qu'aucune exigence CLIENT ne nomme, et qui entre quand même.**
    Deux justifications indépendantes, et la seconde suffit seule :

    * RAPPEL-04 (phase 10) applique la règle AMO des onze mois aux enfants de douze ans
      et moins, donc il lui faut un âge ;
    * `PITFALLS.md` rapporte, **de source secondaire**, qu'une ordonnance médicale est
      requise au Maroc en dessous de seize ans.

    La **colonne** ne dépend pas de la validité de la seconde ; seul l'avertissement A10
    en dépend, et il est un avertissement, jamais un refus. L'ajouter plus tard coûterait
    une migration **plus** une campagne de collecte sur toutes les fiches déjà saisies,
    ce qui est la sorte chère.

    **Le coût honnête des colonnes dérivées.** Changer la règle de normalisation exigera
    un `RunPython` de reprise sur `nom_recherche` et `cle_phonetique`. C'est précisément
    pour cela que le normaliseur est *une fonction nommée* dans `recherche.py` : la
    reprise sera un `RunPython` qui l'appelle, pas une réécriture de la règle.
    """

    nom = models.CharField(max_length=160)
    #: Le nom plié — accents, casse, espaces. C'est la colonne que l'index GIN porte, et
    #: la seule que le trigramme interroge. `editable=False` : elle n'est ni saisie ni
    #: écrite par une API, et un champ dérivé qu'un POST peut écrire est une seconde
    #: source de vérité (menace T-04-05).
    nom_recherche = models.CharField(max_length=160, editable=False)
    #: `metaphone(nom_recherche, 8)`. **Vide en écriture arabe**, et l'index ci-dessous
    #: refuse le vide — une clé vide qui sert de critère rapproche chaque fiche arabe de
    #: toutes les autres.
    cle_phonetique = models.CharField(max_length=16, blank=True, editable=False)
    telephone = models.CharField(max_length=30, blank=True)
    #: Les chiffres seuls. CLIENT-01 veut « retrouver par téléphone », et l'opticien tape
    #: le numéro comme il le lit : `06 12 34 56 78`, `0612345678`, `+212 6 …`.
    telephone_normalise = models.CharField(
        max_length=24, blank=True, editable=False, db_index=True
    )
    date_naissance = models.DateField(null=True, blank=True)
    adresse = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    actif = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "client"
        verbose_name_plural = "clients"
        indexes = [
            # Couche 2 du rappel : l'opérateur `<%` servi par un index GIN. C'est le seul
            # moyen d'obtenir une correspondance floue *indexée* — mesuré à 4,3 ms sur
            # 20 400 lignes, contre un balayage séquentiel sans lui.
            GinIndex(
                OpClass(F("nom_recherche"), name="gin_trgm_ops"),
                name="idx_client_nom_trgm",
            ),
            # Couche 3 : l'égalité de clé phonétique, sur un btree ordinaire parce que
            # `metaphone` est `IMMUTABLE`.
            #
            # **L'index est partiel, et ce n'est pas une optimisation.** Une clé vide —
            # ce que rend toute écriture arabe — correspondrait à toutes les autres clés
            # vides, donc chaque fiche en arabe rapprocherait toutes les autres :
            # la fiche du voisin, ordonnances comprises (menace T-04-02). La garde vit
            # des deux côtés : ici dans l'index, et au plan 04-03 dans la requête, qui
            # saute la branche phonétique quand la clé de la requête est vide.
            models.Index(
                fields=["cle_phonetique"],
                name="idx_client_phonetique",
                condition=~Q(cle_phonetique=""),
            ),
            # Couche 1 et le tri de la liste. La collation ICU `fr-FR` posée à la
            # création de la base est ce qui rend cet ordre lisible par un francophone.
            models.Index(fields=["nom"], name="idx_client_nom"),
        ]

    def __str__(self) -> str:
        return self.nom

    def save(self, *args, **kwargs):
        """Recalcule les trois colonnes dérivées, inconditionnellement, avant d'écrire.

        Inconditionnellement plutôt que « si le nom a changé » : une dérivée qui n'est
        rafraîchie que sur détection de changement finit par diverger le jour où le
        chemin de détection a un trou, et la divergence est muette — la fiche est
        correcte à l'écran et introuvable à la recherche.

        **L'alias est demandé au routeur de Django, pas à `plateforme.tenancy`.**
        `domaine/*` n'importe rien de la couche de tenancy sauf `MagasinScopedModel`
        (convention posée dans `domaine/magasins/models.py`), et `router.db_for_write`
        interroge de toute façon `TenantRouter`, qui lit le contextvar et **lève** quand
        rien n'est lié. Le comportement est identique et la couche reste étanche.
        """
        alias = kwargs.get("using") or router.db_for_write(type(self), instance=self)

        self.nom_recherche = recherche.normaliser_pour_recherche(self.nom)
        self.telephone_normalise = recherche.normaliser_telephone(self.telephone)
        self.cle_phonetique = recherche.cle_phonetique(self.nom_recherche, alias=alias)

        if update_fields := kwargs.get("update_fields"):
            # Un `update_fields` qui ne nommerait pas les dérivées écrirait le nom et
            # laisserait la colonne indexée sur l'ancienne valeur — la fiche serait
            # correcte et introuvable. Les trois sont donc toujours ajoutées.
            kwargs["update_fields"] = {*update_fields, *DERIVEES}

        super().save(*args, **kwargs)


#: Les trois colonnes que `save()` recalcule. Nommées pour que l'ajout à `update_fields`
#: ci-dessus n'ait pas à les recopier, et pour que la reprise par `RunPython` du jour où
#: la normalisation change les lise ici.
DERIVEES = ("nom_recherche", "telephone_normalise", "cle_phonetique")


class EquivalenceNom(models.Model):
    """La couche 4 du rappel : les équivalences de prénoms, **en donnée et non en code**.

    **Une appartenance à un groupe, jamais une paire, et c'est structurel.** Une table de
    paires exigerait d'écrire les deux sens — `mhamed → mohamed` *et*
    `mohamed → mhamed` — et l'un des deux manquerait, un jour, sur une ligne. La requête
    joint son propre jeton normalisé à `groupe`, puis accepte **tout** membre de ce
    groupe : la symétrie est alors une propriété de la forme, pas une discipline de
    saisie.

    **Amorcée par base client**, dans le point d'extension de `seed_new_client`, et non
    dans le plan de contrôle. Deux raisons, indépendantes : le plan de contrôle porte
    l'identité, la base client porte les données métier (CLAUDE.md #11) ; et un opticien
    qui ajoute une variante locale — `source = "opticien"` — ne doit pas l'imposer à la
    flotte.

    **La liste d'amorce est courte, délibérément.** Les couches 2 et 3 couvrent la traîne.
    Une grande table d'équivalences non validée est une machine à faux positifs,
    c'est-à-dire à fiches du voisin : `AMORCE_DES_EQUIVALENCES` ci-dessous ne contient
    donc **ni** `fatima`/`fatiha`, **ni** `abdelkader`/`abdelkrim`, **ni**
    `rachid`/`rachida`, qui sont trois paires de personnes différentes mesurées comme
    proches.
    """

    AMORCE = "amorce"
    OPTICIEN = "opticien"
    SOURCES = [
        (AMORCE, "Livrée avec le produit"),
        (OPTICIEN, "Ajoutée par l'opticien"),
    ]

    #: Le jeton tel que `normaliser_pour_recherche` le rend — `'mhamed'`.
    forme_normalisee = models.CharField(max_length=80, db_index=True)
    #: La clé canonique du groupe — `'mohamed'`. Elle est elle-même une forme, et elle a
    #: sa propre ligne : sans cela, chercher la forme canonique ne rendrait pas ses
    #: variantes.
    groupe = models.CharField(max_length=80, db_index=True)
    source = models.CharField(max_length=16, choices=SOURCES, default=AMORCE)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "équivalence de nom"
        verbose_name_plural = "équivalences de noms"
        constraints = [
            # L'unicité est ce qui rend `get_or_create` de l'amorçage réellement
            # idempotent plutôt qu'idempotent par convention : une amorce rejouée sur une
            # base à demi provisionnée ne peut pas doubler une ligne.
            models.UniqueConstraint(
                fields=["forme_normalisee", "groupe"],
                name="unique_forme_dans_un_groupe",
            )
        ]

    def __str__(self) -> str:
        return f"{self.forme_normalisee} → {self.groupe}"


#: L'amorce : vingt familles de prénoms qui reviennent réellement au comptoir marocain.
#:
#: Écrites déjà normalisées — minuscules, sans accent — mais repassées par
#: `normaliser_pour_recherche` à l'amorçage : une accentuation oubliée dans un littéral
#: produirait une ligne que la requête ne joindrait jamais, et l'échec serait muet.
#:
#: **Ce qui n'y est pas est aussi une décision.** Les trois paires que la mesure rapproche
#: et que la clinique sépare — `fatima`/`fatiha`, `abdelkader`/`abdelkrim`,
#: `rachid`/`rachida` — sont absentes, et `test_client10_deux_prenoms_distincts_ne_fusionnent_pas`
#: rougit le jour où l'une d'elles y entre.
AMORCE_DES_EQUIVALENCES: dict[str, tuple[str, ...]] = {
    "mohamed": ("mohamed", "mohammed", "mhamed", "mouhamed", "mohamad", "muhammad"),
    "fatima": ("fatima", "fatma", "fatimazahra"),
    "khadija": ("khadija", "khdija", "khadidja"),
    "youssef": ("youssef", "yousef", "youssouf"),
    "abdelkader": ("abdelkader", "abdelkadir", "abdelqader"),
    "abdelkrim": ("abdelkrim", "abdelkarim", "abdulkarim"),
    "el hassan": ("el hassan", "elhassan", "lhassan"),
    "aicha": ("aicha", "aycha"),
    "naima": ("naima", "nayma"),
    "zoubair": ("zoubair", "zubair", "zoubeir"),
    "abdellah": ("abdellah", "abdallah", "abdoullah"),
    "ibrahim": ("ibrahim", "brahim"),
    "meryem": ("meryem", "mariam", "maryam", "mariem"),
    "yassine": ("yassine", "yacine", "yassin"),
    "soukaina": ("soukaina", "soukayna"),
    "zineb": ("zineb", "zeineb"),
    "hicham": ("hicham", "hichame"),
    "omar": ("omar", "oumar", "omer"),
    "salma": ("salma", "selma"),
    "karim": ("karim", "karime", "kareem"),
}
