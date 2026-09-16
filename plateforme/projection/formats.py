"""Le formateur serveur : `1 800,00 MAD` et `14/09/2026`, épinglés à la main.

**Pourquoi ce module existe alors que Django sait formater des nombres.** « Conventions
françaises » a trois réponses différentes, et elles ne sont pas d'accord
(`03-RESEARCH.md` §7, vérifié) : le locale `fr` de Django groupe les milliers avec un
U+00A0, l'ICU `fr-FR` des navigateurs avec un U+202F, et l'étiquette marocaine `fr-MA`
avec **un point**. Le même montant s'affiche donc `1.800,00 MAD` à l'écran et
`1 800,00 MAD` sur la facture, sans qu'aucun test ne le voie, puisque chaque côté est
cohérent avec lui-même. **Aller chercher une base de locales est le bug** (CLAUDE.md #14,
menaces T-03-67 et T-03-68).

Deux implémentations sont inévitables — celle-ci rend un PDF en Python (phase 9), l'autre
rend le DOM dans un navigateur (`web/src/format/`). L'objectif atteignable n'est donc pas
« un seul formateur » mais **une seule spécification, deux implémentations testées contre
elle**.

**Et la spécification n'est pas lue d'ici.** Elle vit dans `formats_mad.json`, sous le
répertoire de tests, et ce module en **recopie** les constantes plutôt que de charger le
fichier à l'exécution. Lire le JSON depuis la production mettrait le répertoire de tests
sur le chemin d'exécution d'un module que WeasyPrint appellera en phase 9 — inacceptable.
Le prix de ce choix est qu'il y a deux endroits où le U+00A0 est écrit, et il est payé par
un test : `test_app03_les_constantes_du_formateur_viennent_de_la_fixture` compare ces
constantes à la fixture, point de code par point de code. Une divergence rend la suite
rouge. **Ne « simplifiez » donc pas ce module en important le JSON.**

**Ce qui est délibérément absent, et doit le rester.** Rien ici ne délègue à la couche de
localisation de Django ni à son filtre de gabarit d'arrondi, et aucun réglage global de
séparateur n'est activé. Le groupement y est inactif par défaut ; l'activer donnerait le
bon caractère **par accident** plutôt que par décision, et une prochaine mise à jour des
données de locale de Django pourrait le changer sous nos pieds sans qu'une ligne de ce
dépôt ne bouge. `test_app03_le_formateur_n_appuie_sur_aucune_base_de_locale` l'interdit
au niveau du source, parce que la sortie, elle, aurait l'air juste le jour de la bascule.

**Le fuseau est converti ici, jamais dans les réglages.** `TIME_ZONE = "UTC"` est porteur
pour PgBouncer : `_configure_timezone` n'émet un `SET TIMEZONE` que si le serveur en
annonce un autre, et une connexion serveur porteuse de ce réglage retourne au pool en le
gardant (menace T-02-02). La conversion d'affichage est donc le travail du formateur.

**Le piège du Ramadan, noté et non résolu (T-03-72).** Le Maroc est à UTC+1 toute
l'année *sauf* un retour à UTC+0 pendant le Ramadan. `zoneinfo` connaît ces transitions,
donc l'affichage d'un instant passé est juste. Ce qui ne l'est pas encore est la notion de
« journée » : une borne de « CA du jour » calculée en UTC glisse d'une heure ce mois-là et
attrape ou perd les ventes de fin de journée. C'est un problème de **phase 10**, à
résoudre avec une fonction de bornes de journée locale, pas ici.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext
from zoneinfo import ZoneInfo

#: Séparateur de groupes de milliers : U+00A0, espace insécable. Recopié de la fixture.
SEPARATEUR_MILLIERS = "\u00a0"
#: Séparateur décimal.
SEPARATEUR_DECIMAL = ","
#: Séparateur entre le nombre et le sigle : U+00A0, pour que la ligne ne coupe jamais.
SEPARATEUR_AVANT_DEVISE = "\u00a0"
#: Décimales, toujours affichées, `,00` compris.
DECIMALES = 2
#: Le sigle monétaire. Jamais « Dhs », jamais « DH » : la facture porte le code ISO.
DEVISE = "MAD"
#: Le fuseau d'**affichage**. Voir la docstring du module : il n'est pas dans les réglages.
FUSEAU_AFFICHAGE = "Africa/Casablanca"

#: Les deux espaces autour du `à` sont des U+0020 ordinaires — c'est la fixture qui le
#: dit. L'espace insécable est la convention de la **monnaie**, pas celle des dates.
SEPARATEUR_DATE_HEURE = " \u00e0 "

_QUANTUM = Decimal(1).scaleb(-DECIMALES)
_ZONE = ZoneInfo(FUSEAU_AFFICHAGE)


def _en_decimal(valeur: Decimal | int | str) -> Decimal:
    """Refuse un `float`, plutôt que de lui rendre service (CLAUDE.md #7).

    Un formateur tolérant est pire qu'un formateur strict : il rendrait une chaîne
    parfaitement crédible au-dessus d'un binaire déjà faux, et la perte aurait eu lieu
    chez l'appelant, hors de portée de tout test de formatage. Le refus est la dernière
    place où l'erreur est encore attribuable.

    `bool` est refusé aussi, pour une raison moins évidente : il est une sous-classe de
    `int`, donc `formater_montant(True)` rendrait `1,00 MAD` sans rien signaler.
    """
    if isinstance(valeur, Decimal):
        return valeur
    if isinstance(valeur, float):
        raise TypeError(
            "formater_montant refuse un float : la précision est déjà perdue avant "
            f"d'arriver ici (reçu {valeur!r}). L'argent est un Decimal, de bout en bout "
            "(CLAUDE.md #7). DRF livre les montants en chaîne, qui est acceptée telle "
            "quelle."
        )
    if isinstance(valeur, bool) or not isinstance(valeur, (int, str)):
        raise TypeError(
            f"formater_montant attend un Decimal, un int ou la chaîne livrée par l'API, "
            f"reçu {type(valeur).__name__}."
        )
    return Decimal(valeur)


def _grouper(entier: str) -> str:
    """Groupe par trois à partir de la droite, avec l'espace insécable."""
    tete = len(entier) % 3 or 3
    morceaux = [entier[:tete]]
    morceaux += [entier[i : i + 3] for i in range(tete, len(entier), 3)]
    return SEPARATEUR_MILLIERS.join(morceaux)


def formater_montant(valeur: Decimal | int | str) -> str:
    """Rend un montant MAD : `1 800,00 MAD`. Négatif : `-12,30 MAD`.

    `ROUND_HALF_UP`, explicitement : le défaut de `quantize` — comme celui de `round()` —
    est l'arrondi au pair, qui rendrait `999,99` là où la fixture et le formateur client
    exigent `1 000,00`. Un demi-centime arrondi vers le bas une fois sur deux est une
    différence qu'une réconciliation trouve des mois plus tard.

    Le signe est porté par le texte. La couleur destructive du rendu vient **en plus** du
    signe, jamais à sa place (`03-UI-SPEC.md` 8.1) : une facture lue en noir et blanc, ou
    par un daltonien, doit rester juste.
    """
    montant = _en_decimal(valeur)
    with localcontext() as contexte:
        # La précision par défaut (28 chiffres significatifs) ferait lever `quantize` sur
        # un montant plus long, ce qui est un refus pour une raison qui n'a rien à voir
        # avec l'argent. Elle est relevée à la taille de l'entrée.
        contexte.prec = max(contexte.prec, len(montant.as_tuple().digits) + DECIMALES + 1)
        montant = montant.quantize(_QUANTUM, rounding=ROUND_HALF_UP)

    # `abs()` avant le formatage : `-0,001` arrondi à deux décimales vaut zéro, et
    # `Decimal("-0.00")` s'écrirait `-0,00 MAD` — un signe sans montant.
    signe = "-" if montant < 0 else ""
    entier, _, fraction = f"{abs(montant):f}".partition(".")
    return (
        f"{signe}{_grouper(entier)}{SEPARATEUR_DECIMAL}{fraction}"
        f"{SEPARATEUR_AVANT_DEVISE}{DEVISE}"
    )


def _en_instant_local(valeur: datetime | str) -> datetime:
    """Convertit vers l'heure de Casablanca. Un instant naïf est **refusé**.

    `USE_TZ = True`, donc tout `DateTimeField` remonte conscient de son fuseau ; un naïf
    vient d'un `datetime.now()` écrit à la main, et le formater reviendrait à deviner de
    quel instant il parle. Deviner faux décale l'affichage d'une heure sans rien dire.
    """
    instant = datetime.fromisoformat(valeur) if isinstance(valeur, str) else valeur
    if not isinstance(instant, datetime):
        raise TypeError(
            f"attendu un datetime conscient de son fuseau ou son ISO 8601, reçu "
            f"{type(valeur).__name__}."
        )
    if instant.tzinfo is None or instant.tzinfo.utcoffset(instant) is None:
        raise ValueError(
            "instant naïf : impossible de savoir de quel moment il s'agit, donc de "
            "l'afficher à l'heure de Casablanca. Les DateTimeField du produit sont "
            "conscients (USE_TZ = True)."
        )
    return instant.astimezone(_ZONE)


def formater_date_courte(valeur: datetime | date | str) -> str:
    """Rend `14/09/2026`, heure de Casablanca.

    `03/04/2026` et `04/03/2026` sont tous deux plausibles : une date mal ordonnée ne
    ressemble pas à une erreur, elle ressemble à une autre date, et sur une échéance de
    chèque elle se propage sans alerte. L'ordre est donc écrit ici, pas déduit.

    Un `date` sans heure est rendu tel quel : il ne désigne pas un instant, donc le
    convertir le décalerait d'un jour une fois sur vingt-quatre.
    """
    if isinstance(valeur, date) and not isinstance(valeur, datetime):
        jour = valeur
    else:
        jour = _en_instant_local(valeur)
    return f"{jour.day:02d}/{jour.month:02d}/{jour.year:04d}"


def formater_heure(valeur: datetime | str) -> str:
    """Rend `10:14`, heure de Casablanca, sur 24 heures."""
    instant = _en_instant_local(valeur)
    return f"{instant.hour:02d}:{instant.minute:02d}"


def formater_date_heure(valeur: datetime | str) -> str:
    """Rend `14/09/2026 à 10:14`, heure de Casablanca.

    Le cas de la fixture est choisi pour montrer la conversion : 09:14 UTC est 10:14 à
    Casablanca, et un instant de fin de journée change carrément de date.
    """
    instant = _en_instant_local(valeur)
    return f"{formater_date_courte(instant)}{SEPARATEUR_DATE_HEURE}{formater_heure(instant)}"
