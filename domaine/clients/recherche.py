"""CLIENT-10 — les primitives de recherche : normaliser, coder, et poser le seuil.

Quatre fonctions, trois pures et une impure, plus deux constantes qui portent un résultat
mesuré et non un réglage. Tout ce que la phase 4 cherche par un nom passe par ici, et
l'unicité du passage est le point : `04-RESEARCH.md` §5.3 note que changer la règle de
normalisation exigera un `RunPython` de reprise sur les colonnes dérivées, et ce
`RunPython` sera un appel à `normaliser_pour_recherche` plutôt qu'une réécriture — à
condition que la règle n'existe qu'ici.

**Le trigramme est un moyen de rappel et de classement, jamais un filtre.** Mesuré : la
paire exigée par CLIENT-10, `mohammed ↔ mhamed`, vaut 0,333 et passe **sous** deux vrais
négatifs (`fatima ↔ fatiha`, `abdelkader ↔ abdelkrim`) — 0,400 en `similarity`, et
0,545 à 0,600 en `word_similarity`, qui est l'opérateur réellement employé. Le classement
est inversé dans les deux métriques, donc aucun seuil scalaire ne sépare la vérité de
l'erreur. Rien dans cette phase ne doit auto-sélectionner ni fusionner : un faux positif au
comptoir, c'est la fiche du voisin, ordonnances comprises — une divulgation de donnée de
santé, pas une gêne d'ergonomie.

La conséquence pratique est écrite à côté de `SEUIL_MOT` : le seuil du trigramme **monte**
au-dessus des vrais négatifs, et c'est `couche_phonetique` qui rend `mhamed ↔ mohammed`.

**Pourquoi il n'y a pas de `SET pg_trgm.word_similarity_threshold` dans ce fichier.**
Un `SET` nu a été **observé** chevauchant une connexion serveur de PgBouncer et
réapparaissant sur une connexion cliente neuve — reproduit pendant l'exécution de ce
plan : seuil par défaut 0,6, puis `SET … = 0.91`, puis nouvelle connexion cliente, qui lit
0,91. C'est la menace T-02-02, et sous une base par client la connexion suivante peut être
celle d'un autre opticien. `seuil_de_mot` ci-dessous est la seule forme autorisée, et
`test_client10_aucun_reglage_de_session_nu_dans_le_code` refuse toute autre, par AST.
"""

from __future__ import annotations

import re
import unicodedata
from contextlib import contextmanager

from django.contrib.postgres.search import TrigramSimilarity, TrigramWordSimilarity
from django.db import connections, transaction
from django.db.models import Q

#: La longueur du code metaphone. **Porteuse du résultat, pas un réglage.**
#:
#: Mesuré : à 4, `metaphone('abdelkader', 4)` et `metaphone('abdelkrim', 4)` rendent tous
#: deux `ABTL` — deux personnes différentes fondues en une clé. À 8 ils se séparent
#: (`ABTLKTR` / `ABTLKRM`) tandis que `{Mhamed, Mohamed, Mohammed, Mouhamed}` restent
#: groupés sur `MHMT`, ce qui est exactement l'énoncé de CLIENT-10. Baisser ce nombre
#: n'accélère rien et rapproche des inconnus.
LONGUEUR_CODE_PHONETIQUE = 8

#: Le seuil de l'opérateur `<%` / `%>`, en chaîne parce que `set_config` prend du texte.
#:
#: C'est `pg_trgm.word_similarity_threshold` qu'il gouverne, et non
#: `pg_trgm.similarity_threshold` : les deux GUC sont distincts et leurs défauts diffèrent.
#: Mesuré sur PostgreSQL 18.6 de ce dépôt : `similarity_threshold` = 0.3,
#: **`word_similarity_threshold` = 0.6**, `strict_word_similarity_threshold` = 0.5.
#:
#: **0,65, et il MONTE au-dessus du défaut plutôt qu'il ne descende.** La valeur écrite ici
#: au plan 04-01 était 0,3, sur l'hypothèse que la couche trigramme devait à elle seule
#: rendre `mhamed ↔ mohammed` (0,333). Le plan 04-03 a mesuré la conséquence de cette
#: hypothèse et elle est fausse dans l'autre sens. Relevé, en
#: `word_similarity(requête, fiche)` :
#:
#: | requête → fiche | valeur | doit correspondre |
#: |---|---|---|
#: | `mhamed` → `mohammed alaoui` | **0,333** | **OUI — CLIENT-10** |
#: | `mohamed` → `hamed alaoui` | 0,500 | non |
#: | `abdelkader` → `abdelkrim bennani` | 0,545 | **NON — deux personnes** |
#: | `fatima` → `fatiha bennani` | **0,571** | **NON — deux personnes** |
#: | `abdelkrim` → `abdelkader bennani` | **0,600** | **NON — deux personnes** |
#: | `youssef` → `yousef alaoui` | 0,667 | oui |
#: | `mohamed` → `mohammed alaoui` | 0,700 | oui |
#:
#: À 0,3, les deux paires de personnes distinctes fusionnent et
#: `test_client10_deux_prenoms_distincts_ne_fusionnent_pas` est rouge. Aucun seuil n'admet
#: 0,333 en excluant 0,600 : **le trigramme ne peut pas porter CLIENT-10**, et c'est la
#: couche phonétique qui le porte (§5.5, et le tableau des quatre couches du plan 04-03,
#: qui dit déjà « ce que la couche 2 manque à tout seuil sûr »).
#:
#: Pourquoi 0,65 et non le défaut 0,6 : **l'opérateur compare avec `>=`, pas avec `>`** —
#: mesuré, `'abdelkader bennani' %> 'abdelkrim'` rend `true` exactement au défaut, parce
#: que la paire vaut 0,600 pile. Le défaut est donc sur le fil du rasoir du mauvais côté.
#: 0,65 laisse une marge et conserve `mohamed ↔ mohammed` (0,700).
#:
#: **Elle doit rester différente du défaut**, et pas seulement pour la marge :
#: `test_client10_le_seuil_de_mot_ne_fuit_pas_vers_une_connexion_fraiche` affirme
#: `depart != SEUIL_MOT` avant de mesurer la fuite. Poser ici la valeur par défaut rendrait
#: ce test incapable de distinguer une fuite d'une absence de réglage.
SEUIL_MOT = "0.65"

#: Tout ce qui n'est pas un chiffre, pour `normaliser_telephone`.
_NON_CHIFFRES = re.compile(r"\D")


def normaliser_pour_recherche(valeur: str) -> str:
    """NFKD, retrait des diacritiques combinantes, casefold, espaces repliés.

    C'est le remplacement de l'extension `unaccent`, et il est meilleur pour une raison
    précise : `unaccent` est `STABLE`, donc PostgreSQL refuse de l'indexer (`42P17`),
    colonne générée comprise. Cette fonction-ci est immuable par construction, parce
    qu'elle est appliquée **à l'écriture** et que la colonne indexée contient son
    résultat.

    **Elle ne retire ni ponctuation ni trait d'union.** `"El-Hassan"` reste
    `"el-hassan"` : un trait d'union n'est pas un accent, et rapprocher `elhassan` de
    `el hassan` est le travail de la couche qui **mesure** — le trigramme — pas de celle
    qui normalise. Un normaliseur qui déciderait à la place de la mesure rendrait la
    mesure inaudible et le réglage du seuil arbitraire.

    L'écriture arabe traverse intacte : NFKD ne la décompose pas utilement et elle n'a pas
    de casse. BRAND-05 anticipe des noms de clients en arabe, et un filtre « ASCII
    seulement » les viderait tous vers la même chaîne.

    Le coût honnête : changer cette règle demandera un `RunPython` de reprise sur
    `Client.nom_recherche` et `Client.cle_phonetique`. C'est précisément pourquoi elle est
    une fonction nommée — la reprise l'appellera.
    """
    decompose = unicodedata.normalize("NFKD", valeur or "")
    sans_diacritiques = "".join(c for c in decompose if not unicodedata.combining(c))
    return " ".join(sans_diacritiques.casefold().split())


def normaliser_telephone(valeur: str) -> str:
    """Les chiffres seuls, le `+` de tête conservé. **Jamais de refus.**

    Un numéro marocain s'écrit `06 12 34 56 78`, `0612345678`, `+212 6 12 34 56 78` ou
    `06-12-34-56-78` selon qui le note, et c'est la même personne. La colonne dérivée
    porte la forme comparable ; la colonne saisie garde ce que l'opticien a tapé.

    Cette fonction **ne valide pas** et ne normalise pas l'indicatif : on stocke ce qu'on
    lit. Refuser ici transformerait une recherche en formulaire de saisie, et convertir
    `+212 6…` en `06…` serait une décision de pays prise dans un utilitaire de chaîne.
    """
    valeur = (valeur or "").strip()
    prefixe = "+" if valeur.startswith("+") else ""
    return prefixe + _NON_CHIFFRES.sub("", valeur)


def cle_phonetique(valeur: str, *, alias: str) -> str:
    """`metaphone(valeur, 8)`, calculé par la base. **La seule fonction impure du module.**

    L'aller-retour est délibéré : `metaphone` vit dans `fuzzystrmatch` et aucune
    implémentation Python n'en est l'équivalent exact. Une réimplémentation serait une
    **seconde** définition de la clé, et elle dériverait de celle que l'index contient —
    donc une recherche qui ne trouve pas ce que la colonne dit. Le coût est une requête
    par écriture de fiche ; les écritures de fiche sont rares et les lectures, qui sont
    chaudes, n'en font aucune (menace T-04-06, acceptée).

    **Rend `""` en écriture arabe**, parce que c'est ce que `metaphone` rend là (mesuré :
    `metaphone('محمد', 8)` = `''`). La chaîne vide, pas `None` : la colonne dérivée doit
    rester comparable. Et une clé vide ne doit **jamais** servir de critère — sinon chaque
    fiche en arabe rapprocherait toutes les autres. La garde vit à trois endroits : ici
    (la valeur), dans l'index partiel `WHERE cle_phonetique <> ''` du modèle, et dans la
    requête du plan 04-03 qui saute la branche phonétique quand la clé de la requête est
    vide.
    """
    valeur = (valeur or "").strip()
    if not valeur:
        return ""
    with connections[alias].cursor() as cur:
        cur.execute("SELECT metaphone(%s, %s)", [valeur, LONGUEUR_CODE_PHONETIQUE])
        code = cur.fetchone()[0]
    return code or ""


@contextmanager
def seuil_de_mot(alias: str):
    """Le seuil de `<%`, posé pour **LA** transaction et pour rien de plus.

    Deux détails portent tout le sens de ce bloc de six lignes.

    **`SELECT set_config(nom, valeur, true)` et non `SET LOCAL nom = %s`.** `SET`
    n'accepte pas de paramètre lié : `SET LOCAL x = %s` est une erreur de syntaxe, donc la
    seule façon d'écrire `SET LOCAL` avec une valeur variable est l'interpolation de
    chaîne — c'est-à-dire une injection SQL dans le chemin qui existe précisément pour
    être sûr (menace T-04-01). `set_config(nom, valeur, is_local => true)` **est**
    `SET LOCAL`, et il est paramétrable. C'est la discipline `psycopg.sql` de
    `provisioner.py`, appliquée ici.

    **Le `true` final est le tout.** À `false`, c'est un `SET` nu, et le `SET` nu a été
    observé chevauchant une connexion serveur du pool jusqu'à la requête suivante
    (T-02-02). `transaction.atomic()` n'est pas décoratif non plus : hors d'un bloc de
    transaction, PostgreSQL avertit que `SET LOCAL` ne fait rien, et sous l'autocommit de
    Django chaque instruction est sa propre transaction — le seuil serait perdu avant la
    requête qu'il devait gouverner.
    """
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cur:
            cur.execute(
                "SELECT set_config('pg_trgm.word_similarity_threshold', %s, true)",
                [SEUIL_MOT],
            )
        yield


# ======================================================================================
# Le service de recherche — quatre couches de rappel, unies, classées, plafonnées
# ======================================================================================

#: Le nombre de candidats rendus. Vingt, parce que c'est une liste qu'une personne
#: parcourt des yeux, pas un jeu de résultats qu'on pagine.
LIMITE_PAR_DEFAUT = 20

#: En dessous, on n'interroge pas. C'est déjà le contrat de la palette (`03` §5.5), et
#: c'est aussi la borne du déni de service par terme très court (T-04-18) : `a` rapproche
#: la moitié de la table par trigramme.
LONGUEUR_MINIMALE_DU_TERME = 2

#: La longueur minimale d'une clé phonétique pour que la couche 3 s'applique.
#:
#: La couche 3 compare par **préfixe** (voir `couche_phonetique`), donc une clé de deux
#: caractères — `metaphone('ali', 8)` rend `AL` — rapprocherait tout nom commençant par
#: ce son. Trois est la longueur en dessous de laquelle un préfixe cesse d'être un
#: indice.
LONGUEUR_MINIMALE_DE_LA_CLE = 3

#: Les chiffres qu'il faut avoir tapés pour que la couche téléphone s'applique. Sous
#: quatre, `06` rapprocherait tous les numéros marocains.
CHIFFRES_MINIMAUX_DU_TELEPHONE = 4

#: Le plafond de chaque couche **avant** classement. Une couche qui rapporterait dix mille
#: identifiants ferait du classement le point chaud, pour un résultat dont on ne rendra
#: que vingt lignes. Le prix est qu'au-delà de ce plafond le rappel d'une couche est
#: tronqué par ordre alphabétique et non par pertinence ; c'est assumé et borné.
PLAFOND_PAR_COUCHE = 200

#: Les cinq raisons qu'un résultat peut porter. **Rendues dans la charge utile**, pour que
#: l'interface puisse dire *pourquoi* une ligne est là — « proche de « mhamed » » plutôt
#: qu'un score, qui ne dit rien à un opticien (`04-UI-SPEC.md` §18.4).
RAISON_EXACT = "exact"
RAISON_TELEPHONE = "telephone"
RAISON_ORTHOGRAPHE = "orthographe"
RAISON_PHONETIQUE = "phonetique"
RAISON_EQUIVALENCE = "equivalence"

#: L'ordre de priorité quand plusieurs couches rapportent la même fiche. La première
#: gagne, donc une fiche trouvée à la fois par son nom exact et par équivalence est dite
#: « exact » — la raison rendue est la plus forte, pas la dernière calculée.
RAISONS = (
    RAISON_EXACT,
    RAISON_TELEPHONE,
    RAISON_ORTHOGRAPHE,
    RAISON_PHONETIQUE,
    RAISON_EQUIVALENCE,
)

#: Les deux couches qui méritent une prime au classement : une égalité de nom et une
#: correspondance de téléphone ne sont pas des ressemblances, ce sont des certitudes.
_RAISONS_PRIMEES = frozenset({RAISON_EXACT, RAISON_TELEPHONE})

#: La valeur de la prime. Un point plein, donc strictement au-dessus de tout score de
#: similarité, qui vit dans [0, 1] : une certitude ne se classe jamais sous une
#: ressemblance, quel que soit le corpus.
_PRIME = 1.0


def _fiches(alias: str):
    """Le gestionnaire de `Client` **lié explicitement** à `alias`.

    `using(alias)` et non le routeur implicite, alors même que les deux résolvent vers la
    même connexion en requête HTTP. La raison est `seuil_de_mot` : il pose
    `pg_trgm.word_similarity_threshold` sur **une** transaction, celle d'`alias`. Si la
    requête partait sur une autre connexion, le seuil s'appliquerait à une transaction
    vide et la recherche s'exécuterait au défaut — donc `mohammed` ne rendrait pas
    *Mhamed* et rien ne le signalerait. Un alias unique, nommé une fois, rend cette
    divergence impossible plutôt qu'improbable.
    """
    from domaine.clients.models import Client

    return Client.objects.using(alias)


def couche_trigramme(terme: str, *, alias: str):
    """Couche 2 — l'orthographe qui dérive. Rend un queryset d'identifiants.

    Fonction nommée, et pas une ligne au milieu de `chercher_clients`, parce que
    `test_client10_la_recherche_emprunte_l_index_gin` en fait l'`EXPLAIN` : un test qui
    reconstruirait la requête à sa façon prouverait qu'un index sert *sa* requête, pas
    celle du produit.

    **`trigram_word_similar` et non `trigram_similar`**, et ce n'est pas au choix.
    `similarity('mohammed alaoui', 'mhamed')` est diluée par le nom de famille que
    l'utilisateur n'a pas tapé ; `word_similarity` note la requête contre la **meilleure
    étendue** de la cible, donc une requête d'un jeton n'est pas punie pour les jetons
    qu'elle omet. Le lookup compile vers `%>`, qui est servi par l'index GIN
    `gin_trgm_ops` du plan 04-01 — mesuré, 4,3 ms sur 20 400 lignes.

    Le seuil consulté est `pg_trgm.word_similarity_threshold` : **l'appelant doit être
    dans un `seuil_de_mot(alias)`**, sans quoi la requête s'exécute au défaut 0,6 et
    fusionne Abdelkader avec Abdelkrim. Voir `SEUIL_MOT`.

    **`order_by()` vide, et il est load-bearing.** `Client.Meta.ordering = ["nom"]`
    attache un `ORDER BY nom` à toute requête sur ce modèle. Mesuré : avec ce tri, et
    même sous `enable_seqscan = off`, le planificateur choisit
    `Index Scan using idx_client_nom` — qui lui donne l'ordre gratuitement — et réduit
    `%>` à un simple `Filter`. **L'index GIN n'est alors jamais consulté.** Le tri de
    présentation est posé une seule fois, à la fin de `chercher_clients`, sur les vingt
    lignes retenues ; il n'a rien à faire sur une requête de rappel.
    """
    jeton = normaliser_pour_recherche(terme)
    return (
        _fiches(alias)
        .filter(nom_recherche__trigram_word_similar=jeton)
        .order_by()
        .values_list("pk", flat=True)
    )


def couche_phonetique(cle: str, *, alias: str):
    """Couche 3 — `metaphone(·, 8)`, comparé par **préfixe**. Rend un queryset d'identifiants.

    **Préfixe et non égalité, et c'est la mesure qui l'impose.** La colonne
    `cle_phonetique` porte le code du **nom complet** :
    `metaphone('mohammed alaoui', 8)` = `MHMTL`, comme `metaphone('mhamed alaoui', 8)`.
    La requête, elle, est un prénom : `metaphone('mhamed', 8)` = `MHMT`. Une comparaison
    par égalité ne rendrait donc **rien** pour l'exemple littéral de CLIENT-10, alors même
    que la clé est correcte des deux côtés. `MHMT` est le préfixe de `MHMTL` ; c'est la
    relation qui existe entre « le prénom tapé » et « le nom complet enregistré ».

    Les deux vrais négatifs restent séparés sous cette forme, vérifié :
    `metaphone('fatima', 8)` = `FTM` n'est pas un préfixe de `FTHBNN` (Fatiha Bennani), et
    `metaphone('abdelkader', 8)` = `ABTLKTR` n'est pas un préfixe de `ABTLKRMB`.

    **Le coût honnête :** un `LIKE 'MHMT%'` sous la collation ICU `fr-FR` de la base
    n'emprunte pas `idx_client_phonetique`, qui est un btree de collation par défaut. La
    couche 3 balaie donc. C'est borné par `PLAFOND_PAR_COUCHE` et noté comme différé : un
    index `text_pattern_ops` le réglerait, et il n'est pas posé ici parce que la mesure
    qui le justifierait n'existe pas encore.

    L'appelant garantit `cle != ""` — voir `chercher_clients`.

    `order_by()` vide pour la même raison que `couche_trigramme` : le tri par défaut du
    modèle détourne le planificateur d'un index de filtrage vers un index de tri.
    """
    return (
        _fiches(alias)
        .filter(cle_phonetique__startswith=cle)
        .order_by()
        .values_list("pk", flat=True)
    )


def formes_equivalentes(jeton: str, *, alias: str) -> frozenset[str]:
    """Les autres membres des groupes d'équivalence auxquels les jetons de `jeton` appartiennent.

    Le terme est découpé, parce qu'un opticien tape « mhamed alaoui » aussi souvent que
    « mhamed » et que l'équivalence porte sur un prénom, pas sur une chaîne complète.

    Les jetons de la requête sont **retirés** du résultat : les couches 1 et 2 les
    couvrent déjà, et une fiche trouvée par son propre jeton ne doit pas être étiquetée
    « equivalence ».
    """
    from domaine.clients.models import EquivalenceNom

    jetons = [
        morceau
        for morceau in jeton.split()
        if len(morceau) >= LONGUEUR_MINIMALE_DU_TERME
    ][:4]
    if not jetons:
        return frozenset()

    table = EquivalenceNom.objects.using(alias)
    groupes = set(
        table.filter(forme_normalisee__in=jetons).values_list("groupe", flat=True)
    )
    if not groupes:
        return frozenset()

    formes = set(
        table.filter(groupe__in=sorted(groupes)).values_list(
            "forme_normalisee", flat=True
        )
    )
    return frozenset((formes | groupes) - set(jetons))


def _condition_de_jeton(formes) -> Q:
    """Un `Q` vrai quand `nom_recherche` contient l'une de `formes` **comme mot entier**.

    Quatre formes littérales plutôt qu'une expression régulière, et c'est délibéré : un
    `__regex` construit à partir de valeurs lues en base fait entrer une syntaxe dans un
    chemin qui n'a besoin que d'égalité, et les quatre cas — le nom entier, le début, la
    fin, le milieu — couvrent exactement la notion de mot dans une chaîne déjà normalisée
    à un seul espace séparateur.
    """
    from django.db.models import Q

    condition = Q(pk__in=[])
    for forme in sorted(formes):
        condition |= (
            Q(nom_recherche=forme)
            | Q(nom_recherche__startswith=f"{forme} ")
            | Q(nom_recherche__endswith=f" {forme}")
            | Q(nom_recherche__contains=f" {forme} ")
        )
    return condition


def _expression_de_score(jeton: str, identifiants_primes):
    """`GREATEST(similarity, word_similarity)`, plus une prime aux certitudes.

    Construite par un appel plutôt que posée en constante : une expression Django se
    résout contre une requête, et réutiliser le même objet dans deux querysets est un
    piège qu'il est moins cher d'éviter que de vérifier.

    Ni `similarity` ni `word_similarity` ne consultent de GUC — seuls les **opérateurs**
    le font. Le score est donc calculable hors de `seuil_de_mot`, ce dont dépend le fait
    que `chercher_clients` puisse rendre un queryset paresseux.
    """
    from django.db.models import Case, ExpressionWrapper, FloatField, Value, When
    from django.db.models.functions import Greatest

    return ExpressionWrapper(
        Greatest(
            TrigramSimilarity("nom_recherche", jeton),
            TrigramWordSimilarity(jeton, "nom_recherche"),
        )
        + Case(
            When(pk__in=sorted(identifiants_primes), then=Value(_PRIME)),
            default=Value(0.0),
            output_field=FloatField(),
        ),
        output_field=FloatField(),
    )


def chercher_clients(terme: str, *, alias: str, limite: int = LIMITE_PAR_DEFAUT):
    """Les candidats pour `terme`, classés, plafonnés. **Jamais « le » client.**

    ## La garantie, et elle est de sécurité, pas d'ergonomie

    **Le trigramme est un moyen de rappel et de classement, jamais un filtre de
    précision.** Aucun appelant ne doit auto-sélectionner, auto-fusionner, ni traiter un
    unique résultat bien classé comme « le client ». Un faux positif au comptoir est la
    fiche du voisin — et avec des ordonnances dessus, c'est une divulgation de donnée de
    santé, pas une gêne d'interface (T-04-13). La même phrase part dans la `description`
    OpenAPI de la route, donc dans la documentation que lira le client mobile de la
    phase 11.

    ## Les quatre couches

    | Couche | Mécanisme | Ce qu'elle attrape |
    |---|---|---|
    | 1 | égalité / préfixe sur `nom_recherche` **et** sur `telephone_normalise` | les 90 % de cas, et le « retrouver par téléphone » de CLIENT-01 |
    | 2 | `trigram_word_similar`, index GIN `gin_trgm_ops` | l'orthographe qui dérive, les accents, une lettre |
    | 3 | préfixe de `metaphone(·, 8)`, des deux côtés `<> ''` | `mhamed ↔ mohammed`, que la couche 2 manque à tout seuil sûr |
    | 4 | appartenance à un `EquivalenceNom.groupe` | ce que les trois premières manquent encore |

    Les couches sont **unies**, pas enchaînées : une fiche rapportée par une seule d'entre
    elles est un candidat. La première couche qui la rapporte lui donne sa `raison`.

    ## La garde de la clé vide, moitié requête

    `metaphone` rend `''` en écriture arabe. L'index est partiel (`WHERE cle_phonetique
    <> ''`, plan 04-01) ; ici la couche 3 est **entièrement sautée** quand la clé du terme
    est vide ou trop courte. Une clé vide servant de critère rapprocherait chaque fiche
    arabe de toutes les autres (T-04-02).

    ## Ce que rend la fonction

    Un `QuerySet` d'au plus `limite` fiches, annoté de `score` (flottant) et de `raison`
    (l'une de `RAISONS`), ordonné par score décroissant puis par nom. Un queryset et non
    une liste, pour que les backends de filtre de la vue — l'allowlist de paramètres de
    `plateforme/projection/filtres.py` — restent dans le chemin : une liste les
    court-circuiterait et rouvrirait l'oracle de paramètres (T-04-16).

    Le classement est fait **dans** `seuil_de_mot`, le queryset rendu est évalué **après**.
    C'est correct parce qu'il filtre sur des clés primaires déjà arrêtées et que les
    fonctions de score ne consultent aucun GUC.
    """
    base = _fiches(alias)
    terme = (terme or "").strip()
    if len(terme) < LONGUEUR_MINIMALE_DU_TERME:
        return base.none()

    from django.db.models import Case, CharField, Q, Value, When

    jeton = normaliser_pour_recherche(terme)
    chiffres = normaliser_telephone(terme).lstrip("+")

    raison_par_identifiant: dict[int, str] = {}

    def _retenir(identifiants, raison: str) -> None:
        for identifiant in identifiants:
            raison_par_identifiant.setdefault(identifiant, raison)

    def _plafonner(queryset):
        """Borner une couche de rappel, **sans lui imposer de tri**.

        L'ordre de la troncature est donc non spécifié, et c'est un choix mesuré : un
        `ORDER BY nom` rendrait la coupe déterministe et ferait choisir au planificateur
        `idx_client_nom` — qui sert le tri — plutôt que `idx_client_nom_trgm`, qui sert
        le filtre. L'index que toute la couche 2 existe pour emprunter serait alors
        inutilisé sur chaque recherche. Au-delà du plafond, la coupe est arbitraire ;
        en deçà, elle n'a lieu nulle part, et c'est le cas normal.
        """
        return list(queryset.order_by()[:PLAFOND_PAR_COUCHE])

    with seuil_de_mot(alias):
        # Couche 1a — le nom, à l'identique ou en préfixe.
        _retenir(
            _plafonner(
                base.filter(
                    Q(nom_recherche=jeton) | Q(nom_recherche__startswith=jeton)
                ).values_list("pk", flat=True)
            ),
            RAISON_EXACT,
        )

        # Couche 1b — le téléphone, sous sa forme normalisée des deux côtés. `contains`
        # et non `startswith` : un opticien qui lit « …56 78 » sur un écran tape la fin
        # du numéro aussi volontiers que son début.
        if len(chiffres) >= CHIFFRES_MINIMAUX_DU_TELEPHONE:
            _retenir(
                _plafonner(
                    base.filter(telephone_normalise__contains=chiffres).values_list(
                        "pk", flat=True
                    )
                ),
                RAISON_TELEPHONE,
            )

        # Couche 2 — le trigramme.
        _retenir(_plafonner(couche_trigramme(terme, alias=alias)), RAISON_ORTHOGRAPHE)

        # Couche 3 — la phonétique, sautée sur une clé vide ou trop courte.
        cle = cle_phonetique(jeton, alias=alias)
        if len(cle) >= LONGUEUR_MINIMALE_DE_LA_CLE:
            _retenir(
                _plafonner(couche_phonetique(cle, alias=alias)), RAISON_PHONETIQUE
            )

        # Couche 4 — les équivalences amorcées, ou ajoutées par l'opticien.
        formes = formes_equivalentes(jeton, alias=alias)
        if formes:
            _retenir(
                _plafonner(
                    base.filter(_condition_de_jeton(formes)).values_list(
                        "pk", flat=True
                    )
                ),
                RAISON_EQUIVALENCE,
            )

        if not raison_par_identifiant:
            return base.none()

        primes = [
            identifiant
            for identifiant, raison in raison_par_identifiant.items()
            if raison in _RAISONS_PRIMEES
        ]
        classement = list(
            base.filter(pk__in=sorted(raison_par_identifiant))
            .annotate(score=_expression_de_score(jeton, primes))
            .order_by("-score", "nom", "pk")
            .values_list("pk", flat=True)[:limite]
        )

    return (
        base.filter(pk__in=classement)
        .annotate(
            score=_expression_de_score(jeton, primes),
            raison=Case(
                *[
                    When(pk=identifiant, then=Value(raison_par_identifiant[identifiant]))
                    for identifiant in classement
                ],
                default=Value(RAISON_ORTHOGRAPHE),
                output_field=CharField(),
            ),
        )
        .order_by("-score", "nom", "pk")
    )
