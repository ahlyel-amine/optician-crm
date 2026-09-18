"""CLIENT-09 — la photo de l'ordonnance : où elle vit, et qui peut la lire.

Ce fichier garde une frontière d'un genre que ce dépôt n'avait pas encore. L'isolation
des **lignes** entre opticiens repose sur `REVOKE CONNECT` et une base séparée — une
frontière *sous* l'application, que PostgreSQL tient même si Python se trompe.
L'isolation des **fichiers** repose sur Python, et sur une seule classe. **Il n'y a
aucun `REVOKE` en dessous.**

Le contrôle compensatoire est donc le même que pour la projection : un test qui lie le
locataire B, lui présente un chemin appartenant au locataire A, et vérifie le refus.
`test_client09_un_chemin_d_un_autre_client_est_refuse` n'est pas un test parmi d'autres —
il **est** la garantie, et ses trois moitiés le sont chacune.

**Ce que la traversée de chemin classique n'est pas.**
`django/core/files/utils.py::validate_file_name(nom, allow_relative_path=True)` lève déjà
sur un chemin absolu ou sur tout composant `..`. Le risque résiduel de ce plan n'est donc
pas `../../` : c'est un chemin **relatif parfaitement valide appartenant à un autre
opticien**. Seule la redérivation du préfixe depuis le contexte vivant le ferme, et c'est
pour cela que le test présente le vrai nom stocké de A avant de présenter une traversée
fabriquée.

**Aucun test de ce fichier n'écrit dans l'arbre du dépôt.** `config/settings/test.py`
pointe la racine de stockage sur un répertoire temporaire de session : une photo
d'ordonnance commise serait une fuite de donnée de santé dans l'historique git, et
l'historique git n'est pas révocable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

#: La route plate, écrite une fois. Un test qui recopie une URL reste vert le jour où la
#: route déménage : il vérifie alors une 404 bien formée.
PHOTO = "/api/ordonnances/{pk}/photo/"

#: Les premiers octets d'un JPEG — `SOI` puis le marqueur `APP0`/JFIF. Ce qui compte
#: pour un point d'entrée de téléversement n'est pas que l'image soit décodable, c'est
#: que les octets **correspondent au type déclaré**.
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x2a" * 64

#: Un exécutable Windows, déclaré `image/jpeg` et nommé `.jpg`. C'est la forme que prend
#: un téléversement hostile : l'extension et le type MIME sont tous deux choisis par
#: l'appelant, donc ni l'un ni l'autre n'est une preuve.
PAS_UNE_IMAGE = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 64

#: Le nom de fichier tel qu'un comptoir en produit réellement. **Il porte le nom du
#: patient**, et c'est la raison d'être de la moitié « le message d'erreur n'échoie pas
#: le nom » et de l'élargissement de `SENSITIVE_KEY`.
NOM_QUI_PORTE_LE_PATIENT = "ordonnance_benali_ahmed.jpg"

#: 10 Mo, en octets. Recopié ici **exprès** plutôt qu'importé du réglage : un test qui
#: lit la limite qu'il vérifie est vert quelle que soit la limite, y compris nulle.
DIX_MEGAOCTETS = 10 * 1024 * 1024


# ======================================================================================
# Fabriques locales
# ======================================================================================
def _fichier(contenu=JPEG, nom=NOM_QUI_PORTE_LE_PATIENT, type_declare="image/jpeg"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(nom, contenu, content_type=type_declare)


def _ordonnance():
    from tests.factories import OrdonnanceFactory

    return OrdonnanceFactory()


def _attacher(ordonnance, fichier=None):
    from domaine.ordonnances.services import attacher_photo

    return attacher_photo(
        ordonnance, fichier if fichier is not None else _fichier(), par="comptoir@optique.test"
    )


def _nom_stocke(ordonnance):
    """Le nom **relu depuis la base**, jamais celui que l'instance porte en mémoire.

    La distinction n'est pas de la pédanterie : c'est la ligne persistée qu'un autre
    locataire pourrait un jour présenter, et c'est donc elle que ces tests manipulent.
    """
    from domaine.ordonnances.models import Ordonnance

    return Ordonnance.objects.get(pk=ordonnance.pk).photo.name


def _toutes_les_colonnes(instance) -> dict:
    """Toutes les colonnes concrètes, **y compris les non modifiables**.

    Et non `model_to_dict`, qui **saute silencieusement** tout champ `editable=False` —
    donc précisément `photo`, la colonne que ce fichier existe pour surveiller. Mesuré :
    la première version de la comparaison champ par champ ne voyait pas l'attache du
    tout, et seule l'assertion de contrôle « au moins une colonne de photo a bougé » l'a
    révélé. Un comparateur aveugle à la moitié de la ligne est vert pour toujours.
    """
    return {
        champ.name: champ.value_from_object(instance)
        for champ in instance._meta.concrete_fields
    }


def _racine_du_locataire(alias):
    """La racine attendue, **résolue**.

    `.resolve()` et non le chemin brut : sur macOS `/var` est un lien vers
    `/private/var`, donc `tempfile.mkdtemp()` rend un chemin que le stockage résout
    différemment. Sans cette ligne, l'assertion échoue sur un détail de plateforme au
    lieu d'échouer sur la garantie — ce qui est la pire façon de la faire rougir.
    """
    from django.conf import settings

    return (Path(settings.ORDONNANCE_MEDIA_ROOT) / alias).resolve()


def _proprietaire():
    from plateforme.comptes.acces import acces_pour
    from tests.factories import ProprietaireFactory

    compte = ProprietaireFactory()
    return compte, acces_pour(compte)


def _gerant_avec(magasins, codes):
    """Un gérant ayant accès aux `magasins` et y détenant `codes`, dans **tous**.

    `Acces.peut(code)` sans argument magasin est une conjonction (plan 03-05) : un droit
    accordé dans un seul des deux magasins n'autorise rien.
    """
    from plateforme.comptes.acces import acces_pour
    from tests.factories import AccesMagasinFactory, DroitAccordeFactory, GerantFactory

    compte = GerantFactory()
    for magasin in magasins:
        AccesMagasinFactory(utilisateur=compte, magasin_code=magasin.code)
        for code in codes:
            DroitAccordeFactory(utilisateur=compte, magasin_code=magasin.code, code=code)
    return compte, acces_pour(compte)


def _appeler_photo(utilisateur, methode, pk, fichier=None):
    """Une vraie requête : principal -> `AccesMiddleware` -> la vue -> la réponse rendue.

    La réponse d'une lecture réussie est un `FileResponse`, qui n'a pas de `.render()` et
    dont le corps est un itérable. Les deux formes sont donc traitées ici, une fois, pour
    qu'aucun test n'ait à savoir laquelle il vient d'obtenir.
    """
    from rest_framework.test import APIRequestFactory, force_authenticate

    from domaine.ordonnances.vues import VuePhotoOrdonnance
    from plateforme.comptes.middleware import AccesMiddleware

    vue = VuePhotoOrdonnance.as_view()
    fabrique = APIRequestFactory()
    chemin = PHOTO.format(pk=pk)
    if fichier is not None:
        requete = getattr(fabrique, methode)(
            chemin, {"fichier": fichier}, format="multipart"
        )
    else:
        requete = getattr(fabrique, methode)(chemin)
    requete.user = utilisateur
    force_authenticate(requete, user=utilisateur)
    reponse = AccesMiddleware(lambda recue: vue(recue, pk=pk))(requete)
    if hasattr(reponse, "render"):
        reponse.render()
    return reponse


def _corps(reponse) -> bytes:
    if getattr(reponse, "streaming", False):
        return b"".join(reponse.streaming_content)
    return reponse.content


# ======================================================================================
# 1 — le rangement : le préfixe est sur le disque, jamais dans la ligne
# ======================================================================================
def test_client09_la_photo_est_rangee_sous_le_client_lie(db_all):
    """Deux moitiés, et la seconde est celle qui tient la sécurité.

    La première — le fichier atterrit bien sous le préfixe du locataire lié — est
    évidente. La seconde — **le nom stocké en base ne porte PAS ce préfixe** — l'est
    moins, et c'est elle qui interdit la classe de bogue entière : un nom qui porterait
    `tenant_a/...` serait un chemin venu de la **ligne**, donc un chemin qu'un autre
    locataire pourrait présenter. Le préfixe doit venir du contexte vivant, et de nulle
    part ailleurs.

    Troisième assertion, du même coup : le nom stocké est **fabriqué**. Un nom de fichier
    téléversé porte couramment le nom du patient, et il n'a rien à faire sur un disque
    ni dans une colonne.
    """
    from plateforme.tenancy.context import tenant_context

    with tenant_context("tenant_a") as alias:
        ordonnance = _ordonnance()
        _attacher(ordonnance)
        nom = _nom_stocke(ordonnance)

        assert nom, "Aucun nom n'a été persisté : la photo n'est attachée à rien."
        assert not Path(nom).is_absolute(), (
            f"Le nom stocké {nom!r} est absolu. Un chemin absolu en base est un chemin "
            "que le stockage n'a plus qu'à ouvrir, donc une frontière que la ligne "
            "décide."
        )
        assert alias not in nom, (
            f"Le nom stocké {nom!r} porte le préfixe du locataire. Il vient donc de la "
            "ligne et non du contexte — c'est exactement le chemin qu'un autre opticien "
            "pourrait présenter."
        )
        assert "benali" not in nom.lower(), (
            f"Le nom stocké {nom!r} dérive du nom du fichier envoyé, qui porte le nom du "
            "patient. Le nom doit être fabriqué."
        )

        from domaine.ordonnances.stockage import stockage_des_photos

        chemin = Path(stockage_des_photos().path(nom))
        assert chemin.is_file(), f"Aucun fichier sur le disque à {chemin}."
        assert chemin.is_relative_to(_racine_du_locataire(alias)), (
            f"Le fichier est à {chemin}, hors de {_racine_du_locataire(alias)}. Le "
            "préfixe du locataire n'est pas appliqué à l'écriture."
        )


# ======================================================================================
# 2 — LE test : le chemin d'un autre opticien ne se résout pas
# ======================================================================================
def test_client09_un_chemin_d_un_autre_client_est_refuse(db_all):
    """**La garantie entière de ce plan, et ses trois moitiés.**

    1. Sous le locataire **B**, le nom stocké par **A** est refusé — jamais des octets.
    2. Sous **A**, ce même nom rend bien les octets. Sans cette moitié, une
       implémentation qui refuse tout serait verte, et ce test serait le plus rassurant
       et le plus vide de la suite.
    3. **Hors de tout contexte**, l'accès est refusé et non servi depuis une racine par
       défaut. Fail-closed comme le routeur : `current_alias()` lève, et cette exception
       doit traverser le stockage sans être rattrapée en « fichier absent ».

    Une quatrième assertion, distincte : une traversée **fabriquée** (`../tenant_a/...`)
    est refusée elle aussi. Elle ne prouve pas la même chose — celle-là, le cadre la
    ferme déjà dans `validate_file_name`. Elle est là pour que le refus de la moitié 1
    ne puisse pas être confondu avec elle : la moitié 1 présente un chemin **relatif et
    parfaitement licite**, et c'est la redérivation du préfixe, elle seule, qui le
    refuse.
    """
    from django.core.exceptions import SuspiciousFileOperation

    from domaine.ordonnances.stockage import stockage_des_photos
    from plateforme.tenancy.context import NoTenantBound, tenant_context

    stockage = stockage_des_photos()

    with tenant_context("tenant_a"):
        ordonnance = _ordonnance()
        _attacher(ordonnance)
        nom = _nom_stocke(ordonnance)

        # Moitié 2 — la moitié jumelle, sans laquelle le test est vide.
        with stockage.open(nom) as ouvert:
            assert ouvert.read() == JPEG, (
                "Sous son propre locataire, le nom stocké ne rend pas les octets écrits. "
                "Le test d'isolation qui suit serait alors vert pour la mauvaise raison."
            )

    with tenant_context("tenant_b"):
        with pytest.raises((FileNotFoundError, SuspiciousFileOperation)) as refus:
            stockage.open(nom).read()
        assert refus.value is not None

        assert not stockage.exists(nom), (
            f"Le locataire B voit exister {nom!r}, qui appartient au locataire A. Le "
            "préfixe n'est pas redérivé : il vient de la ligne."
        )

        with pytest.raises(SuspiciousFileOperation):
            stockage.open(f"../tenant_a/{nom}")

    # Moitié 3 — hors de tout contexte. Ni octets, ni racine par défaut.
    with pytest.raises(NoTenantBound):
        stockage.open(nom)


# ======================================================================================
# 3 — l'image est gouvernée par le même droit que les valeurs
# ======================================================================================
def test_client09_l_image_exige_le_droit_ordonnance_voir(db_all, deux_magasins):
    """403 sans `ordonnance.voir`, 200 avec — et **aucun oracle d'énumération**.

    La seconde moitié est la moins évidente et la plus facile à casser : un refus qui
    répondrait 404 sur un identifiant inexistant et 403 sur un identifiant existant
    dirait à un appelant sans droit **quelles ordonnances existent**. Le droit doit donc
    se résoudre avant la ligne, et les deux réponses doivent être indiscernables —
    statut **et** corps.
    """
    from plateforme.comptes.permissions_catalogue import Permission

    ordonnance = _ordonnance()
    _attacher(ordonnance)

    aveugle, _ = _gerant_avec(deux_magasins, [Permission.CLIENT_VOIR.value])
    voyant, _ = _gerant_avec(
        deux_magasins, [Permission.CLIENT_VOIR.value, Permission.ORDONNANCE_VOIR.value]
    )

    refus = _appeler_photo(aveugle, "get", ordonnance.pk)
    assert refus.status_code == 403, (
        f"Un gérant sans `ordonnance.voir` obtient {refus.status_code} sur l'image. "
        "L'image est la même donnée de santé que les valeurs structurées ; la servir "
        "derrière un droit plus faible ferait de la couche de projection un théâtre."
    )

    inexistante = _appeler_photo(aveugle, "get", 10_000_000)
    assert inexistante.status_code == refus.status_code, (
        f"Identifiant inexistant : {inexistante.status_code} ; identifiant existant hors "
        f"de portée : {refus.status_code}. L'écart est un oracle d'énumération — il dit "
        "à qui n'a aucun droit quelles ordonnances existent."
    )
    assert _corps(inexistante) == _corps(refus), (
        "Les deux refus ont des corps différents. Le statut ne suffit pas : le message "
        "est lisible lui aussi."
    )

    servie = _appeler_photo(voyant, "get", ordonnance.pk)
    assert servie.status_code == 200, (
        f"Un gérant détenant `ordonnance.voir` obtient {servie.status_code}."
    )
    assert _corps(servie) == JPEG, "Les octets servis ne sont pas ceux qui ont été écrits."


# ======================================================================================
# 4 — une photo s'attache une fois
# ======================================================================================
def test_client09_une_photo_s_attache_une_fois_et_ne_se_remplace_jamais(
    db_all, deux_magasins
):
    """§28-Q5 et §22.3 — `null -> posé` est la **seule** mutation permise sur la ligne.

    Quatre moitiés, et la dernière est celle qui compte. Une ordonnance est immuable
    (CLIENT-06) ; la photo est l'unique exception, parce que le papier arrive souvent le
    lendemain. Un chemin d'attache qui toucherait **autre chose** que les quatre colonnes
    de la photo serait la brèche par laquelle un `UPDATE` général reviendrait — et il
    reviendrait sur un historique clinique.

    La comparaison est donc champ par champ, avant et après, et non « la sphère n'a pas
    bougé ».
    """
    from domaine.ordonnances.models import Ordonnance
    from plateforme.comptes.permissions_catalogue import Permission

    #: Les colonnes que l'attache a le droit de toucher. `photo_par` est la cinquième,
    #: et elle est là pour la même raison que `created_par` : la provenance d'une pièce
    #: justificative de santé est ce qui la rend discutable au comptoir dix ans plus
    #: tard. **Recopiée ici plutôt qu'importée de `services.py`** — un test qui importe
    #: la liste qu'il vérifie est vert quelle que soit cette liste, y compris quand
    #: quelqu'un y ajoute `sphere_od`.
    COLONNES_DE_LA_PHOTO = {
        "photo",
        "photo_type",
        "photo_octets",
        "photo_attachee_le",
        "photo_par",
    }

    ordonnance = _ordonnance()
    avant = _toutes_les_colonnes(Ordonnance.objects.get(pk=ordonnance.pk))

    saisisseur, _ = _gerant_avec(
        deux_magasins,
        [
            Permission.CLIENT_VOIR.value,
            Permission.ORDONNANCE_VOIR.value,
            Permission.ORDONNANCE_SAISIR.value,
        ],
    )

    premiere = _appeler_photo(saisisseur, "post", ordonnance.pk, fichier=_fichier())
    assert premiere.status_code in (200, 201), (
        f"La première attache rend {premiere.status_code} : {_corps(premiere)!r}. Une "
        "version enregistrée sans photo doit pouvoir en recevoir une."
    )

    seconde = _appeler_photo(saisisseur, "post", ordonnance.pk, fichier=_fichier())
    assert seconde.status_code not in (200, 201), (
        "Une seconde attache a réussi. Une photo ne se remplace pas : sur la mauvaise "
        "version, elle se corrige par une nouvelle version, comme tout le reste."
    )
    assert seconde.status_code == 409, (
        f"La seconde attache rend {seconde.status_code} et non 409. Le conflit porte sur "
        "l'état de la ressource, pas sur la forme de la requête."
    )

    retrait = _appeler_photo(saisisseur, "delete", ordonnance.pk)
    assert retrait.status_code == 405, (
        f"DELETE rend {retrait.status_code} et non 405. Un 403 dirait que la route "
        "existe et qu'un droit la garde — donc qu'il suffit d'accorder ce droit pour "
        "effacer une pièce justificative."
    )

    apres = _toutes_les_colonnes(Ordonnance.objects.get(pk=ordonnance.pk))
    bouges = {
        cle for cle in avant if avant[cle] != apres[cle]
    } | (set(apres) - set(avant))
    assert bouges <= COLONNES_DE_LA_PHOTO, (
        f"L'attache a modifié {sorted(bouges - COLONNES_DE_LA_PHOTO)}. `null -> posé` sur "
        "les colonnes de la photo est la seule mutation permise sur une ordonnance "
        "enregistrée."
    )
    assert "photo" in bouges, (
        "Aucune colonne de photo n'a bougé : la comparaison ci-dessus passerait aussi "
        "sur une attache qui n'écrit rien du tout."
    )


# ======================================================================================
# 5 — taille, type déclaré, octets magiques, et le message qui n'échoie rien
# ======================================================================================
def test_client09_un_televersement_est_borne_en_taille_et_en_type(db_all, deux_magasins):
    """Trois refus, et une assertion qui n'est pas évidente.

    Les octets magiques priment sur le type déclaré, parce que l'extension **et** le
    type MIME sont tous deux choisis par l'appelant. Pillow n'est pas ajoutée pour
    autant : `ImageField` prouverait seulement que les octets sont décodables, et poser
    une bibliothèque d'images sur un flux non fiable élargit la surface d'attaque au
    service d'une garantie dont ce plan n'a pas besoin.

    **L'assertion qui n'est pas évidente :** aucun des trois messages ne contient le nom
    du fichier. Un nom de fichier téléversé porte couramment le nom du patient, et une
    chaîne d'erreur est la seule chaîne du produit qui atteint Sentry de façon fiable.
    """
    from plateforme.comptes.permissions_catalogue import Permission

    saisisseur, _ = _gerant_avec(
        deux_magasins,
        [
            Permission.CLIENT_VOIR.value,
            Permission.ORDONNANCE_VOIR.value,
            Permission.ORDONNANCE_SAISIR.value,
        ],
    )

    cas = {
        "trop gros": _fichier(contenu=JPEG + b"\x00" * DIX_MEGAOCTETS),
        "pas une image": _fichier(
            contenu=b"du texte", nom="ordonnance_benali_ahmed.txt", type_declare="text/plain"
        ),
        "octets menteurs": _fichier(contenu=PAS_UNE_IMAGE),
    }

    for etiquette, fichier in cas.items():
        ordonnance = _ordonnance()
        reponse = _appeler_photo(saisisseur, "post", ordonnance.pk, fichier=fichier)
        assert reponse.status_code == 400, (
            f"« {etiquette} » rend {reponse.status_code} et non 400 : "
            f"{_corps(reponse)!r}"
        )
        corps = _corps(reponse).decode("utf-8", "replace").lower()
        assert "benali" not in corps, (
            f"Le message de « {etiquette} » échoie le nom du fichier, qui porte le nom "
            f"du patient : {corps}"
        )

        from domaine.ordonnances.models import Ordonnance

        assert not Ordonnance.objects.get(pk=ordonnance.pk).photo, (
            f"« {etiquette} » a été refusé et pourtant quelque chose est attaché."
        )


# ======================================================================================
# 6 — le champ ne fige aucun locataire à l'import (T-04-39)
# ======================================================================================
def test_client09_le_champ_ne_fige_aucun_locataire_a_la_construction(db_all):
    """La menace que la forme du champ pourrait réintroduire, testée sur la **propriété**.

    `FileField.__init__` fait `self.storage = self.storage()` **une fois**, à la
    construction du champ, donc à l'import du module. Un appelable qui y résoudrait le
    locataire — `lambda: StockageDuLocataire(current_alias())` — lierait donc
    silencieusement celui qui se trouvait lié à cet instant : aucun en pratique, **un
    seul** au pire, et alors toutes les photos de tous les opticiens dans une seule
    arborescence.

    **Ce test ne regarde pas la forme du champ, il regarde ce que le champ fait.** Une
    assertion du type « `storage` n'est pas un appelable » interdirait une forme sans
    garantir la propriété — et l'appelable qui ne choisit que le *back-end* est
    parfaitement sûr, tandis qu'une instance dont le préfixe serait calculé dans
    `__init__` ne le serait pas. Ce qui compte est qu'un préfixe **change** avec le
    locataire lié et **n'existe pas** sans lui.
    """
    from domaine.ordonnances.models import Ordonnance
    from plateforme.tenancy.context import NoTenantBound, tenant_context

    stockage = Ordonnance._meta.get_field("photo").storage

    with tenant_context("tenant_a"):
        chez_a = stockage._prefixe()
    with tenant_context("tenant_b"):
        chez_b = stockage._prefixe()

    assert chez_a != chez_b, (
        f"Le stockage du champ rend le même préfixe {chez_a} pour deux locataires "
        "différents. Un locataire a été figé à la construction du champ, et toutes les "
        "photos de tous les opticiens partagent une arborescence."
    )
    with pytest.raises(NoTenantBound):
        stockage._prefixe()
