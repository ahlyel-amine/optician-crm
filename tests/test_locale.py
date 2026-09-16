"""APP-01 et APP-03 — le français côté serveur, et le format marocain de l'argent et des dates.

Le fait qui rend ce fichier nécessaire est vérifié, pas supposé : « conventions
françaises » a **trois** réponses différentes et elles ne sont pas d'accord entre elles.
Le locale `fr` de Django groupe les milliers avec U+00A0, l'ICU `fr-FR` des navigateurs et
de Node utilise U+202F, et l'ICU **`fr-MA` utilise un point** — soit `1.800,00 MAD` à
l'écran contre `1 800,00 MAD` sur la facture, même montant, même produit, même journée
(`03-RESEARCH.md` §7). S'appuyer sur l'une ou l'autre base de locales **est** le bug.

D'où CLAUDE.md #14 : le format est épinglé explicitement, des deux côtés, depuis un seul
fichier — `tests/fixtures/formats_mad.json`. Ces tests en sont le premier consommateur ;
`web/tests/format.test.ts` (plan 03-11) en est le second, et c'est le fait qu'ils lisent
**le même fichier** qui empêche le serveur et le navigateur de diverger.

**Où vit la spécification, et pourquoi le code de production n'en lit pas le JSON.** La
fixture est sous `tests/`. Un `formats.py` qui la chargerait à l'exécution mettrait le
répertoire de tests sur le chemin de production — inacceptable pour un module que
WeasyPrint appellera en phase 9. Les constantes sont donc **inscrites** dans
`plateforme/projection/formats.py`, et c'est le test nommé
`..._les_constantes_du_formateur_viennent_de_la_fixture` qui interdit la divergence : la
spécification reste unique, et une retouche d'un seul côté rend la suite rouge.

Deux tests portent sur le JSON plutôt que sur l'affichage, et c'est CLAUDE.md #7 : un
montant qui traverse la frontière en flottant a déjà perdu sa précision avant qu'un
formateur ne le voie. `assert total == 1800.0` passe pendant que l'argent est faux
(`.planning/TESTING.md` §4).

**Aucun import du code en construction au niveau du module.**
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

#: La spécification partagée. Le chemin est écrit une fois ; `web/tests/format.test.ts`
#: remonte au même fichier depuis `web/`.
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "formats_mad.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _points_de_code(chaine: str) -> list[str]:
    """La forme sur laquelle on compare quand l'égalité de chaînes ne suffit pas.

    Un U+00A0 mué en espace ordinaire par un éditeur, un copier-coller ou un outil de
    formatage passe à l'œil nu et passe aussi `assert a == b` **dans le message d'erreur**,
    qui affiche les deux chaînes identiques. Comparer les points de code rend l'écart
    lisible : `U+00A0` contre `U+0020`.
    """
    return [f"U+{ord(c):04X}" for c in chaine]


# --------------------------------------------------------------------------------------
# APP-03 — le formateur serveur
# --------------------------------------------------------------------------------------
def test_app03_les_constantes_du_formateur_viennent_de_la_fixture():
    """Une seule spécification, deux implémentations — et c'est ce test qui tient le « une ».

    `formats.py` inscrit ses séparateurs en dur plutôt que de lire `tests/fixtures/` à
    l'exécution (voir la docstring du module). Le prix de ce choix est qu'il y a
    désormais deux endroits où le U+00A0 est écrit ; ce test est ce qui les recolle. Sans
    lui, quelqu'un corrigerait la fixture pour le client et le serveur continuerait
    tranquillement à rendre l'ancien caractère, ce qui est exactement la panne — écran et
    facture en désaccord — que CLAUDE.md #14 existe pour interdire.
    """
    from plateforme.projection import formats

    attendu = _fixture()

    assert _points_de_code(formats.SEPARATEUR_MILLIERS) == _points_de_code(
        attendu["separateur_milliers"]
    )
    assert _points_de_code(formats.SEPARATEUR_DECIMAL) == _points_de_code(
        attendu["separateur_decimal"]
    )
    assert _points_de_code(formats.SEPARATEUR_AVANT_DEVISE) == _points_de_code(
        attendu["separateur_avant_devise"]
    )
    assert formats.DECIMALES == attendu["decimales"]
    assert formats.DEVISE == attendu["devise"]
    assert formats.FUSEAU_AFFICHAGE == attendu["fuseau_affichage"]


def test_app03_le_formatage_serveur_respecte_la_fixture_partagee():
    """APP-03 / CLAUDE.md #14 — le serveur et le navigateur lisent le **même** fichier.

    Ce test lit `tests/fixtures/formats_mad.json` et exige que le formateur serveur rende
    chaque cas exactement. `format.test.ts` (plan 03-11) lit le même fichier et exige la
    même chose du formateur client. Rouge des deux côtés, ils disent « quelqu'un a changé
    le format » ; rouge d'un seul côté, ils disent « le serveur et le client ont divergé »,
    ce qui est la panne que CLAUDE.md #14 existe pour empêcher et qu'aucun test écrit d'un
    seul côté ne peut voir.

    Deux cas de la fixture portent plus que les autres. Le cas `999.995` doit rendre
    `1 000,00 MAD` : il épingle `ROUND_HALF_UP` sur un `Decimal`, là où le `round()` de
    Python arrondit au pair et rendrait un centime de moins une fois sur deux. Et le
    séparateur de milliers est un U+00A0, invisible en revue, qu'un éditeur peut remplacer
    par une espace ordinaire sans que rien ne le signale — d'où la comparaison sur les
    points de code, faite sur **chaque** cas plutôt qu'une fois pour l'exemple.
    """
    from plateforme.projection.formats import formater_montant

    cas = _fixture()["cas_montants"]
    assert cas, "La fixture ne porte aucun cas : le test serait vert et vide."

    for entree, attendu in cas:
        rendu = formater_montant(Decimal(entree))
        assert _points_de_code(rendu) == _points_de_code(attendu), (
            f"{entree} rendu {rendu!r} au lieu de {attendu!r}. La comparaison est faite "
            "sur les points de code : une espace insécable devenue ordinaire est ici "
            "visible, alors qu'une comparaison de chaînes l'aurait affichée à l'identique."
        )


def test_app03_le_formateur_refuse_un_flottant():
    """CLAUDE.md #7 — un `float` est refusé, jamais accepté « pour rendre service ».

    Un formateur tolérant est pire qu'un formateur strict : `formater_montant(1234.56)`
    rendrait une chaîne parfaitement crédible au-dessus d'un binaire déjà faux, et la
    perte aurait eu lieu chez l'appelant, hors de portée de tout test de formatage. Le
    refus est la seule place où l'erreur est encore attribuable.

    `999.995` est le cas qui le montre : en `Decimal` il rend `1 000,00 MAD`, en double il
    vaut 999.99499999999997 et rendrait un centime de moins.
    """
    from plateforme.projection.formats import formater_montant

    with pytest.raises(TypeError):
        formater_montant(1800.00)
    with pytest.raises(TypeError):
        formater_montant(999.995)

    # Le contrôle positif : ce qui traverse réellement le produit doit passer. DRF livre
    # les montants en chaîne (`COERCE_DECIMAL_TO_STRING`), et un entier est exact.
    assert formater_montant(Decimal("1800.00")) == formater_montant("1800.00")
    assert formater_montant(1800) == formater_montant(Decimal("1800"))


def test_app03_le_formateur_n_appuie_sur_aucune_base_de_locale():
    """Une assertion au niveau du **source**, parce que le bug ne serait pas visible en sortie.

    Le groupement des utilitaires de Django est inactif tant qu'un réglage global ne
    l'active pas, et il rend alors le bon caractère **par accident** plutôt que par
    décision : une mise à jour des données de locale de Django le changerait sous nos
    pieds, et la suite resterait verte le jour du changement puisque le test comparerait
    la sortie d'une base de locale à elle-même. Épingler explicitement est la seule forme
    de garantie possible ici, donc l'interdiction porte sur le source (T-03-68).
    """
    from plateforme.projection import formats

    source = Path(formats.__file__).read_text(encoding="utf-8")
    for interdit in ("django.utils.formats", "floatformat", "USE_THOUSAND_SEPARATOR"):
        assert interdit not in source, (
            f"`{interdit}` apparaît dans plateforme/projection/formats.py. Le format MAD "
            "est épinglé à la main (CLAUDE.md #14) : déléguer à une base de locale rend "
            "le séparateur dépendant d'une donnée qui n'est pas dans ce dépôt."
        )

    assert "ROUND_HALF_UP" in source, (
        "L'arrondi n'est pas nommé. `round()` et la valeur par défaut de `quantize` "
        "arrondissent au pair, donc `999.995` rendrait un centime de moins une fois sur "
        "deux — et la fixture exige `1 000,00 MAD`."
    )


def test_app03_la_date_courte_est_au_format_jj_mm_aaaa():
    """APP-03 — `03/04/2026` et `04/03/2026` sont tous deux plausibles, et c'est le problème.

    Une date mal ordonnée ne ressemble pas à une erreur : elle ressemble à une autre date.
    Sur une échéance de chèque ou une date de facture, elle se propage sans jamais
    déclencher d'alerte. Rouge, ce test dirait que le format court a glissé vers
    `MM/DD/YYYY` — ce que fait le défaut de Django dès que le locale n'est pas celui qu'on
    croit.

    Il vérifie aussi la conversion depuis UTC : `TIME_ZONE = "UTC"` reste tel quel, parce
    que c'est porteur pour PgBouncer, donc la conversion vers UTC+1 se fait à l'affichage
    et un instant tardif tombe la veille si on l'oublie. Le cas de la fixture est choisi
    pour cela : 09:14 UTC est 10:14 à Casablanca.
    """
    from plateforme.projection.formats import formater_date_courte, formater_date_heure

    cas = _fixture()["cas_dates"]
    assert cas, "La fixture ne porte aucun cas de date."

    for horodatage, date_attendue, date_heure_attendue in cas:
        assert _points_de_code(formater_date_courte(horodatage)) == _points_de_code(
            date_attendue
        )
        assert _points_de_code(formater_date_heure(horodatage)) == _points_de_code(
            date_heure_attendue
        )


def test_app03_le_fuseau_est_converti_dans_le_formateur_pas_dans_les_reglages():
    """Le réglage de fuseau reste `UTC`, et l'affichage bascule quand même (T-03-72).

    Deux affirmations en une, parce qu'elles ne sont vraies qu'ensemble. Basculer le
    réglage sur Casablanca ferait émettre à Django un `SET TIMEZONE` au connect, qui
    resterait collé à la connexion serveur rendue au pool de PgBouncer en mode
    transaction (menace T-02-02) — donc le réglage ne bouge pas. Mais s'il ne bouge pas et
    que personne ne convertit, une vente de 23h30 heure locale s'affiche la veille.

    Un instant de fin de journée est donc choisi exprès : 23:30 UTC est déjà le lendemain
    à Casablanca.
    """
    from django.conf import settings

    from plateforme.projection.formats import FUSEAU_AFFICHAGE, formater_date_courte

    assert settings.TIME_ZONE == "UTC"
    assert FUSEAU_AFFICHAGE == "Africa/Casablanca"
    assert formater_date_courte("2026-09-14T23:30:00Z") == "15/09/2026"


# --------------------------------------------------------------------------------------
# Tâche 2 — le français de l'API et l'invariant monétaire de bout en bout
# --------------------------------------------------------------------------------------
@pytest.mark.pending
def test_app01_les_erreurs_de_lapi_sont_en_francais():
    """APP-01 — l'interface est française jusque dans ses messages d'échec.

    Les chaînes qu'un opticien voit le plus souvent au moment où il a le plus besoin de les
    comprendre sont les messages de validation, et ce sont celles qu'on ne traduit pas :
    elles viennent de DRF, pas de nos gabarits. Rouge, ce test dirait que `LANGUAGE_CODE`
    ou le catalogue `fr` de DRF n'est pas en place, donc qu'un formulaire refusé répond
    *« This field is required. »* dans un produit par ailleurs entièrement français.

    Il assertent sur une réponse d'API réelle, pas sur le réglage : `LANGUAGE_CODE = "fr-fr"`
    peut être posé et neutralisé par un `LocaleMiddleware` qui négocie l'`Accept-Language`
    du navigateur — c'est-à-dire par le poste de l'utilisateur, ce qui n'est pas une
    décision produit.
    """
    pytest.fail("non implémenté : plan 03-10")


@pytest.mark.pending
def test_app03_un_montant_traverse_le_json_en_chaine_pas_en_flottant():
    """APP-03 / CLAUDE.md #7 — `COERCE_DECIMAL_TO_STRING` est une garantie, pas un réglage.

    Un `DecimalField` sérialisé en nombre JSON devient un double IEEE-754 dans le
    navigateur, et `0.1 + 0.2` y vaut `0.30000000000000004`. Sur une facture soumise à
    l'art. 145 CGI, c'est un centime d'écart qui apparaît des mois plus tard dans une
    réconciliation, sans trace de sa cause.

    Rouge, ce test dirait que le réglage a été désactivé — souvent pour faire taire un
    composant de graphique qui voulait des nombres. Le composant a tort.
    """
    pytest.fail("non implémenté : plan 03-10")


@pytest.mark.pending
def test_app03_aucun_montant_n_est_un_flottant_dans_une_reponse():
    """APP-03 / CLAUDE.md #7 — la version balayante du test ci-dessus, et la seule durable.

    Le test ciblé vérifie un point de terminaison ; celui-ci parcourt les réponses et
    échoue sur **tout** nombre JSON à la place d'un montant, y compris ceux qu'un
    `annotate()` de phase 8 aura ajoutés sans passer par un `DecimalField`. C'est là que se
    trouve la vraie dérive : personne ne désactive `COERCE_DECIMAL_TO_STRING`, quelqu'un
    ajoute une somme calculée.

    Rouge, il nomme le chemin et la clé fautifs, ce qui est ce qui rend un test balayant
    utilisable plutôt que décourageant.
    """
    pytest.fail("non implémenté : plan 03-10")
