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
import re
from decimal import Decimal
from pathlib import Path

import pytest

from tests.ressources_fixture import (  # noqa: F401 — fixtures pytest, importées pour être disponibles
    PRIX_VENTE,
    VueRessourceFixture,
    acces_avec_le_droit,
    registre_de_la_fixture,
    ressource,
    table_ressource_fixture,
)

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
CONNEXION = "/api/auth/connexion/"


def _corps_json(reponse):
    """Le JSON **tel qu'il part sur le fil**, pas `response.data`.

    La différence est tout le sujet de ces deux tests : `response.data` porte encore les
    objets Python que le sérialiseur a produits, donc un `Decimal` y ressemble à un
    montant juste. Ce qui décide du type côté navigateur est le rendu JSON, et c'est lui
    qu'il faut lire.
    """
    if not getattr(reponse, "is_rendered", True):
        reponse.render()
    return json.loads(reponse.content.decode("utf-8"))


def test_app01_les_erreurs_de_lapi_sont_en_francais(affaire_reelle):
    """APP-01 — l'interface est française jusque dans ses messages d'échec.

    Les chaînes qu'un opticien voit le plus souvent au moment où il a le plus besoin de
    les comprendre sont les messages de validation, et ce sont celles qu'on ne traduit
    pas : elles viennent de DRF, pas de nos gabarits. Rouge, ce test dirait que
    `LANGUAGE_CODE` ou le catalogue `fr` de DRF n'est pas en place, donc qu'un formulaire
    refusé répond *« This field is required. »* dans un produit par ailleurs entièrement
    français.

    Il assertent sur une réponse d'API réelle, pas sur le réglage : `LANGUAGE_CODE =
    "fr-fr"` peut être posé et neutralisé par un middleware de négociation de langue, qui
    lit l'`Accept-Language` du navigateur — c'est-à-dire le poste de l'utilisateur, ce qui
    n'est pas une décision produit.
    """
    from rest_framework.test import APIClient

    reponse = APIClient().post(CONNEXION, {}, format="json")

    assert reponse.status_code == 400, reponse.data
    corps = _corps_json(reponse)
    messages = [str(m) for liste in corps.values() for m in liste]
    assert messages, f"Aucun message de validation dans {corps!r}."
    assert all("Ce champ est obligatoire." == m for m in messages), (
        f"Les messages de validation ne sont pas en français : {messages!r}. Le catalogue "
        "`fr` de DRF est livré avec la bibliothèque ; ce test vérifie NOTRE configuration, "
        "pas le fonctionnement de Django."
    )


def test_app01_la_langue_ne_depend_pas_dun_entete_fourni_par_le_client(affaire_reelle):
    """T-03-71 — la langue est une décision produit, pas une préférence de navigateur.

    Le produit est monolingue et le restera (`03-RESEARCH.md` §8, i18n délibérément
    reportée à *jamais*, sauf demande d'une interface arabe). Installer un middleware de
    négociation de langue ferait donc trois choses, toutes indésirables : il rendrait la
    langue de l'API dépendante d'un en-tête que l'appelant contrôle — dans un produit dont
    tout l'argument de la phase 2 est que rien de significatif ne vient du client — il
    ajouterait `Vary: Accept-Language` à **chaque** réponse, ce qui coûte en cache pour
    une dimension inutilisée, et il ferait basculer les messages de DRF en anglais pour
    l'opticien dont le poste est en anglais, ce qui est précisément le poste le plus
    susceptible d'exister dans une boutique.

    Deux assertions, et il faut les deux. L'une prouve le comportement : un en-tête
    anglais n'obtient pas d'anglais. L'autre prouve **pourquoi**, et resterait rouge le
    jour où quelqu'un ajouterait le middleware sans rien casser d'autre, parce que le
    catalogue anglais est la source par défaut et qu'une chaîne non traduite passerait
    inaperçue.
    """
    from django.conf import settings
    from rest_framework.test import APIClient

    assert not any("LocaleMiddleware" in couche for couche in settings.MIDDLEWARE), (
        "Un middleware de négociation de langue est installé. La langue du produit ne se "
        "négocie pas : voir la docstring de ce test."
    )
    assert "Vary" not in APIClient().post(CONNEXION, {}, format="json").headers.get(
        "Vary", "Accept-Language"
    ).replace("Accept-Language", "Vary"), "Vary: Accept-Language sur une réponse d'API."

    reponse = APIClient().post(
        CONNEXION, {}, format="json", headers={"accept-language": "en-US,en;q=0.9"}
    )
    messages = [str(m) for liste in _corps_json(reponse).values() for m in liste]
    assert all(m == "Ce champ est obligatoire." for m in messages), (
        f"Un en-tête Accept-Language anglais a changé la langue de l'API : {messages!r}."
    )


def test_app03_le_reglage_de_localisation_retire_de_django_n_est_pose_nulle_part():
    """Un réglage qui ne fait rien est pire qu'un réglage absent : il rassure.

    Le réglage de localisation des nombres a été **retiré** de Django ; l'écrire
    aujourd'hui, dans un sens ou dans l'autre, n'a littéralement aucun effet. Le risque
    n'est donc pas qu'il casse quelque chose, c'est qu'une revue le lise et en conclue que
    le formatage des montants est géré — alors que ce qui le gère est
    `plateforme/projection/formats.py` et rien d'autre (`03-RESEARCH.md` correction 5).
    """
    from pathlib import Path as _Path

    reglages = sorted((_Path("config") / "settings").glob("*.py"))
    assert reglages, "Aucun module de réglages trouvé : le test ne vérifierait rien."
    for module in reglages:
        assert "USE_L10N" not in module.read_text(encoding="utf-8"), (
            f"{module} pose un réglage retiré de Django. Voir la docstring de ce test."
        )


def test_app03_un_montant_traverse_le_json_en_chaine_pas_en_flottant(
    ressource, deux_magasins
):
    """APP-03 / CLAUDE.md #7 — `COERCE_DECIMAL_TO_STRING` est une garantie, pas un réglage.

    Un `DecimalField` sérialisé en nombre JSON devient un double IEEE-754 dans le
    navigateur, et `0.1 + 0.2` y vaut `0.30000000000000004`. Sur une facture soumise à
    l'art. 145 CGI, c'est un centime d'écart qui apparaît des mois plus tard dans une
    réconciliation, sans trace de sa cause.

    Rouge, ce test dirait que le réglage a été désactivé — souvent pour faire taire un
    composant de graphique qui voulait des nombres. Le composant a tort.

    Les deux assertions sont voulues : le type observé sur le fil peut être juste par
    accident (une valeur ronde, un sérialiseur écrit à la main), et le réglage seul ne
    prouve pas qu'un sérialiseur ne le contourne pas. Ensemble, elles tiennent.
    """
    from django.conf import settings

    assert settings.REST_FRAMEWORK["COERCE_DECIMAL_TO_STRING"] is True

    proprietaire, _ = acces_avec_le_droit(deux_magasins)
    corps = _corps_json(_appeler_ressource(proprietaire, ressource))

    assert isinstance(corps["prix_vente"], str), (
        f"`prix_vente` traverse le JSON en {type(corps['prix_vente']).__name__} et non en "
        "chaîne : la valeur est déjà un double dans le navigateur."
    )
    assert corps["prix_vente"] == f"{PRIX_VENTE:.2f}"


def test_app03_aucun_montant_n_est_un_flottant_dans_une_reponse(ressource, deux_magasins):
    """APP-03 / CLAUDE.md #7 — la version balayante du test ci-dessus, et la seule durable.

    Le test ciblé vérifie une clé ; celui-ci parcourt la charge utile entière et échoue
    sur **tout** nombre JSON non entier, y compris ceux qu'un `annotate()` de phase 8 ou
    un `SerializerMethodField` auront ajoutés sans passer par un `DecimalField`. C'est là
    que se trouve la vraie dérive : personne ne désactive `COERCE_DECIMAL_TO_STRING`,
    quelqu'un ajoute une somme calculée.

    Rouge, il nomme le chemin et la clé fautifs, ce qui est ce qui rend un test balayant
    utilisable plutôt que décourageant.

    **Le contrôle positif est la moitié du test.** Une charge utile sans aucun montant
    passe « aucun flottant » sans rien prouver, et c'est l'état par défaut d'une phase 3
    qui n'a pas encore de facturation. La ressource de test, elle, porte deux champs
    monétaires : le balayage exige donc d'en avoir vu au moins un, en chaîne.
    """
    proprietaire, _ = acces_avec_le_droit(deux_magasins)
    charge = _corps_json(_appeler_ressource(proprietaire, ressource))

    _refuser_les_flottants({"ressource-fixture": charge})

    montants = _montants_en_chaine(charge, "ressource-fixture")
    assert montants, (
        "Le balayage n'a rencontré aucun montant : il est vert et vide. La ressource de "
        "test porte deux champs monétaires ; si elle n'en sert plus, ce contrôle positif "
        "doit être reporté sur une charge utile qui en porte."
    )


def test_app03_aucun_flottant_dans_les_charges_utiles_servies_par_lapi(affaire_reelle):
    """Le même balayage, sur les points de terminaison réellement montés.

    Il est **séparé** du précédent pour une raison mécanique et non esthétique : les
    fixtures de locataire statique lient le contexte pour toute la durée du test, et
    `TenantMiddleware` refuse — correctement — de servir une requête dont le thread porte
    déjà un contexte (CLAUDE.md #8). Une vraie requête HTTP et un locataire `tenant_a`
    lié à la main ne peuvent donc pas coexister dans un test, et essayer produirait un
    `TenantContextLeak` qui n'a rien à voir avec l'argent.

    **Il est vert et sans montant aujourd'hui, et c'est assumé.** La phase 3 ne sert
    aucune monnaie : l'amorçage, le catalogue de droits et la liste des comptes n'en
    portent pas. Son contrôle positif est le test précédent ; celui-ci est l'assertion qui
    commencera à mordre en phase 6, sur les mêmes quatre points de terminaison plus ceux
    qu'elle ajoutera. Le garder vide maintenant coûte une seconde et évite d'avoir à s'en
    souvenir plus tard.
    """
    from rest_framework.test import APIClient

    from tests.factories import MOT_DE_PASSE_DE_TEST, ProprietaireFactory

    api = APIClient()
    proprietaire = ProprietaireFactory(client=affaire_reelle.client)
    connexion = api.post(
        CONNEXION,
        {"email": proprietaire.email, "mot_de_passe": MOT_DE_PASSE_DE_TEST},
        format="json",
    )
    assert connexion.status_code == 200, connexion.data

    charges = {
        CONNEXION: _corps_json(connexion),
        "/api/auth/moi/": _corps_json(api.get("/api/auth/moi/")),
        "/api/comptes/": _corps_json(api.get("/api/comptes/")),
        "/api/comptes/catalogue/": _corps_json(api.get("/api/comptes/catalogue/")),
    }
    assert all(charge for charge in charges.values()), (
        f"Une charge utile est vide, donc balayée pour rien : "
        f"{[nom for nom, charge in charges.items() if not charge]}"
    )
    _refuser_les_flottants(charges)


def _refuser_les_flottants(charges):
    """L'assertion partagée par les deux balayages, avec son message."""
    flottants = [t for nom, charge in charges.items() for t in _flottants(charge, nom)]
    assert not flottants, (
        "Un nombre JSON non entier est servi là où un montant est attendu : "
        + ", ".join(f"{chemin} = {valeur!r}" for chemin, valeur in flottants)
        + ". L'argent traverse le JSON en chaîne (CLAUDE.md #7) ; un `annotate()` ou un "
        "`SerializerMethodField` qui rend un float contourne `COERCE_DECIMAL_TO_STRING` "
        "sans jamais le désactiver."
    )


def _appeler_ressource(utilisateur, instance):
    """Une vraie requête sur la ressource de test : principal -> middleware -> vue -> JSON.

    Même idiome que `tests/test_projection.py` : `force_authenticate` est obligatoire
    parce que le setter `Request.user` de DRF réécrit `_request.user`, donc une vue sans
    classe d'authentification y poserait `AnonymousUser` **après** le middleware et
    l'accès paresseux se résoudrait en `Acces.ANONYME` — le test verrait une charge utile
    projetée, pour une raison qui n'a rien à voir avec l'argent.
    """
    from rest_framework.test import APIRequestFactory, force_authenticate

    from plateforme.comptes.middleware import AccesMiddleware

    vue = VueRessourceFixture.as_view({"get": "retrieve"})
    requete = APIRequestFactory().get(f"/api/ressources-fixture/{instance.pk}/")
    requete.user = utilisateur
    force_authenticate(requete, user=utilisateur)
    reponse = AccesMiddleware(lambda recue: vue(recue, pk=instance.pk))(requete)
    reponse.render()
    return reponse


def _flottants(valeur, chemin):
    """Tout `float` de la charge utile, avec le chemin qui y mène.

    `json.loads` rend un `float` pour tout nombre JSON non entier, donc cette marche
    attrape exactement ce qu'il faut : `"1800.00"` reste une chaîne et passe, `1800.0`
    est un double et échoue. Les entiers sont laissés tranquilles — un identifiant, un
    compte de lignes ou une quantité n'est pas un montant, et les refuser rendrait ce
    test insupportable sans rien protéger.
    """
    if isinstance(valeur, float):
        return [(chemin, valeur)]
    if isinstance(valeur, dict):
        return [t for cle, v in valeur.items() for t in _flottants(v, f"{chemin}.{cle}")]
    if isinstance(valeur, list):
        return [t for i, v in enumerate(valeur) for t in _flottants(v, f"{chemin}[{i}]")]
    return []


def _montants_en_chaine(valeur, chemin):
    """Les chaînes qui ressemblent à un montant décimal — le contrôle positif du balayage."""
    if isinstance(valeur, str):
        return [(chemin, valeur)] if re.fullmatch(r"-?\d+\.\d{2}", valeur) else []
    if isinstance(valeur, dict):
        return [
            t for cle, v in valeur.items() for t in _montants_en_chaine(v, f"{chemin}.{cle}")
        ]
    if isinstance(valeur, list):
        return [
            t for i, v in enumerate(valeur) for t in _montants_en_chaine(v, f"{chemin}[{i}]")
        ]
    return []
