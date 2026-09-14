"""PERM-04 et PERM-05 — la portée magasin : des **lignes** et des **agrégats**, pas des champs.

**Ces tests ne sont pas encore implémentés.** Marqueur `pending`, corps volontairement
rouge ; les plans **03-05** (résolution de l'accès) et **03-07** (portée des querysets et
des agrégats) les implémentent et retirent le marqueur.

La distinction que ce fichier existe pour tenir, et qui est la raison pour laquelle il
n'est pas fusionné avec `test_projection.py` : la couche de projection caviarde des
**champs**. Elle ne peut caviarder ni une **ligne**, ni un **agrégat**. Un gérant qui n'a
accès qu'à un magasin mais qui reçoit encore un `SUM(montant)` sur toute l'affaire s'est
fait dire le chiffre d'affaires global que PERM-05 interdit, alors même que chaque champ
individuel était correctement masqué. Le total n'est le champ de personne.

Le magasin est une **colonne**, jamais une base : `tests/test_magasin_scoping.py`
(TENANT-07) pinne déjà l'asymétrie et l'absence délibérée de contextvar magasin. Il n'y a
donc pas de filtre implicite à hériter — la portée est écrite dans `get_queryset()` **et
dans chaque queryset de champ lié**, et c'est ce que ces tests vérifient.

Presque tous demandent `deux_magasins`. Ce n'est pas du confort : avec un seul magasin,
une vue qui ignore complètement la portée renvoie la même chose qu'une vue correcte, et
chaque assertion passe (`03-RESEARCH.md` P16).

**Aucun import du code en construction au niveau du module.**
"""

from __future__ import annotations

import pytest


# --------------------------------------------------------------------------------------
# PERM-04 — les lignes
# --------------------------------------------------------------------------------------
@pytest.mark.pending
def test_perm04_un_gerant_ne_voit_que_les_magasins_accordes_en_liste_et_en_detail(
    db_all, deux_magasins
):
    """PERM-04 — **et en détail**, ce qui est la moitié qu'on oublie.

    Filtrer la liste est le réflexe ; `/api/magasins/<id>/` sur un identifiant deviné ne
    passe pas par le même chemin si la portée a été écrite dans `list()` plutôt que dans
    `get_queryset()`. Rouge, ce test dirait exactement cela : la liste est propre, le
    détail est ouvert, et l'identifiant est un petit entier.

    Il porte donc **deux** assertions, pas une : la liste ne contient que Anfa, et le
    détail de Maârif répond 404.
    """
    pytest.fail("non implémenté : plan 03-07")


@pytest.mark.pending
def test_perm04_un_gerant_ne_peut_pas_ecrire_dans_un_magasin_non_accorde(
    db_all, deux_magasins
):
    """PERM-04 — la lecture filtrée ne dit rien de l'écriture.

    Une vue qui restreint `get_queryset()` protège la lecture, la modification et la
    suppression, mais **pas la création** : un POST qui nomme `magasin: <Maârif>` ne
    consulte aucun queryset. Rouge, ce test dirait qu'un gérant écrit dans un magasin qu'il
    ne voit même pas — une vente, un mouvement de stock ou une ligne de caisse chez un
    collègue, donc une balance qui ne tombe plus juste sans que personne sache pourquoi.

    La portée en écriture est une contrainte sur le **queryset du champ lié**, pas une
    validation ajoutée après coup.
    """
    pytest.fail("non implémenté : plan 03-07")


@pytest.mark.pending
def test_perm04_un_droit_obsolete_sur_un_magasin_inactif_n_accorde_rien(
    db_all, deux_magasins
):
    """PERM-04 — l'accès effectif est une **intersection**, pas une liste stockée.

    Les magasins se désactivent (`actif = False`), ils ne se suppriment pas : CLAUDE.md #4
    et dix ans de conservation fiscale l'imposent. Les lignes `AccesMagasin` qui les visent
    survivent donc indéfiniment. Rouge, ce test dirait que l'accès est lu tel quel dans la
    table, donc qu'un magasin fermé l'an dernier reste dans la portée de quelqu'un — et le
    jour où son code est réutilisé pour une nouvelle boutique, l'accès s'y rouvre tout seul.

    L'accès effectif se calcule : droits stockés ∩ magasins actifs.
    """
    pytest.fail("non implémenté : plan 03-05")


@pytest.mark.pending
def test_perm04_lacces_du_proprietaire_est_lensemble_complet_et_non_un_filtre_saute(
    db_all, deux_magasins
):
    """PERM-04 — « le propriétaire voit tout » doit être une valeur, pas un `if` qui saute.

    Les deux implémentations rendent la même réponse ici et divergent partout ailleurs. Si
    `est_proprietaire` fait sortir du chemin de portée par un retour anticipé, alors il
    existe un chemin de code où aucun filtre ne s'applique — et la phase 8 y branchera un
    agrégat, ou la phase 9 un rendu, en croyant que la portée est acquise. Si au contraire
    l'accès du propriétaire est l'**ensemble de tous les magasins actifs**, il n'y a qu'un
    seul chemin, et il est filtré.

    Rouge, ce test dirait que la branche existe. Il l'affirme sur l'objet `Acces`
    lui-même — un test qui ne regarderait que la réponse HTTP ne saurait pas distinguer.
    """
    pytest.fail("non implémenté : plan 03-05")


# --------------------------------------------------------------------------------------
# PERM-05 — les agrégats
# --------------------------------------------------------------------------------------
@pytest.mark.pending
def test_perm05_un_agregat_est_calcule_sur_le_queryset_deja_filtre(db_all, deux_magasins):
    """PERM-05 — le total est le trou que la projection de champs ne bouche pas.

    `Model.objects.aggregate(Sum(...))` repart du manager par défaut et ignore le queryset
    filtré que la vue vient de construire. Rouge, ce test dirait qu'un gérant d'un seul
    magasin reçoit le chiffre d'affaires de toute l'affaire dans une carte de tableau de
    bord — un nombre unique, sans champ protégé, sans ligne interdite, et pourtant
    exactement l'information que PERM-05 interdit.

    Avec un seul magasin ce test est vide de sens : la somme filtrée et la somme globale
    sont le même nombre. D'où `deux_magasins`, avec des montants différents des deux côtés.
    """
    pytest.fail("non implémenté : plan 03-07")


def test_perm05_le_catalogue_declare_prix_achat_marge_et_ca_global():
    """PERM-05 — la phase 3 livre le **mécanisme** ; les champs arrivent en phases 8 et 10.

    `prix_achat`, `marge` et le chiffre d'affaires global n'existent pas encore comme
    colonnes — `03-VALIDATION.md` § « Known Deferral » le dit, et la vérification vivante
    appartient à la phase 8. Ce que la phase 3 peut prouver, et que ce test prouve, c'est
    que les **codes** de permission correspondants sont déclarés dès maintenant, donc que
    la phase 8 n'aura qu'une ligne de registre à ajouter au lieu d'un modèle de droits à
    inventer sous pression.

    Rouge, il dirait que le catalogue a été écrit pour ce qui existe aujourd'hui, ce qui est
    la façon dont une garantie architecturale se perd : non par renversement, par omission.
    """
    from plateforme.comptes.permissions_catalogue import (
        EXPLICATIONS,
        PREREQUIS,
        SECTIONS,
        Permission,
    )

    differes = (
        "article.voir_prix_achat",  # phase 8
        "vente.voir_marge",  # phase 8
        "dashboard.voir_ca_global",  # phase 10
    )
    for code in differes:
        assert code in Permission.values, code
        # Déclaré ne suffit pas : il doit être **accordable**, donc porté par une section
        # de l'écran et pourvu de son explication. Un code présent dans l'énumération mais
        # absent des sections est invisible, et la phase 8 le redécouvrirait sous pression.
        assert any(code in section.codes for section in SECTIONS), code
        assert EXPLICATIONS[code].strip().endswith("."), code

    # La dépendance que `03-UI-SPEC.md` 7.6 impose entre les deux codes de phase 8 : voir
    # la marge sans voir le prix d'achat rendrait le prix d'achat calculable à la main.
    assert PREREQUIS["vente.voir_marge"] == ("article.voir_prix_achat",)

    # Et le contrôle positif : aucun des trois n'a de colonne derrière lui en phase 3.
    # Si l'un en acquiert une ici, ce n'est plus un mécanisme, c'est une fonctionnalité
    # arrivée en avance et non testée.
    from django.apps import apps

    champs_metier = {
        f"{modele._meta.label}.{champ.name}"
        for config in apps.get_app_configs()
        if config.name.startswith("domaine.")
        for modele in config.get_models()
        for champ in modele._meta.get_fields()
    }
    assert not {nom for nom in champs_metier if nom.endswith((".prix_achat", ".marge"))}
