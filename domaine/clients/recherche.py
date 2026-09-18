"""CLIENT-10 — les primitives de recherche : normaliser, coder, et poser le seuil.

Quatre fonctions, trois pures et une impure, plus deux constantes qui portent un résultat
mesuré et non un réglage. Tout ce que la phase 4 cherche par un nom passe par ici, et
l'unicité du passage est le point : `04-RESEARCH.md` §5.3 note que changer la règle de
normalisation exigera un `RunPython` de reprise sur les colonnes dérivées, et ce
`RunPython` sera un appel à `normaliser_pour_recherche` plutôt qu'une réécriture — à
condition que la règle n'existe qu'ici.

**Le trigramme est un moyen de rappel et de classement, jamais un filtre.** Mesuré : la
paire exigée par CLIENT-10, `mohammed ↔ mhamed`, vaut 0,333 et passe **sous** deux vrais
négatifs à 0,400 (`fatima ↔ fatiha`, `abdelkader ↔ abdelkrim`). Le classement est inversé,
donc aucun seuil scalaire ne sépare la vérité de l'erreur. Rien dans cette phase ne doit
auto-sélectionner ni fusionner : un faux positif au comptoir, c'est la fiche du voisin,
ordonnances comprises — une divulgation de donnée de santé, pas une gêne d'ergonomie.

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

from django.db import connections, transaction

#: La longueur du code metaphone. **Porteuse du résultat, pas un réglage.**
#:
#: Mesuré : à 4, `metaphone('abdelkader', 4)` et `metaphone('abdelkrim', 4)` rendent tous
#: deux `ABTL` — deux personnes différentes fondues en une clé. À 8 ils se séparent
#: (`ABTLKTR` / `ABTLKRM`) tandis que `{Mhamed, Mohamed, Mohammed, Mouhamed}` restent
#: groupés sur `MHMT`, ce qui est exactement l'énoncé de CLIENT-10. Baisser ce nombre
#: n'accélère rien et rapproche des inconnus.
LONGUEUR_CODE_PHONETIQUE = 8

#: Le seuil de l'opérateur `<%`, en chaîne parce que `set_config` prend du texte.
#:
#: C'est `pg_trgm.word_similarity_threshold` qu'il gouverne, et non
#: `pg_trgm.similarity_threshold` : les deux GUC sont distincts et leurs défauts
#: diffèrent. Mesuré sur PostgreSQL 18.6 de ce dépôt : `similarity_threshold` vaut 0.3 par
#: défaut, `word_similarity_threshold` vaut **0.6**, et à 0.6 l'opérateur `<%` ne rend même
#: pas *Mohamed* pour la requête « mhamed ». Il faut donc le poser explicitement.
#: 0,3 vient de `word_similarity('mhamed', 'mohammed alaoui') = 0.333`.
SEUIL_MOT = "0.3"

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
