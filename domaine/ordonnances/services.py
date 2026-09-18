"""CLIENT-06 — enregistrer une version, et lire la version en cours.

Trois fonctions, et une seule règle qui gouverne les trois : **une ordonnance ne se
modifie pas, elle se remplace.** Ce module est donc en écriture seule vers l'avant — il
insère, il ne met jamais à jour — et en lecture il ne rend jamais qu'une **sélection**,
jamais une agrégation de deltas.

## Pourquoi un service et non une méthode de sérialiseur

`create()` sur un sérialiseur ferait exactement la même chose, en moins d'endroits.
Refusé pour une raison datée : la phase 12 prévoit une reprise de données, la phase 5 une
commande spéciale qui part d'une ordonnance, et l'une comme l'autre s'écrit dans une
commande de gestion, sans requête HTTP. Un service lève donc les exceptions de **Django**
— `ValidationError` — que la vue traduit, et non celles de DRF, qui exigeraient un
contexte de requête pour avoir du sens. C'est l'idiome que `plateforme/comptes/views.py`
a établi au plan 03-08.
"""

from __future__ import annotations

from decimal import ROUND_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import router, transaction
from django.db.models import Max, Prefetch
from django.utils import timezone

from domaine.ordonnances.models import Ordonnance, TypeRevision
from domaine.ordonnances.stockage import EXTENSIONS
from plateforme.numerotation import numero_suivant

#: L'attribut que `avec_la_derniere_ordonnance` pose sur chaque fiche. Nommé ici plutôt
#: qu'écrit trois fois : le sérialiseur le lit, la vue le pose, et un nom recopié entre
#: les deux se désaccorderait en rendant `null` — donc « ce client n'a pas d'ordonnance »
#: — au lieu de lever. Un nombre faux sans erreur, ce que tout ce dépôt refuse.
ATTRIBUT_PRECHARGE = "_versions_les_plus_recentes"


def enregistrer_ordonnance(*, client, magasin, valeurs: dict, par: str) -> Ordonnance:
    """Insère une **nouvelle version**, dont le numéro est émis ici, sous verrou.

    ## Le verrou, et pourquoi il porte sur la fiche client

    `Client.objects.select_for_update().get(pk=...)` sérialise les insertions **de ce
    dossier-là**. Deux comptoirs qui enregistrent pour deux clients différents ne se
    bloquent donc pas, là où un verrou de table les mettrait en file. La lecture du
    maximum et l'`INSERT` sont dans la même transaction que ce verrou — c'est la seule
    disposition qui rende `(client, version)` sûr, et l'unicité en base est le filet, pas
    la garantie.

    **Jamais une `SEQUENCE` PostgreSQL.** Elle ne revient pas en arrière à l'annulation,
    donc elle produit des trous. Sur une version d'ordonnance un trou est une gêne ; sur
    la série des factures de la phase 6 il est traitable comme une fraude, et c'est le
    **même** mécanisme qui sera réutilisé — l'écrire deux fois différemment serait la
    vraie dette (CLAUDE.md #3, `plateforme/numerotation.py`).

    ## Ce que le service refuse, et que la base ne peut pas refuser

    Une `correction` doit dire **ce qu'elle remplace** et **pourquoi** ; un
    `renouvellement` n'est la correction de rien et n'exige ni l'un ni l'autre. Et un
    `supersede` doit appartenir au **même dossier** : la clé étrangère pointe vers
    `Ordonnance` en général, donc la base accepte parfaitement qu'une correction du
    dossier A désigne une version du dossier B. L'historique dirait alors « remplace la
    version 2 » en renvoyant vers la fiche de quelqu'un d'autre — une divulgation de
    donnée de santé, pas une incohérence d'affichage.

    `par` est une **adresse**, pas une clé étrangère : les comptes vivent dans le plan de
    contrôle (CLAUDE.md #11) et le routeur refuse la relation. La chaîne reste lisible dix
    ans plus tard (art. 211 CGI), même compte désactivé.

    ## L'alias est demandé au routeur, jamais écrit ni laissé au défaut

    `transaction.atomic()` sans `using` ouvre une transaction sur `default`, c'est-à-dire
    sur le **plan de contrôle** : le verrou serait alors posé ailleurs que l'insertion, et
    `select_for_update()` ne sérialiserait rien du tout. L'alias vient donc de
    `router.db_for_write`, qui lit le contextvar et **lève** quand rien n'est lié — un
    service appelé hors contexte échoue fermé plutôt que d'écrire dans la mauvaise base
    (CLAUDE.md #8). C'est aussi pourquoi `ATOMIC_REQUESTS` n'existe pas ici :
    CLAUDE.md #15 interdit le réglage global, et un bloc explicite est de toute façon la
    seule forme qui puisse nommer l'alias.
    """
    alias = router.db_for_write(Ordonnance)
    with transaction.atomic(using=alias):
        return _inserer_la_version(
            client=client, magasin=magasin, valeurs=valeurs, par=par
        )


def _inserer_la_version(*, client, magasin, valeurs, par) -> Ordonnance:
    """Le corps de `enregistrer_ordonnance`, **à l'intérieur** de la transaction.

    Séparé pour que l'ouverture de la transaction et le verrou soient lisibles d'un coup
    d'œil au-dessus, et pour qu'aucune relecture ne puisse déplacer par mégarde le
    `select_for_update()` hors du bloc — ce qui le rendrait silencieusement inopérant.
    """
    from domaine.clients.models import Client

    # Le verrou d'abord, la lecture du maximum ensuite : l'ordre inverse lirait un
    # maximum qu'un autre fil peut encore faire bouger, et le verrou n'aurait plus rien
    # à sérialiser.
    client = Client.objects.select_for_update().get(pk=client.pk)

    supersede = valeurs.get("supersede")
    type_revision = valeurs.get("type_revision") or ""
    motif = (valeurs.get("motif_revision") or "").strip()

    if type_revision == TypeRevision.CORRECTION:
        if supersede is None:
            raise ValidationError(
                {
                    "supersede": "Une correction doit dire quelle version elle remplace.",
                }
            )
        if not motif:
            raise ValidationError(
                {
                    "motif_revision": (
                        "Dites ce qui était faux. Cela restera lisible : c'est ce qui "
                        "distingue une correction assumée d'une réécriture silencieuse."
                    )
                }
            )
    if supersede is not None and supersede.client_id != client.pk:
        raise ValidationError(
            {
                "supersede": (
                    "Cette version appartient à un autre dossier. Une correction ne "
                    "remplace que l'historique de son propre client."
                )
            }
        )

    maximum = Ordonnance.objects.filter(client=client).aggregate(
        dernier=Max("version")
    )["dernier"]

    champs = {
        cle: valeur
        for cle, valeur in valeurs.items()
        # `version` n'est pas dans le sérialiseur d'écriture ; ce filtre est la seconde
        # moitié de T-04-31, pour l'appelant hors HTTP qui la passerait par distraction.
        if cle != "version"
    }
    champs["motif_revision"] = motif

    return Ordonnance.objects.create(
        client=client,
        magasin=magasin,
        version=numero_suivant(maximum),
        created_par=par,
        **champs,
    )


def avec_la_derniere_ordonnance(queryset):
    """Le même queryset de fiches, chacune portant ses versions déjà chargées.

    **Une requête de plus au total, jamais une par ligne.** Une liste de deux cents
    clients au comptoir doit coûter deux requêtes, pas deux cent une — et l'intention
    écrite dans une docstring ne tient rien : c'est
    `test_client06_le_resume_de_la_fiche_ne_fait_pas_une_requete_par_ligne` qui la mesure.

    Le tri est `-version` et **non** l'ordre par défaut du modèle, qui commence par
    `-date_prescription` : la « version en cours » est celle qui porte le plus grand
    numéro, pas la plus récemment prescrite. Les deux coïncident presque toujours et
    divergent exactement là où cela compte — une correction saisie aujourd'hui pour une
    ordonnance de l'an dernier.
    """
    return queryset.prefetch_related(
        Prefetch(
            "ordonnances",
            queryset=Ordonnance.objects.order_by("-version"),
            to_attr=ATTRIBUT_PRECHARGE,
        )
    )


def derniere_ordonnance_de(fiche) -> Ordonnance | None:
    """La version en cours d'une fiche, préchargée si elle l'est, chargée sinon.

    **Le repli est délibéré, et il n'annule pas la promesse de performance.** Un
    sérialiseur qui rendrait `None` faute d'attribut préchargé produirait « ce client n'a
    pas d'ordonnance » là où la vérité est « l'appelant a oublié le `prefetch` » : un
    nombre faux sans erreur, servi sur une donnée clinique. La correction est donc
    **toujours** juste ; c'est la vue, et le test qui compte ses requêtes, qui la rendent
    aussi rapide. L'export et le document — les deux autres consommateurs du registre —
    passent par le même chemin sans avoir à connaître le préchargement.
    """
    prechargees = getattr(fiche, ATTRIBUT_PRECHARGE, None)
    if prechargees is not None:
        return prechargees[0] if prechargees else None
    return fiche.ordonnances.order_by("-version").first()


# ======================================================================================
# CLIENT-09 — attacher la photo, une fois
# ======================================================================================
#: Les cinq colonnes que l'attache écrit, et les seules. Nommées ici plutôt que recopiées
#: dans l'appel : c'est ce qui rend mécanique le « cette transition et rien d'autre » de
#: `04-UI-SPEC.md` §22.3, et c'est ce que le test compare champ par champ.
COLONNES_DE_LA_PHOTO = (
    "photo",
    "photo_type",
    "photo_octets",
    "photo_attachee_le",
    "photo_par",
)

#: Les octets magiques, par type réel. **L'extension et le type MIME sont tous deux
#: choisis par l'appelant**, donc ni l'un ni l'autre n'est une preuve ; ces octets-ci
#: sont produits par l'encodeur.
#:
#: Pillow n'est **pas** ajoutée pour autant. `ImageField` prouverait seulement que les
#: octets sont décodables, et poser une bibliothèque d'images sur un flux non fiable
#: élargit la surface d'attaque au service d'une garantie dont ce plan n'a pas besoin
#: (T-04-43).
_MARQUES_HEIC = frozenset({b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"})

#: Combien d'octets il faut lire pour trancher. Douze suffisent pour WEBP (`RIFF....WEBP`)
#: et pour HEIC (`....ftypheic`) ; seize par confort de lecture.
_TETE = 16

MESSAGE_PAS_UNE_IMAGE = (
    "Ce fichier n'est pas une image. Formats acceptés : JPG, PNG, WEBP, HEIC."
)
MESSAGE_UNE_SEULE_FOIS = (
    "Une photo ne se remplace pas. Pour corriger, enregistrez une nouvelle version."
)


class PhotoDejaAttachee(Exception):
    """Cette version porte déjà une photo. Ce n'est pas une requête mal formée.

    **Pas une `ValidationError`, et la distinction porte jusqu'au code HTTP.** Le corps
    de la requête est parfaitement valide ; c'est l'**état de la ressource** qui interdit
    l'écriture. La vue rend donc 409 et non 400 — et surtout jamais 200, qui est la seule
    réponse que ce refus existe pour empêcher.
    """


def _type_des_octets(tete: bytes) -> str | None:
    """Le type que les **octets** revendiquent, ou `None` si ce n'est aucun des quatre."""
    if tete.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if tete.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if tete.startswith(b"RIFF") and tete[8:12] == b"WEBP":
        return "image/webp"
    # `ftyp` est à l'offset 4 d'un conteneur ISO-BMFF, mais l'écrire ainsi recopierait un
    # littéral que la garde des nombres cliniques attrape — `4` est l'addition maximale.
    # Le chercher dans la tête et **épingler la marque** à sa position exacte dit la même
    # chose sans le nombre, et la marque est le contrôle qui compte.
    if b"ftyp" in tete[:12] and tete[8:12] in _MARQUES_HEIC:
        return "image/heic"
    return None


#: Un mégaoctet, en `Decimal` — jamais en flottant. Même règle que l'argent (CLAUDE.md
#: #7) : le nombre affiché est calculé, donc il se calcule juste.
UN_MEGAOCTET = Decimal(1024 * 1024)
_UN_DIXIEME = Decimal("0.1")


def _en_megaoctets(octets: int) -> str:
    """`10,1` — arrondi **vers le haut** au dixième, virgule décimale.

    Vers le haut parce qu'un plafond annoncé plus petit que la taille réelle fait
    relancer le même fichier. En mégaoctets parce que `10485761` ne dit rien à personne
    (`04-UI-SPEC.md` §22.1 : jamais des octets, jamais un type MIME à l'écran).

    L'arrondi passe par `quantize` et non par une division entière : la forme naturelle
    — `ceil(octets * 10 / (1024 * 1024))` — recopie deux littéraux que la garde des
    nombres cliniques attrape, `10` étant la borne du cylindre.
    """
    megaoctets = (Decimal(octets) / UN_MEGAOCTET).quantize(
        _UN_DIXIEME, rounding=ROUND_UP
    )
    return f"{megaoctets:f}".rstrip("0").rstrip(".").replace(".", ",")


def attacher_photo(ordonnance, fichier, *, par: str):
    """Pose la photo sur une version qui n'en a pas. La seule mutation permise. CLIENT-09.

    ## `null -> posée`, et rien d'autre

    Une ordonnance est immuable (CLIENT-06). La décision §28-Q5 ouvre **une** exception,
    et pour une raison de comptoir : le papier est souvent scanné le lendemain, et
    interdire l'ajout obligerait à créer une version qui ne change aucune valeur
    clinique — donc à polluer l'historique que CLIENT-06 existe pour protéger.

    L'écriture nomme donc ses colonnes par `update_fields`, et non un `save()` nu. C'est
    ce qui rend la promesse mécanique plutôt que documentaire : un `save()` nu
    réécrirait toute la ligne, et un `UPDATE` général reviendrait par cette porte-là.

    **Mesuré, et à savoir avant de lire le SQL :** `Ordonnance.save()` élargit
    `update_fields` avec `COLONNES_CANONICALISEES` (plan 04-04), donc l'ordre nomme neuf
    colonnes et non cinq. Les quatre supplémentaires sont réécrites à l'identique — elles
    étaient déjà canoniques, les contraintes de base l'exigent — et l'élargissement
    existe pour qu'une écriture ciblée ne puisse pas laisser un axe de 0 en base. La
    garantie « rien d'autre n'a bougé » est donc tenue sur les **valeurs**, et c'est
    ainsi que le test la vérifie.

    ## Ce qui est refusé, et dans cet ordre

    1. une photo déjà posée — `PhotoDejaAttachee`, donc 409 ;
    2. la taille, **avant** de lire le moindre octet du contenu ;
    3. le type déclaré, contre la liste du réglage ;
    4. les **octets magiques**, qui priment sur le type déclaré.

    ## Le nom du fichier envoyé ne survit à rien

    Ni sur le disque, ni en colonne, ni dans un message d'erreur. Un nom de fichier
    téléversé porte couramment le nom du patient (`ordonnance_benali_ahmed.jpg`), et une
    chaîne d'erreur est la seule chaîne du produit qui atteint Sentry de façon fiable.
    Le nom stocké est fabriqué par `StockageOrdonnances.get_available_name` — dans le
    stockage, pas seulement ici, pour qu'un futur appelant distrait ne puisse pas
    contourner la règle.
    """
    if ordonnance.photo:
        raise PhotoDejaAttachee(MESSAGE_UNE_SEULE_FOIS)

    taille = int(fichier.size or 0)
    if taille > settings.ORDONNANCE_TAILLE_MAX_OCTETS:
        raise ValidationError(
            {
                "fichier": (
                    f"Cette image fait {_en_megaoctets(taille)} Mo. La limite est de "
                    f"{_en_megaoctets(settings.ORDONNANCE_TAILLE_MAX_OCTETS)} Mo."
                )
            }
        )
    if taille == 0:
        raise ValidationError({"fichier": MESSAGE_PAS_UNE_IMAGE})

    declare = (getattr(fichier, "content_type", "") or "").split(";")[0].strip().lower()
    if declare not in settings.ORDONNANCE_TYPES_ACCEPTES:
        raise ValidationError({"fichier": MESSAGE_PAS_UNE_IMAGE})

    fichier.seek(0)
    reel = _type_des_octets(fichier.read(_TETE))
    fichier.seek(0)
    if reel is None or reel != declare:
        # Le message est **le même** que pour un type refusé, et c'est délibéré : la
        # vérité utile à l'opticien est identique, et un message distinct apprendrait à
        # un appelant hostile que les octets sont inspectés.
        raise ValidationError({"fichier": MESSAGE_PAS_UNE_IMAGE})

    # `<version>/<nom>` : le stockage remplace le nom par un `uuid4` et ne garde que le
    # dossier et l'extension. Le dossier est le numéro de version, et le stockage refuse
    # tout dossier qui n'est pas un nombre.
    nom = f"{ordonnance.version}/photo{EXTENSIONS[reel]}"
    ordonnance.photo.save(nom, fichier, save=False)
    ordonnance.photo_type = reel
    ordonnance.photo_octets = taille
    ordonnance.photo_attachee_le = timezone.now()
    ordonnance.photo_par = par
    ordonnance.save(update_fields=list(COLONNES_DE_LA_PHOTO))
    return ordonnance
