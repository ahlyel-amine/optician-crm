"""Consommateur 2 du registre : l'export CSV.

**L'export n'inspecte pas le queryset. Il réutilise le sérialiseur.** C'est tout l'intérêt,
et c'est la seule ligne de ce module qui compte :

    colonnes = list(serializer.child.fields)      # DÉJÀ projetées

Une liste de colonnes écrite à la main produirait une **colonne vide** là où le droit
manque. « Absent d'un export » échouerait alors dans l'esprit : une colonne vide livre
l'existence du champ, sa position, et le fait qu'il est refusé à celui qui regarde — ce qui
est souvent l'information la plus utile à qui cherche. Dérivée des champs projetés, la
colonne n'existe simplement pas.

**Deux choix de format, tous deux révisables, tous deux notés dans le SUMMARY.**

* Le séparateur est `;` et non `,`. Excel en configuration française et marocaine lit le
  séparateur de liste de la locale ; un fichier à virgules s'y ouvre en **une seule
  colonne** (`03-RESEARCH.md` question ouverte 3).
* Le contenu est préfixé d'un **BOM UTF-8**. Sans lui, Excel devine la page de codes de la
  machine et les accents deviennent du mojibake — sur une facture marocaine, cela touche
  la moitié des noms.

Ces deux réglages sont des conventions d'outil, pas des règles métier, et ils ne sont pas
vérifiés contre un vrai Excel : le jour où un opticien ouvre un export et le trouve en une
colonne, c'est ici qu'il faut revenir.

**Hors HTTP.** L'export est piloté par `_PorteurAcces`, l'objet de cinq lignes du plan
03-05 qui porte `.acces` et `.user` sans requête. Deux règles en découlent, et elles
ferment A-03-02 et A-03-03 :

1. **Toute commande de gestion produisant un artefact destiné au client prend
   `--utilisateur`** et construit sa sortie par cette fonction. L'accès non projeté au
   niveau opérateur — `dumpdata` et consorts — est accepté par conception, mais il doit
   être **nommé** comme accès opérateur, jamais obtenu par distraction.
2. **Toute tâche Celery de rendu a la signature `(*, client_id, acting_utilisateur_id,
   ...)`** et recalcule `acces_pour(...)` dans le contexte de locataire lié. Jamais un
   `Acces` ni une instance de modèle en argument — `TenantTask` l'interdit déjà. Sans
   `acting_utilisateur_id`, la tâche sait de quel client mais pas de qui, donc elle rend
   la vue du propriétaire et l'envoie au gérant qui l'a demandée.
   `test_perm06_toute_tache_de_rendu_exige_acting_utilisateur_id` parcourt le registre des
   tâches et refuse les signatures qui manquent.
"""

from __future__ import annotations

import csv
import io

from plateforme.comptes.acces import _PorteurAcces

#: Le séparateur. Voir la docstring du module : `,` ouvre en une seule colonne dans un
#: Excel francophone.
SEPARATEUR = ";"

#: Le préfixe qui dit à Excel que le fichier est en UTF-8, faute de quoi il devine.
BOM_UTF8 = "﻿"

#: CRLF, la fin de ligne que le module `csv` de la bibliothèque standard documente comme
#: celle attendue par les tableurs. Posée explicitement parce que le défaut de
#: `csv.writer` dépend du dialecte et non de la plateforme.
FIN_DE_LIGNE = "\r\n"


def exporter_csv(classe_serializer, queryset, *, acces) -> str:
    """Le CSV des lignes de `queryset`, projeté pour `acces`.

    Renvoie une `str` plutôt que des octets : l'encodage appartient à la réponse HTTP ou au
    fichier écrit, pas à la projection. L'appelant fait `contenu.encode("utf-8")`.
    """
    serializer = classe_serializer(
        queryset, many=True, context={"request": _PorteurAcces(acces=acces)}
    )
    lignes = serializer.data
    colonnes = list(serializer.child.fields)

    tampon = io.StringIO()
    graveur = csv.DictWriter(
        tampon,
        fieldnames=colonnes,
        delimiter=SEPARATEUR,
        lineterminator=FIN_DE_LIGNE,
        # `extrasaction="ignore"` par prudence et non par nécessité : une clé présente
        # dans les données mais absente des colonnes serait un désaccord entre
        # `serializer.data` et `serializer.child.fields`, donc un bug — mais lever ici
        # transformerait ce bug en 500 sur un export, ce qui est le pire endroit pour
        # l'apprendre.
        extrasaction="ignore",
    )
    graveur.writeheader()
    for ligne in lignes:
        graveur.writerow(ligne)
    return BOM_UTF8 + tampon.getvalue()
