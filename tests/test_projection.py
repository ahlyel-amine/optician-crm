"""PERM-06 — un registre, quatre consommateurs, un test paramétré.

**Ces tests ne sont pas encore implémentés.** Marqueur `pending`, corps volontairement
rouge ; les plans **03-06** (registre, sérialiseurs, export, document, schéma) et
**03-07** (portée et écriture) les implémentent et retirent les marqueurs un par un.

Le problème à concevoir contre n'est pas « où vit le filtrage ». C'est « qu'est-ce qui
empêche trois rendus de diverger d'ici la phase 9 ». Une classe de base partagée ne
l'empêche pas : la phase 9 écrira un gabarit de facture contenant `{{ ligne.prix_achat }}`,
Django rendra une chaîne vide, et **rien ne le signalera** — ni exception, ni
avertissement, ni test. Le lien doit être énumérable, et le test doit itérer dessus.

D'où la forme du premier test, qui est le test porteur de toute la phase : il est
paramétré `CHAMPS_PROTEGES` × `{api, export, document}`. Ajouter une ligne au registre en
phase 8 produit **automatiquement** trois assertions, une par rendu. Ajouter un quatrième
rendu en phase 9 sans lui faire lire le registre le fait échouer dès qu'il rejoint la
liste `rendu`. C'est le test, et non l'abstraction, qui rend PERM-06 vrai.

`CHAMPS_PROTEGES` n'existe pas encore, et une paramétrisation est évaluée à la
**collecte** : le registre est donc importé dans une fonction, sous garde, avec une valeur
de repli constante. Sans ce repli, la collecte de la suite entière casserait jusqu'au plan
03-06. Le corps du test, lui, importera sans garde — c'est ce qui le rendra franchement
rouge le jour où son marqueur `pending` sautera.

`test_perm06_aucun_modele_metier_n_est_enregistre_dans_ladmin` — le douzième nom de la
liste PERM-06 de `03-VALIDATION.md` — **n'est pas ici** : il est déjà implémenté et vert
dans `tests/test_comptes_socle.py`, depuis le plan 03-01, avec son contrôle positif. Le
dupliquer ici donnerait deux tests du même nom dans la suite, dont un seul serait
maintenu.
"""

from __future__ import annotations

import pytest

#: La clé de repli de la paramétrisation, et la ressource de test qu'elle nomme.
#: `tests.RessourceFixture.valeur_protegee` est un modèle de test créé au plan 03-06 dans
#: `tests/ressources_fixture.py`, et il vit dans `tests/` plutôt que dans `domaine/` pour
#: une raison de fond : le registre est **vide** en phase 3 — `prix_achat`, `marge` et le
#: chiffre d'affaires global n'existent pas avant les phases 8 et 10. Sans une ressource
#: fictive, le test porteur de la phase serait paramétré sur zéro cas, donc vert, donc sans
#: valeur. Un test paramétré sur rien est un test qui ne teste rien.
CHAMP_DE_REPLI = ("tests.RessourceFixture.valeur_protegee", "article.voir_prix_achat")

#: Les trois rendus qui doivent s'accorder. La phase 9 en ajoutera un quatrième (le PDF A4
#: de WeasyPrint) ; il rejoint cette liste, et les assertions apparaissent toutes seules.
RENDUS = ["api", "export", "document"]


def champs_proteges_parametres():
    """Les cas `(clé, code)` de la paramétrisation, avec repli avant le plan 03-06.

    Import **local et gardé**, délibérément : les arguments de `parametrize` sont évalués à
    l'import du module de test, donc un import au niveau du module transformerait l'absence
    du registre en erreur de collecte pour toute la suite. Le repli n'est pas une
    complaisance — c'est ce qui permet au test nommé d'exister avant son implémentation, ce
    que `.planning/TESTING.md` §1 demande.
    """
    try:
        from plateforme.projection.registre import CHAMPS_PROTEGES
    except ImportError:
        return [CHAMP_DE_REPLI]
    return sorted(CHAMPS_PROTEGES.items()) or [CHAMP_DE_REPLI]


# --------------------------------------------------------------------------------------
# Le test porteur de la phase
# --------------------------------------------------------------------------------------
@pytest.mark.pending
@pytest.mark.parametrize("rendu", RENDUS)
@pytest.mark.parametrize("cle,code", champs_proteges_parametres())
def test_perm06_champ_protege_absent_de_lapi_de_lexport_et_du_document(
    rendu, cle, code, db_all, deux_magasins
):
    """PERM-06 — le même champ, le même gérant, les trois rendus, une seule réponse.

    **Absent**, et non vide, et non nul, et non masqué à l'affichage : la clé n'est pas dans
    le JSON, la colonne n'est pas dans le CSV, le gabarit du document ne reçoit pas la
    valeur. Une valeur présente mais non affichée est disponible dans les outils de
    développement, dans une réponse en cache et dans le prochain refactor.

    Rouge sur un seul `rendu`, ce test nomme exactement celui qui a divergé — ce qui est
    toute la différence entre « la projection est cassée quelque part » et « l'export CSV de
    la phase 8 ne passe pas par le registre ».
    """
    pytest.fail("non implémenté : plan 03-06")


# --------------------------------------------------------------------------------------
# Les échappatoires, une par attaque de la recherche
# --------------------------------------------------------------------------------------
@pytest.mark.pending
def test_perm06_tout_champ_de_modele_expose_est_classe():
    """PERM-06 / A-03-08 — un champ non classé est un champ que personne n'a examiné.

    Le registre ne protège que ce qu'on y a inscrit, donc son mode de défaillance n'est pas
    la mauvaise entrée, c'est l'entrée **manquante**. La phase 6 imbriquera
    `ArticleSerializer` dans `LigneVenteSerializer` avec un `ModelSerializer` ordinaire et
    `prix_achat` réapparaîtra, sans que rien ne change dans le registre ni dans les tests
    existants.

    Ce test parcourt les sous-classes de `ModelSerializer` et exige que chaque champ exposé
    soit dans `CHAMPS_PROTEGES` ou dans `CHAMPS_PUBLICS`. « Public » est alors une décision
    écrite, datée et relisible, au lieu d'un silence. Rouge, il nomme le champ et le
    sérialiseur qui l'a introduit, le jour où il est introduit.
    """
    pytest.fail("non implémenté : plan 03-06")


@pytest.mark.pending
def test_perm06_le_schema_est_identique_pour_le_proprietaire_et_le_gerant(db_all):
    """PERM-06 / A-03-09 — le schéma ne doit pas être un document par utilisateur.

    `build_mock_request` de drf-spectacular recopie `request.user` (vérifié,
    `plumbing.py:1288`), donc un schéma généré à la volée varie selon l'appelant : le gérant
    reçoit un document d'où `prix_achat` est absent, et le comparer à celui du propriétaire
    **énumère** les champs protégés. La fuite n'est pas la valeur, c'est la liste.

    Elle est doublement coûteuse : le client TypeScript est généré depuis ce schéma, donc un
    schéma qui varie produit des types qui varient, et la SPA cesse d'avoir un contrat.
    Rouge, ce test dirait que `GET_MOCK_REQUEST` n'épingle plus `Acces.SCHEMA`.
    """
    pytest.fail("non implémenté : plan 03-06")


@pytest.mark.pending
def test_perm06_un_champ_protege_est_optionnel_dans_le_schema():
    """PERM-06 / P9 — un champ protégé marqué `required` ment au client TypeScript.

    Le schéma est le contrat du client généré. Un champ protégé déclaré `required` promet
    une clé qui, pour un gérant, ne sera pas là : le type dit `prix_achat: string`, la valeur
    est `undefined`, et le bug se manifeste en phase 8 dans un composant qui n'a rien à voir.
    Le champ doit sortir du tableau `required` de son composant — par le post-traitement, pas
    par `COMPONENT_NO_READ_ONLY_REQUIRED = True`, qui est l'instrument brutal qui rendrait
    `id` optionnel du même coup.

    Rouge, ce test dirait que le hook de post-traitement a été retiré ou n'est plus branché.
    """
    pytest.fail("non implémenté : plan 03-06")


@pytest.mark.pending
def test_perm06_un_champ_protege_ne_peut_ni_trier_ni_filtrer(db_all, deux_magasins):
    """PERM-06 / A-03-07 — le champ n'est dans aucune réponse, et il est entièrement divulgué.

    `?ordering=prix_achat` révèle l'ordre total d'un champ caché ; `?prix_achat__gt=1500` en
    récupère la valeur exacte par dichotomie, en une vingtaine de requêtes. Le paramètre de
    requête est un oracle, et il n'a besoin d'aucune fuite de champ pour fonctionner.

    Un refus **silencieux** est aussi un oracle — l'ordre du résultat change selon que le
    champ a été accepté ou ignoré — donc la réponse attendue est **400**, pas « ignoré ». Les
    allowlists de tri et de filtre sont dérivées de la projection, jamais écrites à la main :
    une liste maintenue à part se désynchronise du registre à la première phase qui ajoute
    une colonne.
    """
    pytest.fail("non implémenté : plan 03-07")


@pytest.mark.pending
def test_perm06_un_champ_protege_ne_peut_pas_etre_ecrit_par_un_gerant(
    db_all, deux_magasins
):
    """PERM-06 — affirmer que la valeur est **inchangée**, jamais qu'un 400 survient.

    C'est la nuance qui décide si ce test vaut quelque chose. DRF ignore silencieusement une
    clé inconnue dans un corps de requête : si le champ est correctement retiré de la
    projection, un PATCH qui le nomme renvoie **200** et n'écrit rien. Un test qui attendrait
    400 serait donc rouge au-dessus d'un code parfaitement correct, et quelqu'un le
    « réparerait » en rendant le champ inscriptible.

    L'assertion est donc : la valeur relue depuis la base est celle d'avant. Rouge, elle dit
    qu'un gérant sans droit sur `prix_achat` peut le réécrire — donc fausser une marge que
    lui-même n'a pas le droit de lire.
    """
    pytest.fail("non implémenté : plan 03-06")


@pytest.mark.pending
def test_perm06_aucune_vue_ne_renvoie_un_values_queryset():
    """PERM-06 / A-03-04 — la faiblesse structurelle d'une projection par sérialiseur, énoncée.

    `Response(qs.values("prix_achat"))` et `qs.annotate(marge=F("pv") - F("pa"))` ne touchent
    **aucun** sérialiseur : la projection n'est pas contournée, elle est absente. Aucune
    classe de base ne peut rattraper cela, donc la garantie est un test au niveau du
    **source** — le même idiome que `tests/test_migration_conventions.py`, qui lit l'AST
    plutôt que d'exécuter.

    Un test au niveau du source est le bon outil ici précisément parce que le chemin fautif
    ne s'exécute jamais dans la suite : personne n'écrit un test pour la vue qu'il vient
    d'ajouter sans projection.
    """
    pytest.fail("non implémenté : plan 03-06")


@pytest.mark.pending
def test_perm06_le_renderer_html_est_absent_hors_developpement():
    """PERM-06 / A-03-06 — l'API navigable énumère des objets que l'appelant ne peut pas voir.

    Le renderer HTML de DRF dessine ses formulaires depuis `get_fields()`, qui **est**
    projeté — donc moins grave qu'il n'y paraît. Mais il rend aussi le `__str__` des objets
    liés dans les listes déroulantes, et une liste déroulante énumère des lignes. Un gérant
    d'un seul magasin y lit les noms des clients des autres.

    `DEFAULT_RENDERER_CLASSES` ne contient donc que le renderer JSON en base, et
    `BrowsableAPIRenderer` n'est ajouté que dans `local.py`. Rouge, ce test dirait qu'un
    réglage de confort posé pour déboguer est parti en production.
    """
    pytest.fail("non implémenté : plan 03-06")


@pytest.mark.pending
def test_perm06_toute_tache_de_rendu_exige_acting_utilisateur_id():
    """PERM-06 / A-03-03 — une tâche Celery sait de quel client, pas de qui.

    `TenantTask` reçoit `client_id` et relie le contexte : la tenancy est sauve. Mais un PDF
    ou un export rendus depuis une tâche n'ont **aucun** `request`, donc aucun `Acces`, donc
    rien qui distingue le propriétaire d'un gérant. Le rendu se fait par défaut — et le
    défaut, si personne ne le décide, est la vue complète, envoyée par e-mail au gérant qui
    l'a demandée.

    La signature est donc `(*, client_id, acting_utilisateur_id, ...)` et la tâche recalcule
    `acces_pour(...)` dans le contexte lié. Jamais un `Acces` ni une instance de modèle en
    argument — déjà interdit par la docstring de `TenantTask`. Ce test parcourt le registre
    des tâches et affirme sur les signatures : rouge, il nomme la tâche ajoutée sans le
    paramètre, à la phase où elle est ajoutée.
    """
    pytest.fail("non implémenté : plan 03-06")


@pytest.mark.pending
def test_perm06_lacces_absent_vaut_aucun_droit():
    """PERM-06 / P2 — la projection doit échouer **fermée**, comme le routeur (CLAUDE.md #8).

    `getattr(request, "acces", None)` suivi de `if acces is None: return fields` rend tous
    les champs protégés sur **tout** chemin où le middleware n'a pas tourné : une vue montée
    hors de la pile habituelle, une commande de gestion, un test, une tâche. Le défaut doit
    être `Acces.ANONYME` — ensemble de permissions vide — jamais `None`, et jamais « on
    laisse passer ».

    C'est le même raisonnement que le routeur qui lève au lieu de renvoyer `None` : un défaut
    permissif produit une fuite silencieuse, un défaut fermé produit une page vide qu'on
    remarque. Rouge, ce test dirait qu'un sérialiseur sans `request` dans son contexte rend
    les champs protégés.
    """
    pytest.fail("non implémenté : plan 03-06")


@pytest.mark.pending
def test_perm06_le_catalogue_servi_a_un_gerant_manager_est_deja_intersecte(
    db_all, deux_magasins
):
    """PERM-06 / `03-UI-SPEC.md` §7.7 — « absent, pas désactivé », au niveau du fil.

    Un gérant qui détient `compte.gerer` administre ses collègues, et ne doit pas pouvoir
    accorder un droit qu'il ne détient pas lui-même, ni un accès à un magasin qu'il n'a pas.
    La tentation est de rendre ces lignes grisées — ce qui lui apprend que la permission
    existe et qu'elle lui manque — ou de les filtrer dans le navigateur, ce qui les laisse
    dans la réponse.

    Le point de terminaison du catalogue sert donc à chaque appelant un catalogue **déjà
    intersecté** avec ses propres droits et magasins : un code qu'il ne détient pas est
    absent du JSON, exactement comme un champ non autorisé est absent d'une ligne. Le client
    rend ce qu'il reçoit et n'a aucune branche de filtrage à lui, donc rien à faire fuir par
    un cache, un outil de développement ou un refactor à venir (`03-UI-CHECK.md`,
    recommandation sur §7.7).
    """
    pytest.fail("non implémenté : plan 03-09")
