"""PERM-02 et PERM-03 — créer un compte gérant, le désactiver, accorder et révoquer.

**Ces tests ne sont pas encore implémentés.** Ils portent le marqueur `pending` et
échouent volontairement. Trois plans se partagent leur mise au vert :

* **03-04** pose `DroitAccorde(utilisateur, magasin_code, code)`, `AccesMagasin` et
  `JournalDroit` — la forme de stockage ;
* **03-05** pose `Acces` et `acces_pour()` — la résolution ;
* **03-09** pose la surface d'écriture de l'API — création de compte, octroi, révocation.

La règle que ce fichier existe pour pinner est CLAUDE.md **#6** : *« Permissions are
granted per gérant individually, as data, not as role tiers »*, et CLAUDE.md **#13** :
les droits sont stockés par **(gérant, magasin, permission)**. `03-RESEARCH.md` §4 propose
`DroitAccorde(utilisateur, code)`, sans dimension magasin ; son propre bandeau de
correction et `03-UI-SPEC.md` 0.1 disent que cette forme est abandonnée. Les deux derniers
tests de ce fichier sont ceux que CLAUDE.md #13 impose et que la table de `03-VALIDATION.md`
avait omis — sans eux, un modèle conforme à la recherche passerait toute la suite.

Tout se joue sur `default` : identité, appartenance et droits vivent dans le plan de
contrôle (CLAUDE.md #11). Les magasins, eux, sont des lignes dans la base d'un opticien,
ce qui est précisément pourquoi le droit stocke un `magasin_code` et non une clé
étrangère — une FK inter-alias n'existe pas.

**Aucun import du code en construction au niveau du module** : ils descendent dans le
corps des fonctions, sans quoi la collecte de la suite entière casserait tant que les
modèles n'existent pas.
"""

from __future__ import annotations

import pytest


# --------------------------------------------------------------------------------------
# PERM-02 — le compte
# --------------------------------------------------------------------------------------
@pytest.mark.pending
def test_perm02_un_proprietaire_ne_cree_un_compte_que_dans_son_propre_client(db_all):
    """PERM-02 — le `client` du nouveau compte est imposé par le serveur, jamais reçu.

    Rouge, ce test dirait que `client` est un champ acceptable en entrée : le propriétaire
    de l'affaire A poste `client: <id de B>` et obtient un compte dans l'affaire d'un
    concurrent, avec une adresse de connexion qu'il contrôle. C'est l'élévation de
    privilèges la plus directe de la phase, et elle ne demande aucun outil — juste un
    champ de plus dans le corps JSON (`03-RESEARCH.md` A-03-05).

    Le test crée deux clients, précisément parce qu'un test à un seul client ne peut pas
    distinguer « le serveur impose le bon » de « le serveur accepte ce qu'on lui donne,
    qui se trouve être le bon ».
    """
    pytest.fail("non implémenté : plan 03-09")


@pytest.mark.pending
def test_perm02_un_compte_desactive_est_refuse_des_la_requete_suivante(db_all):
    """PERM-02 — désactiver doit mordre tout de suite, sans machinerie de révocation.

    `ModelBackend.get_user()` appelle `user_can_authenticate()` à **chaque** requête, donc
    `is_active = False` est effectif dès la suivante, gratuitement — à condition que rien
    n'ait mis le principal en cache. Rouge, ce test dirait qu'une couche de cache ou un
    jeton porteur s'est glissée entre la base et `request.user`, et qu'un gérant congédié
    ce matin travaille encore cet après-midi.

    Le test agit sur une session **déjà ouverte** : désactiver avant la connexion ne
    prouverait que le refus au login, qui n'est pas ce que PERM-02 demande.
    """
    pytest.fail("non implémenté : plan 03-09")


# --------------------------------------------------------------------------------------
# PERM-03 — le droit
# --------------------------------------------------------------------------------------
@pytest.mark.pending
def test_perm03_un_droit_est_une_ligne_pas_un_palier(db_all):
    """PERM-03 / CLAUDE.md #6 — aucun palier de rôle, nulle part.

    Rouge, ce test dirait qu'un `role`, un `profil`, un `niveau` ou un `Group` est réapparu
    quelque part — c'est-à-dire que les droits ne sont plus des données mais des bundles.
    Le mode de défaillance est commercial autant que technique : `research/FEATURES.md`
    donne le modèle de permissions par gérant comme le **seul** différenciateur trouvé sur
    ce marché, et un palier « Gérant » le supprime en une migration.

    Le test affirme sur `DroitAccorde._meta` et sur le catalogue, pas sur une docstring :
    une docstring qui dit « pas de rôles » ne devient pas rouge quand quelqu'un en ajoute.
    """
    pytest.fail("non implémenté : plan 03-04")


@pytest.mark.pending
def test_perm03_un_droit_est_stocke_par_gerant_magasin_et_permission(db_all, deux_magasins):
    """PERM-03 / CLAUDE.md #13 — la dimension magasin existe dans le stockage, dès le jour un.

    Ce test **n'est pas dans la table de `03-VALIDATION.md`** ; il est ajouté ici parce que
    CLAUDE.md #13 l'impose et que `03-UI-SPEC.md` 0.1 montre que la forme proposée par la
    recherche — `UniqueConstraint(utilisateur, code)` — la reverse. Sans ce test, un modèle
    à une seule dimension passerait la phase entière et la correction serait une migration
    de données, sur des droits, en production.

    Rouge, il dit exactement une chose : la contrainte d'unicité porte sur
    `(utilisateur, magasin_code, code)` et non sur `(utilisateur, code)`. L'interface, elle,
    reste une case à cocher unique par droit — le « par magasin » ne se montre que sur
    demande (`03-UI-SPEC.md` §6.4). C'est le stockage qui doit pouvoir, pas l'écran qui doit
    montrer.
    """
    pytest.fail("non implémenté : plan 03-04")


@pytest.mark.pending
def test_perm03_un_droit_accorde_dans_un_magasin_ne_fuit_pas_vers_un_autre(
    db_all, deux_magasins
):
    """PERM-03 / CLAUDE.md #13 — la moitié *comportementale* de la dimension magasin.

    Le test précédent regarde la contrainte ; celui-ci regarde la réponse. Une contrainte
    à trois colonnes au-dessus d'un `acces.peut(code)` qui ignore le magasin stocke
    correctement une distinction que le code ne fait pas : le gérant qui peut faire une
    remise à Anfa peut en faire une à Maârif, et la base a l'air juste.

    Il faut **deux** magasins pour que ce test veuille dire quelque chose, d'où
    `deux_magasins` : avec un seul, « le droit du bon magasin » et « n'importe quel droit »
    sont le même objet et l'assertion passe au-dessus du bug (`03-RESEARCH.md` P16).
    """
    pytest.fail("non implémenté : plan 03-05")


@pytest.mark.pending
def test_perm03_la_revocation_prend_effet_sans_reconnexion(db_all):
    """PERM-03 — retirer un droit mord à la requête suivante, sans déconnecter personne.

    C'est la promesse que `03-UI-SPEC.md` §7.8 affiche à l'écran, en toutes lettres, sous
    la liste des droits. Rouge, ce test dirait que cette phrase est fausse : l'`Acces` est
    résolu une fois et posé en session, ou mis en cache par utilisateur, donc le droit
    retiré à 14 h continue de s'appliquer jusqu'à la déconnexion. Une promesse affichée et
    non tenue est pire qu'une promesse absente — le propriétaire croit avoir agi.
    """
    pytest.fail("non implémenté : plan 03-05")


@pytest.mark.pending
def test_perm03_un_proprietaire_ne_peut_pas_accorder_a_un_utilisateur_dun_autre_client(
    db_all,
):
    """PERM-03 — l'octroi traverse la frontière des affaires si personne ne l'en empêche.

    Les droits vivent dans le plan de contrôle, donc **tous les gérants de la flotte sont
    dans la même table**. Rien dans le schéma n'empêche une ligne `DroitAccorde` dont
    l'`utilisateur` appartient à une autre affaire : c'est une clé étrangère parfaitement
    valide. La garantie est applicative, donc elle a besoin d'un test, et le test a besoin
    d'un second client — d'où `db_all`.

    Rouge, il dirait qu'un propriétaire peut accorder des droits sur ses propres magasins à
    un compte qu'il ne contrôle pas, ou pire, à un compte d'une autre affaire qu'il
    rendrait ainsi actif chez lui.
    """
    pytest.fail("non implémenté : plan 03-09")


@pytest.mark.pending
def test_perm03_le_journal_enregistre_qui_a_accorde_quoi_et_quand(db_all):
    """PERM-03 — « qui a donné les marges à Karim ? » doit avoir une réponse après coup.

    La révocation **supprime** la ligne d'octroi : c'est ce qui rend `acces.peut()`
    trivialement juste. Le prix est qu'après une révocation il ne reste rien à interroger,
    sauf journal. `JournalDroit` est append-only et survit à la ligne qu'il décrit
    (menace T-03-19).

    Rouge, ce test dirait soit que le journal n'est pas écrit, soit — le cas sournois —
    qu'il est écrit mais supprimé en cascade avec le droit, donc qu'il ne répond à la
    question que tant que la question ne se pose pas.
    """
    pytest.fail("non implémenté : plan 03-04")
