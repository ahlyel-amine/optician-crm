"""CLIENT-10 / CLIENT-01 — les outils de recherche, et la discipline de seuil.

Cinq tests, et chacun tient une décision mesurée de `04-RESEARCH.md` plutôt qu'une
préférence :

* la normalisation est une **fonction Python nommée**, donc immuable par construction —
  `unaccent` est `STABLE` et ne peut pas entrer dans une expression d'index (`42P17`) ;
* elle ne vide **pas** l'écriture arabe, que BRAND-05 anticipe ;
* la clé phonétique groupe les quatre variantes de Mohamed et sépare Abdelkader
  d'Abdelkrim, ce qu'aucun seuil de trigramme ne fait ;
* elle est **vide** en écriture arabe, et une clé vide qui servirait de critère
  rapprocherait chaque fiche arabe de toutes les autres — une divulgation de fiche ;
* et le seuil `pg_trgm.word_similarity_threshold` ne survit pas à la transaction, parce
  qu'un `SET` nu a été **observé** chevauchant une connexion serveur du pool (T-02-02).
"""

from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent

#: Les deux arbres qui contiennent du code applicatif. `tests/` est délibérément exclu :
#: les sources synthétiques du contrôle positif ci-dessous contiennent, exprès, la faute
#: que la garde cherche.
ARBRES_SCANNES = ("plateforme", "domaine")


# ======================================================================================
# Normalisation
# ======================================================================================
def test_client10_la_normalisation_plie_les_accents_la_casse_et_les_espaces():
    """NFKD + retrait des diacritiques + casefold + espaces repliés, et rien de plus.

    Rouge dans un sens : une normalisation qui n'aurait plié que la casse, donc une
    recherche sourde aux accents alors que tout le produit est en français — « Aïcha »
    ne trouverait pas « Aicha ».

    Rouge dans l'autre : une normalisation trop zélée qui supprimerait la ponctuation.
    Le trait d'union **reste**. Il n'est pas un accent, et le rapprochement
    `elhassan ↔ el hassan` est le travail du trigramme, pas du normaliseur : un
    normaliseur qui décide à la place de la couche qui mesure rend la mesure inaudible.
    """
    from domaine.clients.recherche import normaliser_pour_recherche

    cas = [
        ("  Aïcha   EL   Alaoui ", "aicha el alaoui"),
        ("MOHAMMED", "mohammed"),
        ("Zoubaïr", "zoubair"),
        ("El-Hassan", "el-hassan"),
    ]
    for entree, attendu in cas:
        assert normaliser_pour_recherche(entree) == attendu, (
            f"normaliser_pour_recherche({entree!r}) doit rendre {attendu!r}"
        )


def test_client10_la_normalisation_laisse_l_ecriture_arabe_intacte():
    """Un nom en écriture arabe traverse le normaliseur sans être vidé.

    BRAND-05 anticipe des noms de clients en arabe. NFKD ne décompose rien d'utile ici et
    l'arabe n'a pas de casse, donc la sortie doit être l'entrée. Un normaliseur qui
    filtrerait « tout ce qui n'est pas ASCII » rendrait `""` pour chacun de ces noms, donc
    rendrait **toutes les fiches arabes identiques** dans la colonne indexée.
    """
    from domaine.clients.recherche import normaliser_pour_recherche

    obtenu = normaliser_pour_recherche("محمد")

    assert obtenu, "le nom arabe a été vidé par la normalisation"
    assert obtenu == "محمد".casefold(), (
        f"attendu la valeur casefoldée inchangée, obtenu {obtenu!r}"
    )


# ======================================================================================
# Clé phonétique
# ======================================================================================
def test_client10_la_cle_phonetique_groupe_les_variantes_et_separe_les_homographes(
    tenant_a,
):
    """`metaphone(nom, 8)` : une clé pour les quatre Mohamed, deux pour les deux Abdel.

    C'est l'exigence CLIENT-10 elle-même, et c'est ce qu'aucune autre méthode ne fait :
    mesuré, `mohammed ↔ mhamed` = 0,333 passe **sous** `fatima ↔ fatiha` = 0,400, donc
    aucun seuil de trigramme n'admet le vrai positif sans admettre le faux. Soundex et
    dmetaphone groupent Abdelkader avec Abdelkrim.

    Rouge dans un sens : une clé qui ne groupe pas les variantes, donc CLIENT-10 non
    servie. Rouge dans l'autre : une clé trop courte, qui fusionne deux personnes — ce
    qui, au comptoir, est la fiche du voisin avec ses ordonnances dessus.
    """
    from domaine.clients.recherche import (
        LONGUEUR_CODE_PHONETIQUE,
        cle_phonetique,
        normaliser_pour_recherche,
    )

    assert LONGUEUR_CODE_PHONETIQUE == 8, (
        "à 4, metaphone('abdelkader') et metaphone('abdelkrim') rendent tous deux ABTL : "
        "la longueur porte le résultat, ce n'est pas un réglage (mesuré, 04-RESEARCH §5.5)"
    )

    def cle(nom: str) -> str:
        return cle_phonetique(normaliser_pour_recherche(nom), alias=tenant_a)

    variantes = ["Mhamed", "Mohamed", "Mohammed", "Mouhamed"]
    cles_variantes = {nom: cle(nom) for nom in variantes}
    assert len(set(cles_variantes.values())) == 1, (
        f"les quatre variantes de Mohamed doivent rendre UNE clé : {cles_variantes}"
    )

    homographes = {nom: cle(nom) for nom in ("Abdelkader", "Abdelkrim")}
    assert len(set(homographes.values())) == 2, (
        f"Abdelkader et Abdelkrim sont deux personnes : {homographes}"
    )


def test_client10_la_cle_phonetique_est_vide_en_ecriture_arabe(tenant_a):
    """L'écriture arabe rend `""`, et un nom latin rend une clé non vide.

    Les deux assertions sont indissociables. Sans la seconde, une implémentation qui
    rendrait toujours `""` serait verte — et une clé vide qui sert de critère rapproche
    chaque fiche arabe de **toutes** les autres, ce qui est une divulgation de fiche et
    non une gêne d'interface (menace T-04-02).

    La garde vit des deux côtés. Ici : la clé est vide, donc rien ne la remplit. Dans le
    modèle (tâche 3) : l'index phonétique est **partiel**, `WHERE cle_phonetique <> ''`.
    Dans la requête (plan 04-03) : la branche phonétique est sautée quand la clé de la
    requête est vide.
    """
    from domaine.clients.recherche import cle_phonetique

    assert cle_phonetique("محمد", alias=tenant_a) == "", (
        "metaphone rend '' en écriture arabe (mesuré) ; la fonction doit rendre la chaîne "
        "vide plutôt que None, pour que la colonne dérivée soit comparable"
    )
    assert cle_phonetique("mohamed", alias=tenant_a) != "", (
        "assertion jumelle : sans elle, une implémentation qui rend toujours '' passerait"
    )


# ======================================================================================
# Le seuil, et la fuite par le pooler (T-02-02)
# ======================================================================================
def _seuil_observe(alias: str) -> str:
    """Le seuil `pg_trgm.word_similarity_threshold` vu par une transaction sur `alias`.

    Deux instructions dans **une** transaction, et les deux sont nécessaires :

    * PgBouncer en mode transaction peut rendre une connexion serveur différente entre
      deux instructions en autocommit, donc une lecture non encadrée ne dit pas de quel
      backend elle parle ;
    * le GUC d'une extension n'existe que dans un backend où une fonction de cette
      extension a déjà été appelée — mesuré : sur une session fraîche,
      `SHOW pg_trgm.word_similarity_threshold` rend `unrecognized configuration parameter`.
    """
    from django.db import connections, transaction

    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cur:
            cur.execute("SELECT similarity('a', 'b')")
            cur.execute("SELECT current_setting('pg_trgm.word_similarity_threshold')")
            return cur.fetchone()[0]


def _liberer_le_pool(*, dbname: str, user: str, password: str) -> None:
    """Demander à PgBouncer de lâcher ses connexions serveur vers `dbname`.

    Sans cela, le pooler garde la connexion serveur jusqu'à `server_idle_timeout` (60 s)
    et le `DROP DATABASE` de fin de session de pytest-django échoue avec « is being
    accessed by other users ». Ce serait un avertissement aujourd'hui et un échec de
    teardown le jour où quelqu'un en fait une erreur — pour une raison qui n'aurait rien
    à voir avec le test qui l'a causée.

    `KILL` met aussi la base en pause côté pooler, d'où le `RESUME` qui suit.
    """
    import psycopg
    from django.conf import settings

    with psycopg.connect(
        host=settings.PGBOUNCER_HOST,
        port=settings.PGBOUNCER_PORT,
        user=user,
        password=password,
        dbname="pgbouncer",
        connect_timeout=5,
        autocommit=True,
    ) as admin:
        with admin.cursor() as cur:
            # La console d'administration ne parle que le protocole simple, et `KILL`
            # n'accepte pas de paramètre lié. Le nom vient de `settings`, jamais d'une
            # saisie, et il est encadré de guillemets doubles comme un identifiant.
            nom = '"' + dbname.replace('"', '""') + '"'
            cur.execute(f"KILL {nom}")
            try:
                cur.execute(f"RESUME {nom}")
            except psycopg.Error:
                # Déjà reprise : `KILL` sur une base sans pool ne la met pas en pause.
                pass


@pytest.mark.slow
def test_client10_le_seuil_de_mot_ne_fuit_pas_vers_une_connexion_fraiche(
    tenant_a, allow_runtime_tenant_aliases
):
    """Le seuil posé par `seuil_de_mot` ne survit pas à la transaction, **par le pooler**.

    Le scénario mesuré de `04-RESEARCH.md` §2.4, rejoué. Reproduit à la main pendant
    l'exécution de ce plan :

        SHOW pg_trgm.word_similarity_threshold   -> 0.6
        SET  pg_trgm.word_similarity_threshold = 0.91
        --- connexion cliente fermée, connexion cliente NEUVE ouverte ---
        SHOW pg_trgm.word_similarity_threshold   -> 0.91   <-- a chevauché le pool

    **La fermeture puis réouverture est le test.** Relire dans la même session prouverait
    seulement que `SET LOCAL` existe. Ce qui a été observé, c'est un réglage qui monte sur
    une connexion **serveur** du pool et réapparaît dans la requête suivante — donc
    potentiellement dans celle d'un autre opticien.

    L'alias est enregistré à la volée vers **PgBouncer**, et non vers PostgreSQL :
    `config/settings/test.py` pointe `tenant_a` sur `PG_ADMIN_PORT` pour pouvoir faire du
    DDL, et sur une connexion directe fermer la connexion Django ferme aussi le backend —
    la fuite ne peut alors pas se reproduire, et le test serait vert contre un `SET` nu.
    C'est exactement la substitution qui avait laissé passer le trou de `auth_query`
    (`tests/test_pgbouncer_auth.py`).
    """
    from django.conf import settings
    from django.db import connections

    from domaine.clients.recherche import SEUIL_MOT, seuil_de_mot
    from plateforme.tenancy.registry import evict_alias, register_client_database

    assert settings.PGBOUNCER_PORT != settings.PG_ADMIN_PORT, (
        "PGBOUNCER_PORT et PG_ADMIN_PORT sont identiques : ce test ne peut pas "
        "distinguer le chemin mutualisé du chemin direct, donc il ne prouve rien."
    )

    reglages = connections["tenant_a"].settings_dict
    alias = "tenant_poole_seuil"
    register_client_database(
        alias=alias,
        name=reglages["NAME"],
        host=settings.PGBOUNCER_HOST,
        port=settings.PGBOUNCER_PORT,
        user=reglages["USER"],
        password=reglages["PASSWORD"] or "",
    )

    try:
        depart = _seuil_observe(alias)
        assert depart != SEUIL_MOT, (
            f"le seuil du serveur vaut déjà {depart!r}, soit la valeur que "
            "`seuil_de_mot` pose. Le test ne pourrait alors distinguer aucune fuite de "
            "l'absence de fuite."
        )

        with seuil_de_mot(alias):
            dedans = _seuil_observe(alias)

        connections[alias].close()
        apres = _seuil_observe(alias)
    finally:
        evict_alias(alias)
        _liberer_le_pool(
            dbname=reglages["NAME"],
            user=reglages["USER"],
            password=reglages["PASSWORD"] or "",
        )

    assert dedans == SEUIL_MOT, (
        f"dans le gestionnaire de contexte, le seuil vaut {dedans!r} et non {SEUIL_MOT!r} "
        "— `seuil_de_mot` ne pose rien, ou le pose sur une autre transaction que celle "
        "que la requête utilisera."
    )
    assert apres == depart, (
        f"après fermeture et réouverture de la connexion, le seuil vaut {apres!r} au lieu "
        f"de {depart!r}. Il a chevauché une connexion serveur du pool : c'est la menace "
        "T-02-02, et la requête suivante — potentiellement celle d'un autre opticien — "
        "s'exécutera avec le seuil de celle-ci. Utiliser "
        "`SELECT set_config(..., true)` dans un `transaction.atomic()`, jamais un `SET` nu."
    )


# ======================================================================================
# Garde de source — par AST, jamais par grep d'un mot nu
# ======================================================================================
#: Un `SET` qui n'est pas un `SET LOCAL`. C'est la forme interdite : mesurée fuyante.
SET_NU = re.compile(r"^\s*SET\s+(?!LOCAL\b)", re.IGNORECASE)

#: `set_config(nom, valeur, false)` — c'est-à-dire un `SET` nu écrit autrement. Le
#: troisième argument `is_local` est le tout : à `false`, le réglage survit à la
#: transaction et rejoint le pool.
SET_CONFIG_GLOBAL = re.compile(
    r"set_config\s*\(\s*[^,()]+,\s*[^,()]+,\s*(?:false|'f'|0)\s*\)", re.IGNORECASE
)


def _texte_litteral(noeud: ast.AST) -> str | None:
    """Le littéral SQL derrière `noeud`, ou `None` si ce n'en est pas un.

    Trois formes, parce que ce dépôt les utilise toutes les trois :
    `"SELECT …"`, `sql.SQL("SELECT …")` et `sql.SQL("SELECT …").format(…)`. Ne pas
    déballer les deux dernières laisserait au `psycopg.sql` du provisionneur un passage
    libre, ce qui ferait de cette garde un théâtre.
    """
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
        return noeud.value
    if isinstance(noeud, ast.Call):
        nom = getattr(noeud.func, "attr", None) or getattr(noeud.func, "id", None)
        if nom == "format" and isinstance(noeud.func, ast.Attribute):
            return _texte_litteral(noeud.func.value)
        if nom in {"SQL", "Composed"} and noeud.args:
            return _texte_litteral(noeud.args[0])
    return None


def reglages_de_session_nus(sources) -> list[str]:
    """Les `.execute(<littéral>)` de `sources` qui posent un réglage de session nu.

    `sources` est une suite de couples `(étiquette, source)`. Rend une liste
    `"étiquette:ligne: extrait"`, vide quand tout va bien.

    **Par AST et sur le premier argument d'un `.execute()`, jamais par grep d'un mot
    nu.** Le piège s'est produit huit fois en phase 3 : un critère qui cherche un mot que
    la prose du dépôt contient aussi. Ici la prose **doit** contenir `SET pg_trgm` — la
    docstring de `domaine/clients/recherche.py` explique précisément pourquoi il est
    interdit, et le commentaire de `docker-compose.yml` aussi. Une docstring n'est jamais
    le premier argument d'un `.execute(...)`, donc la garde ne peut pas attraper sa propre
    explication.
    """
    fautes: list[str] = []
    for etiquette, source in sources:
        arbre = ast.parse(source)
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            if getattr(noeud.func, "attr", None) != "execute":
                continue
            if not noeud.args:
                continue
            texte = _texte_litteral(noeud.args[0])
            if texte is None:
                continue
            if SET_NU.search(texte) or SET_CONFIG_GLOBAL.search(texte):
                fautes.append(f"{etiquette}:{noeud.lineno}: {texte.strip()[:80]}")
    return sorted(fautes)


def _sources_du_depot():
    """Chaque module Python de `plateforme/` et `domaine/`, avec son chemin relatif."""
    for arbre in ARBRES_SCANNES:
        for chemin in sorted((RACINE / arbre).rglob("*.py")):
            if "__pycache__" in chemin.parts:
                continue
            yield str(chemin.relative_to(RACINE)), chemin.read_text(encoding="utf-8")


def test_client10_aucun_reglage_de_session_nu_dans_le_code():
    """Aucun `SET` nu, ni `set_config(..., false)`, dans `plateforme/` ni `domaine/`.

    Un réglage de session posé hors transaction chevauche une connexion serveur du pool
    et atteint la requête suivante, qui peut être celle d'un autre opticien (T-02-02,
    mesuré). La seule forme autorisée est
    `SELECT set_config('…', %s, true)` à l'intérieur d'un `transaction.atomic()` :
    c'est `SET LOCAL`, et contrairement à `SET LOCAL` elle accepte un **paramètre lié**
    — `SET LOCAL x = %s` est une erreur de syntaxe, donc écrire `SET LOCAL` avec une
    valeur variable obligerait à interpoler la chaîne, c'est-à-dire à ouvrir une injection
    SQL dans le chemin qui existe pour être sûr (T-04-01).
    """
    fautes = reglages_de_session_nus(_sources_du_depot())

    assert not fautes, (
        "Réglages de session nus trouvés :\n  " + "\n  ".join(fautes) + "\n\n"
        "Remplacer par, dans un `transaction.atomic(using=alias)` :\n"
        "    cur.execute(\"SELECT set_config('<nom>', %s, true)\", [valeur])"
    )


def test_client10_le_scan_de_source_lit_vraiment_des_fichiers():
    """Un scan qui ne lit rien rend une liste vide, donc passe pour toujours.

    Le même raisonnement que `test_tenant03_the_migration_scan_actually_finds_...` :
    l'assertion ci-dessus n'a de sens que si elle a vu du code.
    """
    lus = dict(_sources_du_depot())

    assert "domaine/clients/recherche.py" in lus, (
        f"le scan n'a pas trouvé recherche.py ; il a vu {sorted(lus)[:5]}…"
    )
    assert len(lus) >= 15, f"le scan n'a lu que {len(lus)} module(s)"


#: Les sources synthétiques, dans l'idiome de `tests/test_migration_conventions.py`. Un
#: détecteur jamais éprouvé sur un cas fautif est un détecteur vert et vide.
SET_NU_DIRECT = textwrap.dedent(
    """
    def poser(cur):
        cur.execute("SET pg_trgm.word_similarity_threshold = 0.3")
    """
)

SET_CONFIG_NON_LOCAL = textwrap.dedent(
    """
    def poser(cur):
        cur.execute("SELECT set_config('pg_trgm.word_similarity_threshold', %s, false)", ["0.3"])
    """
)

SET_NU_PAR_PSYCOPG_SQL = textwrap.dedent(
    """
    from psycopg import sql

    def poser(cur, valeur):
        cur.execute(sql.SQL("SET pg_trgm.word_similarity_threshold = {}").format(valeur))
    """
)

SET_CONFIG_LOCAL = textwrap.dedent(
    """
    def poser(cur):
        cur.execute("SELECT set_config('pg_trgm.word_similarity_threshold', %s, true)", ["0.3"])
    """
)

PROSE_QUI_NOMME_LA_FAUTE = textwrap.dedent(
    '''
    """Ne jamais écrire SET pg_trgm.word_similarity_threshold = 0.3 : mesuré fuyant."""

    SET_INTERDIT = "SET pg_trgm.word_similarity_threshold = 0.3"

    def lire(cur):
        """Un `SET` nu rejoint le pool ; voir SET pg_trgm ci-dessus."""
        cur.execute("SELECT current_setting('pg_trgm.word_similarity_threshold')")
    '''
)


@pytest.mark.parametrize(
    ("etiquette", "source", "fautif"),
    [
        ("set-nu-direct", SET_NU_DIRECT, True),
        ("set-config-non-local", SET_CONFIG_NON_LOCAL, True),
        ("set-nu-par-psycopg-sql", SET_NU_PAR_PSYCOPG_SQL, True),
        ("set-config-local", SET_CONFIG_LOCAL, False),
        ("prose-qui-nomme-la-faute", PROSE_QUI_NOMME_LA_FAUTE, False),
    ],
)
def test_client10_la_garde_de_source_est_prouvee_sur_des_modules_synthetiques(
    etiquette, source, fautif
):
    """La garde dit non aux trois formes interdites, et oui aux deux formes licites.

    Le cinquième cas est celui qui vaut d'être écrit : une docstring, un commentaire et
    une constante nommée contenant tous `SET pg_trgm` — exactement ce que
    `recherche.py` et `docker-compose.yml` contiennent — et **aucune faute**. C'est la
    preuve que la garde ne peut pas attraper sa propre prose, ce qu'un grep de mot nu
    ferait immanquablement.
    """
    fautes = reglages_de_session_nus([(etiquette, source)])

    assert bool(fautes) is fautif, f"{etiquette} : {fautes}"
