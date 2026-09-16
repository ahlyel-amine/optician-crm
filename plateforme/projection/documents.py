"""Consommateur 3 du registre : le document imprimé.

**La phase 3 rend du HTML, pas du PDF.** Aucune dépendance de rendu PDF n'est introduite
ici — ni dans `pyproject.toml`, ni dans ce paquet, et le plan en fait un critère grepable.
La phase 9 possède les documents A4 : elle enveloppera la **même** chaîne dans
`HTML(string=rendre_html(...)).write_pdf()`, avec le moteur nommé dans la table de pile de
CLAUDE.md, sans toucher d'une ligne à la projection. Ce qui est livré maintenant est la
**couture**, pas le document — c'est le plus
petit objet qui rende le critère 4 de la feuille de route vérifiable au lieu de le laisser
dériver jusqu'à la phase 9 (`03-RESEARCH.md` correction 4).

**Le piège du gabarit, fermé explicitement.** Une clé absente d'un contexte de gabarit rend
`string_if_invalid`, qui vaut `""` par défaut. Un champ **caché par la projection** et un
champ **mal orthographié** ont donc exactement la même apparence correcte : pas
d'exception, pas d'avertissement, pas de test rouge. La phase 9 écrira
`{{ ligne.prix_achat }}` dans un gabarit de facture et personne ne le saura.

Ne **pas** corriger cela en changeant `string_if_invalid` globalement : la documentation de
Django avertit que toute valeur non vide y casse `{% if %}` sur les variables optionnelles,
et le réglage est délibérément absent de tous les modules de `config/settings/`. La
correction est structurelle — les gabarits **itèrent une liste de colonnes déclarée et déjà
projetée** et ne nomment aucun champ en ligne. Deux tests la tiennent : l'un lit le source
de chaque gabarit et refuse un `{{ objet.champ }}`, l'autre compte les cellules rendues
contre les champs projetés, parce qu'un gabarit peut très bien itérer une *autre* liste.

Hors HTTP, les deux mêmes règles que pour l'export s'appliquent — commande de gestion avec
`--utilisateur`, tâche Celery avec `acting_utilisateur_id` — et la docstring de
`plateforme/projection/export.py` les énonce en entier plutôt que de les répéter à moitié
ici.
"""

from __future__ import annotations

from django.template.loader import render_to_string

from plateforme.comptes.acces import _PorteurAcces

#: Le gabarit générique. Il ne connaît aucune ressource : il reçoit un titre et une liste
#: de paires `(nom, valeur)`, ce qui est exactement ce qu'une projection peut promettre.
GABARIT_PAR_DEFAUT = "projection/document.html"


def contexte_document(classe_serializer, instance, *, acces, titre="Document") -> dict:
    """Le contexte de gabarit d'une instance, projeté pour `acces`.

    Renvoie trois clés :

    * `titre` — une chaîne fournie par l'appelant, jamais dérivée de la donnée ;
    * `colonnes` — la liste **ordonnée** de paires `(nom, valeur)`, et c'est la seule que
      les gabarits ont le droit de parcourir ;
    * `donnees` — le dictionnaire projeté, pour un gabarit spécialisé de phase 9 qui aurait
      une mise en page et non un tableau. Il reste soumis à la même règle : itérer, jamais
      nommer un champ que la projection pourrait retirer.

    L'ordre de `colonnes` suit `serializer.fields`, donc l'ordre déclaré dans `Meta.fields`.
    Un document dont les colonnes changeraient de place d'un appel à l'autre serait
    illisible à l'impression, et le `dict` de DRF est ordonné par construction.
    """
    serializer = classe_serializer(
        instance, context={"request": _PorteurAcces(acces=acces)}
    )
    donnees = dict(serializer.data)
    colonnes = [(nom, donnees[nom]) for nom in serializer.fields if nom in donnees]
    return {"titre": titre, "colonnes": colonnes, "donnees": donnees}


def rendre_html(nom_template: str, contexte: dict) -> str:
    """Le HTML du document. La phase 9 passera cette chaîne au moteur PDF, sans rien changer."""
    return render_to_string(nom_template, contexte)
