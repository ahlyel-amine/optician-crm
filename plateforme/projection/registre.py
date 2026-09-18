"""Le registre : la source unique de la visibilité champ par champ. PERM-06.

**Clé par champ de modèle, jamais par classe de sérialiseur.** C'est ce qui fait qu'un
champ protégé le reste partout où il est sérialisé, y compris imbriqué dans la ressource
d'un autre sérialiseur — qui est précisément la route par laquelle ce genre de chose fuit
normalement (`03-RESEARCH.md` A-03-08). `ArticleSerializer` est sûr tout seul ; la phase 6
l'imbriquera dans `LigneVenteSerializer`, et une protection attachée à la classe
disparaîtrait à ce moment-là sans que rien ne change dans ce fichier.

**Quatre consommateurs lisent ce registre, et un seul test les garde ensemble.**

| Consommateur | Module | Ce qu'un champ interdit y devient |
|---|---|---|
| l'API JSON | `serializers.py` | une clé absente de la charge utile |
| l'export | `export.py` | **aucune** colonne, et non une colonne vide |
| le document | `documents.py` | aucune valeur dans le HTML rendu |
| le schéma OpenAPI | `schema.py` | un champ jamais `required`, donc un type TS honnête |

Ce qui empêche ces quatre-là de diverger d'ici la phase 9 n'est pas l'abstraction, c'est
`test_perm06_champ_protege_absent_de_lapi_de_lexport_et_du_document`, paramétré registre ×
rendus. Une ligne ajoutée ci-dessous produit trois assertions ; un rendu ajouté sans lire
le registre échoue dès qu'il rejoint la liste `RENDUS` du test.

**L'admission qui va avec.** Tout cela est écrit en Python et il n'existe aucune couche en
dessous : tous les utilisateurs d'un client partagent un seul rôle PostgreSQL, donc la base
ne sait pas distinguer le propriétaire d'un gérant. Là où l'isolation entre clients
s'appuie sur `REVOKE CONNECT`, la visibilité des champs ne s'appuie sur rien d'autre que ce
fichier et son test. Le contrôle compensatoire est **l'énumérabilité**, pas la profondeur.

**Pourquoi « absent » et non « `null` ».** Émettre toujours la clé, à `null` quand le droit
manque, donnerait un type TypeScript plus simple et éviterait de toucher `required`. C'est
refusé pour trois raisons : PERM-05 et le critère 4 de la feuille de route disent
**absent** ; une colonne toujours présente dans un CSV est une colonne vide, qui livre
l'existence et la position du champ ; et une valeur monétaire `null` invite un `?? 0` au
site d'appel, donc une marge de **zéro** plutôt qu'une marge visiblement manquante — un
nombre faux sans erreur, exactement ce que la docstring de `MagasinScopedModel` refuse déjà.
"""

from __future__ import annotations

from typing import Mapping

#: `"app_label.ModelName.field_name"` -> code de permission du catalogue.
#:
#: **Vide en phase 3, et c'est délibéré.** `prix_achat` et `marge` n'existent qu'en phase 8
#: (ACHAT-04/07), le chiffre d'affaires global qu'en phase 10 (DASH-01) ; les déclarer ici
#: préempterait le schéma de la phase 8, ce que `03-RESEARCH.md` correction 3 nomme comme
#: l'erreur à ne pas commettre. La phase 3 livre et teste le **mécanisme**, contre une
#: ressource fictive déclarée dans le dossier des tests.
#:
#: Les trois lignes que les phases 8 et 10 ajouteront, telles quelles :
#:
#:     "achats.Article.prix_achat":        Permission.ARTICLE_VOIR_PRIX_ACHAT,
#:     "ventes.LigneVente.marge":          Permission.VENTE_VOIR_MARGE,
#:     "dashboard.Synthese.ca_entreprise": Permission.DASHBOARD_VOIR_CA_GLOBAL,
#:
#: Les trois codes, eux, **existent déjà** dans `plateforme/comptes/permissions_catalogue.py`
#: depuis le plan 03-04 : la phase 8 n'aura qu'une ligne de registre à écrire, pas un
#: modèle de droits à inventer sous pression.
#:
#: C'est un `dict` mutable et non un `MappingProxyType`, pour une seule raison, écrite ici
#: pour qu'elle ne soit pas prise pour de la négligence : la suite de tests y injecte la
#: ressource de test par `monkeypatch.setitem`, exactement la ligne que la phase 8 écrira à
#: demeure. Aucun code de production ne l'écrit, et aucun ne doit le faire — un droit se
#: change en base, jamais en mémoire.
CHAMPS_PROTEGES: dict[str, str] = {}

#: Les champs de modèle délibérément visibles de tous.
#:
#: **Tout champ de modèle exposé par un `ModelSerializer` doit être dans exactement l'une
#: des deux structures** — `test_perm06_tout_champ_de_modele_expose_est_classe` le refuse
#: autrement. Non classé ne veut pas dire public : cela veut dire que quelqu'un a ajouté
#: une colonne et que personne n'a décidé qui peut la voir. « Public » est ici une décision
#: écrite, datée et relisible.
#:
#: Les phases 4 à 10 la remplissent au fur et à mesure, dans le même commit que leurs
#: sérialiseurs. Les huit premières entrées viennent du plan 03-08 : ce sont les champs
#: de l'amorçage de la SPA (`/api/auth/moi/`).
#:
#: **`control_plane.Client` est la raison pour laquelle cette structure vaut son coût.**
#: La table porte aussi `db_name`, `db_host`, `db_user` et `db_password_encrypted`. Deux
#: champs y sont déclarés publics ; les autres ne sont pas « privés par oubli », ils sont
#: **non classés**, et `test_perm06_tout_champ_de_modele_expose_est_classe` rougit en les
#: nommant si quelqu'un les ajoute au sérialiseur. Le garde vaut ici plus que partout
#: ailleurs, parce que la charge utile concernée est servie à chaque connexion.
CHAMPS_PUBLICS: frozenset[str] = frozenset(
    {
        # L'identité du compte connecté (plan 03-08). `password` est absent, donc non
        # classé, donc refusé.
        "comptes.Utilisateur.id",
        "comptes.Utilisateur.email",
        "comptes.Utilisateur.nom_complet",
        "comptes.Utilisateur.est_proprietaire",
        "comptes.Utilisateur.doit_changer_mot_de_passe",
        # La liste des comptes (plan 03-09, `03-UI-SPEC.md` 7.2). Deux décisions plutôt
        # qu'un défaut : le **statut** est visible de quiconque gère les comptes, parce
        # que c'est la colonne que l'écran existe pour montrer ; la **dernière
        # connexion** l'est aussi, et c'est la moins évidente des deux — c'est une donnée
        # de présence sur un collègue, et elle est publiée ici parce qu'un propriétaire
        # qui se demande si un compte sert encore n'a pas d'autre réponse. Elle n'est
        # servie qu'à un détenteur de `compte.gerer`, par la portée de la vue.
        # `derniere_connexion_ip` reste **non classé**, donc refusé : l'adresse d'un
        # collègue n'est une réponse à aucune question de cet écran.
        "comptes.Utilisateur.is_active",
        "comptes.Utilisateur.last_login",
        # L'affaire, telle qu'elle s'affiche dans la barre supérieure.
        "control_plane.Client.code",
        "control_plane.Client.raison_sociale",
        # Le sélecteur de magasin (`03-UI-SPEC.md` 5.4).
        "magasins.Magasin.id",
        "magasins.Magasin.code",
        "magasins.Magasin.nom",
        # ------------------------------------------------------------------------------
        # La fiche client (plan 04-03). « Public » veut dire : quiconque détient
        # `client.voir` voit ces champs. La PORTÉE de la vue décide qui atteint la
        # ressource ; le registre décide seulement ce qu'elle rend une fois atteinte.
        #
        # `notes` est public **et c'est une décision** : l'aide de l'écran l'annonce
        # (« Visible par toute personne qui peut voir ce client »), donc l'opticien sait
        # ce qu'il y écrit. `date_naissance` l'est aussi — c'est une donnée personnelle,
        # mais elle sert la règle des moins de 16 ans et les rappels, à quiconque voit
        # déjà le nom et le téléphone de la même personne.
        #
        # **`derniere_ordonnance` et `resume_ordonnance` n'entrent PAS ici.** Ce sont les
        # deux premières entrées de `CHAMPS_PROTEGES`, et elles arrivent au plan 04-05
        # avec l'ordonnance qui les alimente : une clé protégée déclarée sans son sujet
        # de test rendrait
        # `test_perm06_champ_protege_absent_de_lapi_de_lexport_et_du_document` rouge
        # immédiatement.
        #
        # Les trois colonnes dérivées — `nom_recherche`, `cle_phonetique`,
        # `telephone_normalise` — ne sont pas classées non plus, et n'ont pas à l'être :
        # elles sont `editable=False` et absentes du sérialiseur. Non classé veut dire
        # refusé, ce qui est le bon défaut pour une donnée dont la seule source de vérité
        # est `Client.save()`.
        "clients.Client.id",
        "clients.Client.nom",
        "clients.Client.telephone",
        "clients.Client.date_naissance",
        "clients.Client.adresse",
        "clients.Client.notes",
        "clients.Client.actif",
        "clients.Client.created_at",
        # ------------------------------------------------------------------------------
        # L'ordonnance (plan 04-05). « Public » veut dire ici : **quiconque atteint la
        # ressource**, donc quiconque détient `ordonnance.voir` — et `client.voir`, que
        # `VueOrdonnances` exige en plus. La LIGNE est gardée par le droit ; le registre
        # ne décide que de ce qu'elle rend une fois atteinte.
        #
        # Vingt-quatre lignes, et c'est le prix assumé de la règle que `04-UI-SPEC.md`
        # §15.5 pose : **chaque champ exposé est classé dans le commit de son
        # sérialiseur**, jamais dans un plan de nettoyage. Le coût est de vingt-quatre
        # lignes une fois ; l'alternative est une colonne clinique servie parce que
        # personne n'a décidé qui la voit.
        #
        # **Il n'y a PAS de sous-ensemble protégé ici, et c'est une décision.** On
        # pourrait imaginer réserver `created_par` — qui a saisi — à un droit
        # d'administration. Refusé : la provenance d'une donnée de santé est ce qui rend
        # une correction discutable au comptoir (« c'est Karim qui l'a saisie le 12 »),
        # et la cacher à qui lit déjà la prescription ne protège personne.
        #
        # `motif_revision` est du texte libre saisi par un opticien à propos d'une faute
        # de frappe. Public, et l'écran le dit au moment de l'écrire :
        # « Dites ce qui était faux. Cela restera lisible. » (`04-UI-SPEC.md` §21.3)
        "ordonnances.Ordonnance.id",
        "ordonnances.Ordonnance.client",
        "ordonnances.Ordonnance.magasin",
        "ordonnances.Ordonnance.version",
        "ordonnances.Ordonnance.supersede",
        "ordonnances.Ordonnance.type_revision",
        "ordonnances.Ordonnance.motif_revision",
        "ordonnances.Ordonnance.source",
        "ordonnances.Ordonnance.prescripteur",
        "ordonnances.Ordonnance.date_prescription",
        "ordonnances.Ordonnance.sphere_od",
        "ordonnances.Ordonnance.sphere_og",
        "ordonnances.Ordonnance.cylindre_od",
        "ordonnances.Ordonnance.cylindre_og",
        "ordonnances.Ordonnance.axe_od",
        "ordonnances.Ordonnance.axe_og",
        "ordonnances.Ordonnance.addition_od",
        "ordonnances.Ordonnance.addition_og",
        "ordonnances.Ordonnance.ep_binoculaire",
        "ordonnances.Ordonnance.ep_mono_od",
        "ordonnances.Ordonnance.ep_mono_og",
        "ordonnances.Ordonnance.ep_saisi",
        "ordonnances.Ordonnance.created_at",
        "ordonnances.Ordonnance.created_par",
    }
)


def cle_de_champ(modele, nom_du_champ: str) -> str:
    """La clé de registre d'un champ : `"app_label.ModelName.field_name"`.

    Dérivée plutôt qu'écrite à la main partout où c'est possible : une clé recopiée
    survit à un renommage de champ, et un registre qui protège un nom qui n'existe plus
    est vert et vide.
    """
    return f"{modele._meta.app_label}.{modele._meta.object_name}.{nom_du_champ}"


def est_classe(cle: str) -> bool:
    """Vrai si `cle` a été rangée dans `CHAMPS_PROTEGES` **ou** dans `CHAMPS_PUBLICS`.

    La règle de classification vit ici plutôt que dans le test qui l'applique, pour que le
    jour où elle devient un `system check` — `projection.E001`, comme `03-RESEARCH.md` §3
    le propose — les deux lisent la même fonction. Un test et un check qui ré-implémentent
    chacun « dans l'une des deux » finissent par diverger, et le mode de divergence est
    silencieux dans le mauvais sens.
    """
    return cle in CHAMPS_PROTEGES or cle in CHAMPS_PUBLICS


def champs_interdits(modele, acces, *, magasin_id: int | None = None) -> frozenset[str]:
    """Les champs de `modele` que cet `Acces` n'a pas le droit de voir.

    Trois comportements, et chacun est une décision :

    1. **Un accès absent vaut aucun droit.** `acces is None` retombe sur `Acces.ANONYME`,
       jamais sur « tout montrer ». C'est CLAUDE.md #8 appliqué à la projection : le
       routeur lève plutôt que de renvoyer `None`, la projection cache plutôt que de
       laisser passer (`03-RESEARCH.md` P2, menace T-03-30).
    2. **Le schéma voit tout.** Un `Acces` dont `pour_le_schema` est vrai n'interdit rien,
       pour que le document OpenAPI soit identique quel que soit le lecteur — et donc que
       le client TypeScript généré soit un contrat (menace T-03-32).
    3. **Sans magasin, `peut` est une conjonction.** Le plan 03-05 l'a décidé et sa
       docstring en donne la raison : la projection s'applique à un **sérialiseur**, pas à
       une ligne, donc au moment où elle décide elle ignore de quel magasin sera la ligne
       rendue. `magasin_id` existe pour les appelants qui, eux, le savent — la portée de
       ligne du plan 03-07 et les vues scopées des phases 5 à 10. Aucun consommateur de la
       phase 3 n'en fournit un, et c'est le bon défaut : la conjonction est fail-closed.
    """
    from plateforme.comptes.acces import Acces

    if acces is None:
        acces = Acces.ANONYME
    if getattr(acces, "pour_le_schema", False):
        return frozenset()

    prefixe = f"{modele._meta.app_label}.{modele._meta.object_name}."
    return frozenset(
        cle[len(prefixe) :]
        for cle, code in CHAMPS_PROTEGES.items()
        if cle.startswith(prefixe) and not acces.peut(code, magasin_id=magasin_id)
    )


def codes_proteges_de(modele) -> Mapping[str, str]:
    """`{nom_du_champ: code}` pour ce modèle — la vue par modèle du registre.

    Utilisée par le post-traitement du schéma (`schema.py`), qui raisonne composant par
    composant et a donc besoin de l'entrée dans l'autre sens. Un second dictionnaire tenu
    à la main se désynchroniserait ; une fonction dérivée ne le peut pas.
    """
    prefixe = f"{modele._meta.app_label}.{modele._meta.object_name}."
    return {
        cle[len(prefixe) :]: code
        for cle, code in CHAMPS_PROTEGES.items()
        if cle.startswith(prefixe)
    }
