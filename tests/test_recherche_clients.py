"""CLIENT-10 — la recherche tolérante aux translittérations, et ses deux garde-fous.

Ces tests s'adressent au **service** `chercher_clients`, pas à la vue. Trois raisons, et
la troisième est la vraie :

1. la vue est couverte par `tests/test_clients.py`, qui prouve que `?search=` y arrive ;
2. le service est appelable sans HTTP, donc la règle vérifiée ici est celle qu'une
   commande de gestion ou une tâche Celery obtiendra aussi ;
3. **l'isolation ne se teste pas contre un seul locataire**, et lier deux clients dans un
   même test est direct au niveau du service — `tenant_context` d'un côté, `alias=` de
   l'autre — là où il faudrait deux affaires provisionnées au niveau HTTP.

---

## La contradiction que ces tests tranchent, et le sens dans lequel elle a été tranchée

`04-RESEARCH.md` §5.2 mesure `similarity` et conclut que le vrai positif exigé
(`mohammed ↔ mhamed`, 0,333) passe **sous** deux vrais négatifs exigés
(`fatima ↔ fatiha` et `abdelkader ↔ abdelkrim`, 0,400). C'est exact, et c'est **pire**
mesuré sur l'opérateur réellement utilisé. Relevé sur PostgreSQL 18.6 de ce dépôt, en
`word_similarity(requête, cible)` — l'opérateur `<%` / `%>`, pas `%` :

| requête → fiche | `word_similarity` | doit correspondre |
|---|---|---|
| `mhamed` → `mohammed alaoui` | **0,333** | **OUI** |
| `abdelkader` → `abdelkrim bennani` | 0,545 | **NON** |
| `fatima` → `fatiha bennani` | **0,571** | **NON** |
| `abdelkrim` → `abdelkader bennani` | **0,600** | **NON** |
| `mohamed` → `mohammed alaoui` | 0,700 | oui |

**Aucun seuil scalaire ne satisfait les deux premières lignes à la fois.** La conséquence
n'est donc pas « régler le seuil » : c'est que le trigramme ne peut pas porter CLIENT-10
tout seul. Le seuil monte **au-dessus** de 0,600 pour tenir les non-fusions, et c'est la
couche phonétique — `metaphone(nom, 8)` — qui rend `mhamed ↔ mohammed`. C'est exactement
ce que dit le tableau des quatre couches du plan 04-03 : « ce que la couche 2 manque à
tout seuil sûr ».

Si l'un de ces deux tests passe au détriment de l'autre, **c'est la forme qui est fausse,
pas le nombre.**
"""

from __future__ import annotations

import pytest

#: Les deux paires que `04-RESEARCH.md` §5.2 mesure comme devant rester distinctes.
PAIRES_A_NE_PAS_FUSIONNER = [
    ("Fatima Bennani", "Fatiha Bennani"),
    ("Abdelkader Bennani", "Abdelkrim Bennani"),
]


def _noms(resultats) -> set[str]:
    return {fiche.nom for fiche in resultats}


# --------------------------------------------------------------------------------------
# CLIENT-10 — l'exemple littéral de l'exigence, dans les trois sens
# --------------------------------------------------------------------------------------
def test_client10_mohamed_mohammed_mhamed_trouvent_la_meme_personne(db_all):
    """CLIENT-10 — le test que la docstring de `provisioner.py` nomme depuis la phase 2.

    Trois fiches, trois requêtes, et **les trois sens** : une implémentation asymétrique
    — un préfixe posé d'un seul côté, une comparaison phonétique faite sur la requête et
    pas sur la fiche — passerait un seul sens et paraîtrait correcte.

    La quatrième assertion est l'isolation : une homonyme existe chez `tenant_b` et ne
    doit pas apparaître. **La recherche est l'endroit type où un `Q()` mal placé
    traverse**, et la frontière ici est la *connexion*, pas une colonne (T-04-19).

    **Ce qu'il attrape :** le seuil trigramme laissé à sa valeur par défaut, une couche
    phonétique comparant la clé de la requête à l'égalité d'une clé de **nom complet**
    (`MHMT` contre `MHMTL` — jamais égales), ou une couche phonétique tout simplement
    absente.
    """
    from domaine.clients.recherche import chercher_clients
    from plateforme.tenancy.context import tenant_context
    from tests.factories import FicheClientFactory

    attendus = {"Mohamed Alaoui", "Mohammed Alaoui", "Mhamed Alaoui"}

    with tenant_context("tenant_a"):
        for nom in sorted(attendus):
            FicheClientFactory(nom=nom)
    with tenant_context("tenant_b"):
        FicheClientFactory(nom="Mohamed Alaoui")

    for terme in ("mhamed", "mohamed", "mohammed"):
        trouves = _noms(chercher_clients(terme, alias="tenant_a"))
        assert attendus <= trouves, (
            f"« {terme} » ne rend que {sorted(trouves)}. CLIENT-10 exige les trois "
            f"orthographes dans les trois sens ; il manque "
            f"{sorted(attendus - trouves)}."
        )

    chez_b = list(chercher_clients("mhamed", alias="tenant_b"))
    assert len(chez_b) == 1, (
        f"La recherche chez le client B rend {len(chez_b)} fiches et non une seule. "
        "Les fiches du client A ont traversé : la frontière est la connexion, et elle "
        "vient d'être franchie."
    )


@pytest.mark.parametrize("premier,second", PAIRES_A_NE_PAS_FUSIONNER)
def test_client10_deux_prenoms_distincts_ne_fusionnent_pas(db_all, premier, second):
    """CLIENT-10 — les deux paires mesurées qui sont **deux personnes**, pas deux graphies.

    **C'est le test qui interdit de « régler le seuil » pour faire passer le précédent.**
    Les deux paires sont mesurées entre 0,545 et 0,600 en `word_similarity`, donc
    **au-dessus** du 0,333 que `mohammed ↔ mhamed` exige. Le classement est inversé.

    **Ce qu'il attrape :** un seuil relâché. Baisser `SEUIL_MOT` fait passer le test
    précédent par la couche trigramme et rougit celui-ci dans la seconde qui suit —
    ce qui est exactement le signal voulu.
    """
    from domaine.clients.recherche import chercher_clients
    from plateforme.tenancy.context import tenant_context
    from tests.factories import FicheClientFactory

    with tenant_context("tenant_a"):
        FicheClientFactory(nom=premier)
        FicheClientFactory(nom=second)

    prenom = premier.split()[0].lower()
    trouves = _noms(chercher_clients(prenom, alias="tenant_a"))

    assert premier in trouves, (
        f"« {prenom} » ne rend même pas « {premier} ». Le test serait vert pour une "
        "implémentation qui ne rend jamais rien ; cette moitié l'interdit."
    )
    assert second not in trouves, (
        f"« {prenom} » rend « {second} », qui est une autre personne. "
        "AUCUN SEUIL SCALAIRE NE SÉPARE CE TEST DU PRÉCÉDENT : si l'un passe au "
        "détriment de l'autre, c'est la *forme* qui est fausse, pas le nombre. "
        "Le trigramme doit rester au-dessus de 0,600 et la couche phonétique doit "
        "porter « mhamed ↔ mohammed » — voir la docstring de ce module."
    )


def test_client10_une_cle_phonetique_vide_ne_rapproche_rien(db_all):
    """CLIENT-10 / T-04-02 — l'écriture arabe, et la garde des deux côtés.

    `metaphone('محمد', 8)` rend `''` — mesuré au plan 04-01. Une chaîne vide utilisée
    comme critère rapprocherait **chaque** fiche en arabe de toutes les autres : au
    comptoir, la fiche du voisin, avec ses ordonnances. L'index est partiel côté base ;
    la requête doit sauter la couche phonétique quand la clé de la requête est vide.

    **L'assertion jumelle positive est obligatoire.** Sans elle, une implémentation qui
    ne rend jamais rien serait verte, et la garde serait un théâtre.

    **Ce qu'il attrape :** la condition `if cle:` retirée de la couche 3, ou remplacée par
    un `filter(cle_phonetique=cle)` inconditionnel.
    """
    from domaine.clients.recherche import chercher_clients
    from plateforme.tenancy.context import tenant_context
    from tests.factories import FicheClientFactory

    with tenant_context("tenant_a"):
        FicheClientFactory(nom="محمد")
        FicheClientFactory(nom="فاطمة")

    trouves = _noms(chercher_clients("محمد", alias="tenant_a"))

    assert "محمد" in trouves, (
        "Un nom en écriture arabe ne se retrouve pas par lui-même. La couche exacte / "
        "préfixe travaille sur `nom_recherche`, que la normalisation NFKD laisse intact "
        "en arabe — si elle ne rend rien, c'est la normalisation qui a filtré."
    )
    assert "فاطمة" not in trouves, (
        "Chercher « محمد » rend « فاطمة ». Les deux ont une clé phonétique vide, et la "
        "couche 3 les a rapprochées par cette vacuité : chaque fiche en arabe rapproche "
        "alors toutes les autres (T-04-02)."
    )


@pytest.mark.slow
def test_client10_la_recherche_emprunte_l_index_gin(db_all):
    """CLIENT-10 — la couche trigramme est *indexable*, prouvé par `EXPLAIN`.

    **`enable_seqscan = off` est dans le test, jamais dans le produit**, et il y est posé
    en `LOCAL` comme partout ailleurs dans ce dépôt (`SELECT set_config(…, true)` — un
    `SET` nu chevauche une connexion serveur du pooler, T-02-02).

    Ce que le test affirme est que l'index **est utilisable**, pas que le planificateur le
    choisit aujourd'hui : sur un corpus de six cents lignes, un balayage séquentiel est un
    choix légitime et le planificateur a raison de le préférer. Ce qui doit rester vrai est
    qu'un plan par index existe.

    **Ce qu'il attrape :** un index perdu par un `makemigrations` qui le renomme, un
    `trigram_similar` substitué à `trigram_word_similar` — l'opérateur `%` de l'un n'est
    pas servi par `gin_trgm_ops` de la même façon que le `%>` de l'autre — ou une couche 2
    réécrite en `LIKE '%…%'`, qui ne peut pas emprunter cet index.
    """
    from django.db import connections

    from domaine.clients.models import Client
    from domaine.clients.recherche import couche_trigramme, seuil_de_mot
    from plateforme.tenancy.context import tenant_context
    from tests.fixtures.noms_marocains import peupler_corpus

    with tenant_context("tenant_a"):
        ecrites = peupler_corpus(alias="tenant_a")
    assert ecrites == 600, f"le corpus a écrit {ecrites} fiches et non 600"

    requete = couche_trigramme("mhamed", alias="tenant_a")
    sql, parametres = requete.query.get_compiler(using="tenant_a").as_sql()

    with seuil_de_mot("tenant_a"):
        with connections["tenant_a"].cursor() as curseur:
            curseur.execute(f'ANALYZE "{Client._meta.db_table}"')
            curseur.execute("SELECT set_config('enable_seqscan', 'off', true)")
            curseur.execute(f"EXPLAIN {sql}", parametres)
            plan = "\n".join(ligne[0] for ligne in curseur.fetchall())

    assert "Bitmap Index Scan" in plan, (
        f"la couche trigramme ne peut pas emprunter d'index. Plan obtenu :\n{plan}"
    )
    assert "idx_client_nom_trgm" in plan, (
        "le plan n'emprunte pas `idx_client_nom_trgm`, l'index GIN `gin_trgm_ops` posé "
        f"par le plan 04-01. Plan obtenu :\n{plan}"
    )


def test_client10_la_table_d_equivalences_est_amorcee_par_base_client(db_all):
    """CLIENT-10 — la couche 4, et la seule paire que les trois autres ne peuvent pas rendre.

    `khadija` / `khdija` est le cas discriminant, et il est choisi pour cela :

    * couche 1 — ni égalité ni préfixe ;
    * couche 2 — `word_similarity('khdija', 'khadija alaoui')` = 0,500, **sous** le seuil
      de 0,65 qu'il faut tenir pour que Fatima et Fatiha ne fusionnent pas ;
    * couche 3 — `metaphone('khdija', 8)` = `KTJ`, `metaphone('khadija alaoui', 8)`
      commence par `KHTJ` : ni égal, ni préfixe.

    Seule une équivalence curée peut donc rendre cette fiche, et l'amorce est écrite par
    base client dans `seed_new_client`, pas dans le plan de contrôle (CLAUDE.md #11).

    **Ce qu'il attrape :** le point d'extension de `seed_new_client` laissé vide, une
    amorce placée dans une migration — donc absente des clients déjà provisionnés — ou
    une jointure d'équivalence écrite sur la chaîne entière plutôt que sur les jetons.

    **Le contrôle négatif est dans le test, avant l'amorce**, et il n'est pas décoratif :
    ce test a été écrit après son implémentation — seul de ce fichier — et il était donc
    vert à la première exécution. Un test vert d'emblée ne prouve rien tant qu'on ne l'a
    pas vu rouge. La première assertion l'a vu : table vide, la fiche n'est pas rendue.
    """
    from domaine.clients.models import EquivalenceNom
    from domaine.clients.recherche import chercher_clients
    from plateforme.control_plane.seeding import seed_new_client
    from plateforme.tenancy.context import tenant_context
    from tests.factories import ClientFactory, FicheClientFactory

    affaire = ClientFactory()

    with tenant_context("tenant_a"):
        FicheClientFactory(nom="Khadija Alaoui")

    avant = _noms(chercher_clients("khdija", alias="tenant_a"))
    assert "Khadija Alaoui" not in avant, (
        "« khdija » rend « Khadija Alaoui » AVANT toute équivalence. Les couches 1 à 3 "
        "ne le peuvent pas aux valeurs mesurées : soit le seuil trigramme a baissé, soit "
        "la couche phonétique compare autre chose qu'un préfixe de clé — et ce test ne "
        "prouve alors plus rien de la couche 4."
    )

    with tenant_context("tenant_a"):
        seed_new_client(affaire, ["Anfa"])
        # Idempotence : le second appel ne double aucune ligne — c'est la promesse du
        # module, et une amorce est exactement ce qu'une reprise doublerait.
        seed_new_client(affaire, ["Anfa"])
        amorcees = EquivalenceNom.objects.using("tenant_a").count()

    assert amorcees == 57, (
        f"l'amorce a écrit {amorcees} lignes et non 57 — soit la liste a changé, soit "
        "le second appel a doublé des lignes malgré `get_or_create`."
    )

    apres = _noms(chercher_clients("khdija", alias="tenant_a"))
    assert "Khadija Alaoui" in apres, (
        "« khdija » ne rend pas « Khadija Alaoui ». Aucune des trois premières couches "
        "ne le peut : c'est la couche 4 qui manque, ou son amorce."
    )
