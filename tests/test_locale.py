"""APP-01 et APP-03 — le français côté serveur, et le format marocain de l'argent et des dates.

**Ces tests ne sont pas encore implémentés.** Marqueur `pending`, corps volontairement
rouge ; le plan **03-10** les implémente et retire le marqueur.

Le fait qui rend ce fichier nécessaire est vérifié, pas supposé : « conventions
françaises » a **trois** réponses différentes et elles ne sont pas d'accord entre elles.
Le locale `fr` de Django groupe les milliers avec U+00A0, l'ICU `fr-FR` des navigateurs et
de Node utilise U+202F, et l'ICU **`fr-MA` utilise un point** — soit `1.800,00 MAD` à
l'écran contre `1 800,00 MAD` sur la facture, même montant, même produit, même journée
(`03-RESEARCH.md` §7). S'appuyer sur l'une ou l'autre base de locales **est** le bug.

D'où CLAUDE.md #14 : le format est épinglé explicitement, des deux côtés, depuis un seul
fichier — `tests/fixtures/formats_mad.json`, écrit au plan 03-01 et pour l'instant lu par
personne. Ces tests en sont le premier consommateur ; `format.test.ts` (plan 03-11) en est
le second, et c'est le fait qu'ils lisent **le même fichier** qui empêche le serveur et le
navigateur de diverger.

Deux tests portent sur le JSON plutôt que sur l'affichage, et c'est CLAUDE.md #7 : un
montant qui traverse la frontière en flottant a déjà perdu sa précision avant qu'un
formateur ne le voie. `assert total == 1800.0` passe pendant que l'argent est faux
(`.planning/TESTING.md` §4).

**Aucun import du code en construction au niveau du module.**
"""

from __future__ import annotations

import pytest


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
    par une espace ordinaire sans que rien ne le signale.
    """
    pytest.fail("non implémenté : plan 03-10")


@pytest.mark.pending
def test_app03_la_date_courte_est_au_format_jj_mm_aaaa():
    """APP-03 — `03/04/2026` et `04/03/2026` sont tous deux plausibles, et c'est le problème.

    Une date mal ordonnée ne ressemble pas à une erreur : elle ressemble à une autre date.
    Sur une échéance de chèque ou une date de facture, elle se propage sans jamais
    déclencher d'alerte. Rouge, ce test dirait que le format court a glissé vers
    `MM/DD/YYYY` — ce que fait le défaut de Django dès que le locale n'est pas celui qu'on
    croit.

    Il vérifie aussi la conversion depuis UTC : `TIME_ZONE = "UTC"` reste tel quel, parce
    que c'est porteur pour PgBouncer, donc la conversion vers UTC+1 se fait à l'affichage
    et un instant tardif tombe la veille si on l'oublie.
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
