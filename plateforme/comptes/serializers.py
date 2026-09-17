"""Les sérialiseurs de l'authentification, et la charge utile d'amorçage de la SPA.

**Les trois sérialiseurs de modèle héritent de `SerializerProjete`, et leurs champs sont
inscrits dans `CHAMPS_PUBLICS`.** Ce n'est pas du zèle de conformité : c'est le seul
garde-fou qui existe ici. `test_perm06_tout_champ_de_modele_expose_est_classe` exige que
tout champ exposé par un `ModelSerializer` ait été **classé** — donc le jour où quelqu'un
ajoute `db_name`, `db_password_encrypted` ou `password` à l'un de ces `fields`, la suite
rougit en nommant le champ, au lieu de servir un identifiant de base de données dans la
charge utile d'amorçage de chaque opticien. Un `serializers.Serializer` écrit à la main
n'aurait pas eu ce garde, et c'est la raison du choix.

`Client` est le cas qui justifie la règle à lui seul : la table porte `db_name`,
`db_host`, `db_user` et le mot de passe chiffré du client. Deux champs sont publics, les
autres ne sont pas « privés par oubli », ils sont **non classés**, ce qui est un refus.

Le vocabulaire suit `03-UI-SPEC.md` 9.3 : `droits` à l'écran, `permission` dans le code et
dans l'API.
"""

from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from domaine.magasins.models import Magasin
from plateforme.comptes.models import Utilisateur
from plateforme.comptes.permissions_catalogue import (
    EXPLICATIONS,
    PREREQUIS,
    SECTIONS,
    Permission,
)
from plateforme.control_plane.models import Client
from plateforme.projection.serializers import SerializerProjete


class UtilisateurSerializer(SerializerProjete):
    """Le compte connecté, tel que la SPA le lit.

    `doit_changer_mot_de_passe` est dans la charge utile parce que la SPA en a besoin
    pour router vers `/mot-de-passe` avant d'afficher quoi que ce soit d'autre
    (`03-UI-SPEC.md` 6). `est_proprietaire` y est parce que c'est lui qui décide quelles
    surfaces d'administration sont proposées (7.7) — proposées, jamais autorisées : le
    serveur reste seul juge, et `Acces` est déjà matérialisé sans branche de privilège.
    """

    class Meta:
        model = Utilisateur
        fields = ["id", "email", "nom_complet", "est_proprietaire", "doit_changer_mot_de_passe"]
        read_only_fields = fields


class ClientSerializer(SerializerProjete):
    """L'affaire, réduite à ce qui s'affiche.

    Deux champs, et la liste est courte pour une raison : la table porte aussi le nom, le
    port, l'utilisateur et le mot de passe chiffré de la base de cet opticien. Ajouter
    l'un d'eux ici rendrait la suite rouge (voir la docstring du module), ce qui est
    exactement l'effet recherché.
    """

    class Meta:
        model = Client
        fields = ["code", "raison_sociale"]
        read_only_fields = fields


class MagasinSerializer(SerializerProjete):
    """Un magasin, tel qu'il apparaît dans le sélecteur de la barre supérieure (UI 5.4)."""

    class Meta:
        model = Magasin
        fields = ["id", "code", "nom"]
        read_only_fields = fields


class ConnexionSerializer(serializers.Serializer):
    """Les identifiants soumis. **Aucune validation métier ici, et c'est délibéré.**

    Un `validate()` qui appellerait `authenticate()` produirait une `ValidationError`
    structurée par champ — `{"email": [...]}` contre `{"mot_de_passe": [...]}` — c'est-à-dire
    exactement l'oracle que T-03-48 interdit : la forme du corps dirait lequel des deux
    est faux. Le sérialiseur ne vérifie donc que la présence, et la vue rend une réponse
    unique.

    `trim_whitespace=False` sur le mot de passe : un espace final est un caractère du
    secret, et le rogner rendrait indéchiffrable un compte dont le mot de passe en
    contient un.
    """

    email = serializers.EmailField(write_only=True)
    mot_de_passe = serializers.CharField(write_only=True, trim_whitespace=False)


class ChangementMotDePasseSerializer(serializers.Serializer):
    """Le changement par l'intéressé. L'ancien mot de passe est exigé — **sauf** en
    changement forcé, et la dérogation s'arrête là.

    **Le cas général : `mot_de_passe_actuel` est obligatoire.** Sans lui, un poste laissé
    déverrouillé une minute — ou un CSRF réussi — ne donne plus une session mais un
    compte, définitivement. C'est la différence entre un incident et une perte de
    contrôle, et c'est la garantie que le plan 03-08 a posée ici.

    **La dérogation : `doit_changer_mot_de_passe` vrai, et rien d'autre.** Sur
    l'atterrissage forcé, la personne vient de saisir ce mot de passe précis, quelques
    secondes plus tôt, pour ouvrir la session qui porte cette requête. Le lui redemander
    revient à lui faire répéter ce qu'elle vient de taper. Et la garantie ci-dessus ne
    protège rien dans cet état : le mot de passe d'un compte en changement forcé a été
    **posé par le propriétaire ou par l'opérateur**, il est connu d'un tiers par
    construction — c'est précisément pourquoi le drapeau est levé.

    Tranché par le propriétaire au point de contrôle du plan 03-13, le 2026-09-17,
    revenant sur la décision du point de contrôle 03-12 (`03-UI-SPEC.md` 9.4, amendée
    une seconde fois). Deux tests nommés tiennent les deux moitiés, et c'est le second
    qui compte : `test_perm01_un_changement_force_n_exige_pas_le_mot_de_passe_actuel` et
    `test_perm01_un_compte_ordinaire_reste_refuse_sans_le_mot_de_passe_actuel`. Une
    dérogation écrite pour un cas précis s'élargit au premier refactoring qui trouve la
    condition gênante ; le second test rougit quand cela arrive.

    Facultatif n'est pas ignoré : fourni, le champ est **vérifié**, y compris en
    changement forcé — un mot de passe actuel faux reste un 400.

    `validate_password` applique `AUTH_PASSWORD_VALIDATORS`, qui est **posé** dans
    `config/settings/base.py` : sans validateurs déclarés, cet appel valide `1234` en
    silence, et le point de terminaison aurait l'air protégé sans l'être.
    """

    mot_de_passe_actuel = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        required=False,
        help_text=(
            "Obligatoire, sauf lorsque le compte porte `doit_changer_mot_de_passe`."
        ),
    )
    nouveau_mot_de_passe = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_mot_de_passe_actuel(self, valeur: str) -> str:
        utilisateur = self.context["utilisateur"]
        if not utilisateur.check_password(valeur):
            raise serializers.ValidationError("Le mot de passe actuel est incorrect.")
        return valeur

    def validate(self, attrs: dict) -> dict:
        """L'exigence, portée ici parce qu'elle dépend du compte et non du champ.

        `required=True` sur le champ ne saurait pas lire `doit_changer_mot_de_passe` ;
        la condition est donc au niveau de l'objet. Le corps d'erreur reste indexé par
        le nom du champ, pour que l'interface sache lequel manque.
        """
        utilisateur = self.context["utilisateur"]
        if not utilisateur.doit_changer_mot_de_passe and "mot_de_passe_actuel" not in attrs:
            raise serializers.ValidationError(
                {"mot_de_passe_actuel": ["Ce champ est obligatoire."]}
            )
        return attrs

    def validate_nouveau_mot_de_passe(self, valeur: str) -> str:
        try:
            validate_password(valeur, self.context["utilisateur"])
        except DjangoValidationError as erreur:
            # Les messages de Django sont déjà traduits en français ; les recopier ici
            # les ferait dériver de la politique qu'ils décrivent.
            raise serializers.ValidationError(list(erreur.messages)) from erreur
        return valeur


class DroitCatalogueSerializer(serializers.Serializer):
    """Une ligne de l'écran de droits : le code, son libellé et sa phrase d'explication."""

    code = serializers.CharField(read_only=True)
    libelle = serializers.CharField(read_only=True)
    explication = serializers.CharField(read_only=True)


class SectionCatalogueSerializer(serializers.Serializer):
    """Un bloc de l'écran de droits, dans l'ordre d'affichage (`03-UI-SPEC.md` 7.4)."""

    titre = serializers.CharField(read_only=True)
    droits = DroitCatalogueSerializer(many=True, read_only=True)


class CatalogueSerializer(serializers.Serializer):
    """Le catalogue servi à la SPA : les sections, et la carte des prérequis (7.6)."""

    sections = SectionCatalogueSerializer(many=True, read_only=True)
    prerequis = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField()), read_only=True
    )


class AmorcageSerializer(serializers.Serializer):
    """La forme de `/api/auth/moi/`. **Déclarée pour le schéma, pas pour sérialiser.**

    La charge utile est construite par `charge_utile_moi`, qui interroge deux bases et
    l'accès résolu ; ce sérialiseur existe pour que `drf-spectacular` produise un
    composant et donc un type TypeScript. Sans lui, `AutoSchema` ne devine rien d'une
    `APIView` et **ignore la vue entièrement** — les cinq routes d'authentification
    seraient absentes du contrat dont le client est généré, ce qui est la pire forme
    d'absence : silencieuse et invisible en revue.

    `client` est nullable parce qu'un opérateur de plateforme n'appartient à aucune
    affaire, et le type généré doit le dire plutôt que promettre un objet.
    """

    utilisateur = UtilisateurSerializer(read_only=True)
    client = ClientSerializer(read_only=True, allow_null=True)
    permissions = serializers.ListField(child=serializers.CharField(), read_only=True)
    magasins = MagasinSerializer(many=True, read_only=True)
    catalogue = CatalogueSerializer(read_only=True)


def catalogue_des_droits() -> dict:
    """Le catalogue complet : sections, libellés, explications et prérequis.

    Servi **en entier**, et non pré-intersecté avec les droits de l'appelant : il est
    identique pour chaque client du produit, donc il ne divulgue rien, et l'écran 403 de
    `03-UI-SPEC.md` 8.6 nomme le droit manquant précisément pour cette raison. Le
    catalogue *pré-intersecté* — celui qu'un gérant-gestionnaire peut **accorder** — est
    une question différente, et c'est le plan 03-09 qui la traite.

    Les libellés viennent de `Permission.labels`, donc d'un seul endroit : un libellé ne
    peut pas dériver de son code, et un code ajouté en phase 8 apparaît à l'écran sans
    qu'une ligne change côté client (`03-UI-SPEC.md` 7.4).
    """
    return {
        "sections": [
            {
                "titre": section.titre,
                "droits": [
                    {
                        "code": str(code),
                        "libelle": _libelle(code),
                        "explication": EXPLICATIONS[code],
                    }
                    for code in section.codes
                ],
            }
            for section in SECTIONS
        ],
        "prerequis": {str(code): [str(r) for r in requis] for code, requis in PREREQUIS.items()},
    }


def _libelle(code) -> str:
    """Le libellé humain d'un code, lu sur l'énumération plutôt que dupliqué."""
    from plateforme.comptes.permissions_catalogue import Permission

    return Permission(code).label


def charge_utile_moi(utilisateur, acces, client, magasins) -> dict:
    """L'amorçage de la SPA, en une seule réponse.

    Une requête plutôt que cinq, parce que c'est la première chose qui se passe après la
    connexion et que chaque aller-retour supplémentaire est une fraction de seconde
    d'écran vide au comptoir.

    **`permissions` se calcule avec `peut_quelque_part`, et nulle part ailleurs.** Ce
    champ ne décide que de l'affichage des entrées de navigation : une entrée doit
    apparaître dès lors que le droit est détenu dans **au moins un** magasin, sinon un
    gérant qui gère le stock du seul magasin de Casablanca perdrait l'entrée « Stock ».
    Ce n'est donc **pas** une autorisation, et la SPA ne doit jamais s'en servir pour
    décider d'afficher une donnée : la projection serveur s'en charge
    (`03-UI-SPEC.md` 8.3). C'est l'un des deux seuls appels sanctionnés de
    `peut_quelque_part` ; le garde source de `tests/test_magasin_acces.py` refuse le
    troisième.
    """
    from plateforme.comptes.permissions_catalogue import Permission

    return {
        "utilisateur": UtilisateurSerializer(utilisateur).data,
        "client": ClientSerializer(client).data if client is not None else None,
        "permissions": [
            str(code)
            for code in Permission.values
            # usage-sanctionne: peut_quelque_part navigation
            if acces.peut_quelque_part(code)
        ],
        "magasins": MagasinSerializer(magasins, many=True).data,
        "catalogue": catalogue_des_droits(),
    }


# ======================================================================================
# PERM-02 — la surface de gestion des comptes (plan 03-09)
# ======================================================================================
#
# **Aucun de ces sérialiseurs n'accepte `client`, `est_proprietaire`, `is_staff`,
# `is_superuser` ni `derniere_connexion_ip` en entrée**, et c'est la seule ligne de
# défense devant deux d'entre eux. La contrainte de base du plan 03-01 rattrape
# `is_staff` et `is_superuser` — elle rend un compte-opérateur rattaché à un client
# impossible, même par `queryset.update()` — mais `client` et `est_proprietaire` n'ont
# que le sérialiseur devant eux : un propriétaire qui poste
# `{"client": 7, "est_proprietaire": true}` obtiendrait autrement un compte dans
# l'affaire d'un concurrent, avec une adresse de connexion qu'il contrôle
# (`03-RESEARCH.md` A-03-05, menace T-03-57).
#
# La forme qui rend cela vrai n'est pas une liste d'exclusions — une liste d'exclusions
# se périme au premier champ ajouté au modèle — mais une **liste d'inclusions** : les
# sérialiseurs d'écriture ci-dessous sont des `Serializer` nus qui déclarent leurs trois
# champs, donc un champ ajouté à `Utilisateur` en phase 12 n'y apparaît pas tout seul.


class CompteSerializer(SerializerProjete):
    """Une ligne de la liste des comptes et la fiche de détail (`03-UI-SPEC.md` 7.2, 7.3).

    Purement sortant : l'écriture passe par `CreationCompteSerializer` et par
    `ModificationIdentiteSerializer`, qui ne partagent aucun champ avec celui-ci par
    accident.

    `nombre_de_droits` et `personnalise` sont calculés **côté serveur**. L'interface ne
    doit pas avoir à recomposer l'uniformité d'une ligne depuis N requêtes : à trois
    magasins et vingt-et-un codes, le badge « Personnalisé par magasin » coûterait
    soixante-trois lectures par ligne de tableau (7.2).

    Les noms sont français et les sources sont les colonnes de Django — `actif` pour
    `is_active`, `derniere_connexion` pour `last_login`. `test_perm06_tout_champ_de_modele_expose_est_classe`
    lit la **source**, pas le nom, donc les deux clés correspondantes sont inscrites dans
    `CHAMPS_PUBLICS` et non le nom d'affichage.
    """

    actif = serializers.BooleanField(source="is_active", read_only=True)
    derniere_connexion = serializers.DateTimeField(
        source="last_login", read_only=True, allow_null=True
    )
    magasins = serializers.SerializerMethodField()
    nombre_de_droits = serializers.SerializerMethodField()
    personnalise = serializers.SerializerMethodField()

    class Meta:
        model = Utilisateur
        fields = [
            "id",
            "nom_complet",
            "email",
            "est_proprietaire",
            "actif",
            "doit_changer_mot_de_passe",
            "derniere_connexion",
            "magasins",
            "nombre_de_droits",
            "personnalise",
        ]
        read_only_fields = [
            "id",
            "nom_complet",
            "email",
            "est_proprietaire",
            "doit_changer_mot_de_passe",
        ]

    def _resume(self, compte):
        """Le résumé de ce compte, résolu une fois par réponse et non une fois par champ.

        Trois champs le lisent et `resume_des_droits` passe par `acces_pour`, qui
        interroge deux bases. Sans ce cache de contexte, une liste de dix comptes ferait
        soixante requêtes au lieu de vingt.
        """
        from plateforme.comptes.services import resume_des_droits

        cache = self.context.setdefault("_resumes", {})
        if compte.pk not in cache:
            cache[compte.pk] = resume_des_droits(compte)
        return cache[compte.pk]

    @extend_schema_field(MagasinSerializer(many=True))
    def get_magasins(self, compte):
        """Les magasins **accordés et actifs** de ce compte, jamais tous ceux de l'affaire.

        Même règle que le sélecteur de la barre supérieure (plan 03-08) : renvoyer la
        liste entière donnerait à un gérant-gestionnaire d'Anfa l'énumération des
        magasins qu'il ne détient pas.
        """
        par_id = self.context.get("magasins_par_id") or {}
        magasins = [
            par_id[identifiant]
            for identifiant in self._resume(compte).magasins_ids
            if identifiant in par_id
        ]
        return MagasinSerializer(magasins, many=True).data

    def get_nombre_de_droits(self, compte) -> int:
        return self._resume(compte).nombre_de_droits

    def get_personnalise(self, compte) -> bool:
        """Vrai dès qu'un octroi n'est pas uniforme sur les magasins accordés (7.5)."""
        return self._resume(compte).personnalise


class CreationCompteSerializer(serializers.Serializer):
    """Le dialogue de création (`03-UI-SPEC.md` 7.2) : trois champs, et pas un de plus.

    `client` est posé par la vue depuis `request.acces.client_id` et n'apparaît donc
    nulle part ici. Un `ModelSerializer` aurait été plus court et aurait ouvert la porte
    à un champ de modèle ajouté plus tard qui deviendrait inscriptible sans que personne
    ne le décide : c'est exactement le mode de défaillance de A-03-05.

    Le mot de passe provisoire est **facultatif**. Le bouton `Générer un mot de passe` du
    dialogue existe précisément pour que le propriétaire n'en invente pas un ; quand il
    est absent, le serveur en tire un et le renvoie une seule fois.
    """

    nom_complet = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    mot_de_passe_provisoire = serializers.CharField(
        write_only=True, required=False, allow_blank=False, trim_whitespace=False
    )

    def validate_email(self, valeur: str) -> str:
        """Refuser une adresse déjà prise, **sans confirmer qu'un compte existe**.

        L'adresse de connexion est unique sur toute la flotte (CLAUDE.md #11), donc un
        message « un utilisateur avec cette adresse existe déjà » dirait à un opticien
        qu'un compte existe chez un concurrent — le même oracle d'énumération que la vue
        de connexion refuse d'être (T-03-48). Le refus est inévitable, puisque la
        création doit échouer ; ce qui est évitable est de nommer sa cause.

        Le résidu est admis et écrit : l'appelant apprend que l'adresse est prise
        *quelque part*. Il faut être authentifié et détenir `compte.gerer` pour poser la
        question, donc ce n'est pas un oracle ouvert.
        """
        if Utilisateur.objects.filter(email__iexact=valeur).exists():
            raise serializers.ValidationError(
                "Cette adresse e-mail n'est pas disponible."
            )
        return valeur

    def validate(self, donnees):
        """Le mot de passe fourni passe par `AUTH_PASSWORD_VALIDATORS`.

        La politique est celle de `ChangementMotDePasseSerializer` (plan 03-08), et il
        n'y a pas de raison qu'un mot de passe posé par un tiers y échappe — au
        contraire : c'est celui que le gérant recevra.
        """
        fourni = donnees.get("mot_de_passe_provisoire")
        if fourni:
            futur = Utilisateur(
                email=donnees.get("email", ""),
                nom_complet=donnees.get("nom_complet", ""),
            )
            try:
                validate_password(fourni, futur)
            except DjangoValidationError as erreur:
                raise serializers.ValidationError(
                    {"mot_de_passe_provisoire": list(erreur.messages)}
                ) from erreur
        return donnees


class ModificationIdentiteSerializer(serializers.Serializer):
    """`PATCH` sur la fiche : le nom et l'adresse, rien d'autre (`03-UI-SPEC.md` 7.3 A).

    Le statut n'est pas ici, et c'est la spécification : `Statut` est une liste
    déroulante suivie d'une confirmation, pas un interrupteur, parce que la
    désactivation mérite d'être confirmée. Elle a donc son propre point de terminaison,
    ce qui la rend aussi identifiable côté serveur.
    """

    nom_complet = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False)

    def validate_email(self, valeur: str) -> str:
        existants = Utilisateur.objects.filter(email__iexact=valeur)
        if self.instance is not None:
            existants = existants.exclude(pk=self.instance.pk)
        if existants.exists():
            raise serializers.ValidationError(
                "Cette adresse e-mail n'est pas disponible."
            )
        return valeur


class StatutSerializer(serializers.Serializer):
    """`{"actif": false}` — la désactivation, et son inverse (`03-UI-SPEC.md` 7.9).

    Une action explicite plutôt qu'un `PATCH` sur `is_active` : côté interface elle
    mérite une confirmation, et côté serveur elle mérite d'être un événement
    identifiable plutôt qu'une colonne parmi d'autres dans un corps partiel.
    """

    actif = serializers.BooleanField()


class CompteCreeSerializer(serializers.Serializer):
    """La réponse de création et de réinitialisation : le compte, **et le secret, une fois**.

    Le mot de passe provisoire ne réapparaît dans aucune autre charge utile. Il n'existe
    pas de chemin par courriel (plan 03-08 : aucun fournisseur d'e-mail dans la pile),
    donc l'interface l'affiche avec « Notez-le maintenant : il ne sera plus affiché. » et
    le propriétaire le transmet de vive voix.
    """

    compte = CompteSerializer(read_only=True)
    mot_de_passe_provisoire = serializers.CharField(read_only=True)


# ======================================================================================
# PERM-03 — l'octroi, la révocation, et la forme de leur réponse (plan 03-09)
# ======================================================================================
#
# **La réponse d'une bascule est un contrat**, et le plan 03-14 construit l'écran de
# droits contre lui. Elle porte de quoi reconstruire la ligne — `actif`, `inactif` ou
# `mixte` — pour **chaque** code touché, cascade comprise. Sans cela, la sauvegarde par
# interrupteur de `03-UI-SPEC.md` 7.8 obligerait l'interface à recharger toute la page
# après chaque clic, ce qui est exactement ce que « immédiate » exclut.


class BasculeDroitSerializer(serializers.Serializer):
    """`{code, accorde, magasins?}` — un interrupteur, et rien d'autre.

    Un seul point de terminaison pour les deux sens, parce que c'est **un seul contrôle**
    à l'écran : un `accorde: false` sur une route d'octroi se lit mieux que deux routes
    dont l'interface devrait choisir à chaque clic.

    `magasins` absent signifie **tous les magasins accordés**, ce qui produit le
    comportement uniforme par défaut de 7.5. Le fournir est le chemin « Par magasin »,
    celui qui n'apparaît qu'à la demande et seulement au-dessus de deux magasins.
    """

    code = serializers.ChoiceField(choices=Permission.choices)
    accorde = serializers.BooleanField()
    magasins = serializers.ListField(
        child=serializers.CharField(max_length=20), required=False, allow_empty=False
    )


class UniformisationSerializer(serializers.Serializer):
    """`{code, accorde}` — le bouton `Uniformiser` de 7.5, qui replie une ligne mixte."""

    code = serializers.ChoiceField(choices=Permission.choices)
    accorde = serializers.BooleanField()


class BasculeMagasinSerializer(serializers.Serializer):
    """`{magasin_code, accorde}` — l'accès à un magasin (`03-UI-SPEC.md` 7.3 B).

    Le code métier, jamais l'identifiant : c'est ce que stocke `AccesMagasin`, et c'est
    ce qui survit à une restauration là où un `id` est réattribué (TENANT-09).
    """

    magasin_code = serializers.CharField(max_length=20)
    accorde = serializers.BooleanField()


class LigneDeDroitSerializer(serializers.Serializer):
    """L'état d'un code pour un compte : sa valeur, et les magasins où elle vaut.

    `etat` vaut `actif`, `inactif` ou `mixte`. Les deux premiers sont **uniformes** au
    sens de 7.5 — tous les magasins accordés sont d'accord — et `mixte` est l'unique
    état personnalisé, celui que l'interrupteur parent rend en tri-état avec
    `aria-checked="mixed"`.
    """

    code = serializers.CharField(read_only=True)
    etat = serializers.CharField(read_only=True)
    magasins = serializers.ListField(child=serializers.CharField(), read_only=True)


class ResultatOctroiSerializer(serializers.Serializer):
    """Ce qu'une bascule renvoie, et ce que l'écran de droits en fait.

    | Champ | Ce que l'interface en fait |
    |---|---|
    | `lignes` | redessine chaque interrupteur touché, **sans recharger** (7.8) |
    | `cascade` | la note en ligne « … a été activé automatiquement » (7.6) |
    | `cascade` | et le **toast d'annulation unique** qui couvre tout l'ensemble |
    | `magasins_accordes` | le dénominateur de « Personnalisé : 2 magasins sur 3 » |
    | `magasins_etendus` | la note « Californie a été ajouté. Vérifiez les 2 droits… » |

    `lignes` porte le code demandé **en tête**, puis les codes emportés par la cascade.
    """

    code = serializers.CharField(read_only=True)
    action = serializers.CharField(read_only=True)
    lignes = LigneDeDroitSerializer(many=True, read_only=True)
    cascade = serializers.ListField(child=serializers.CharField(), read_only=True)
    magasins_accordes = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )
    magasins_etendus = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )


def charge_utile_resultat(resultat) -> dict:
    """Le `Resultat` du service, en dictionnaire. Une seule traduction, pour trois routes."""
    return {
        "code": str(resultat.code),
        "action": str(resultat.action),
        "lignes": [
            {"code": ligne.code, "etat": ligne.etat, "magasins": list(ligne.magasins)}
            for ligne in resultat.lignes
        ],
        "cascade": [str(code) for code in resultat.cascade],
        "magasins_accordes": list(resultat.magasins_accordes),
        "magasins_etendus": list(resultat.magasins_etendus),
    }


class EntreeDeJournalSerializer(serializers.Serializer):
    """Une ligne de `03-UI-SPEC.md` 7.3 D — la seule vue de `JournalDroit`.

    **Déclarée pour le schéma, pas pour sérialiser** : la charge utile est construite par
    `charge_utile_journal`, qui joint deux mondes — les libellés des permissions vivent
    dans le plan de contrôle, les noms des magasins dans la base de l'opticien.

    `nature` plutôt qu'une phrase toute faite. « a accordé « Voir le prix d'achat » » et
    « a accordé l'accès au magasin Maârif » ne se composent pas pareil en français, et
    cette grammaire-là appartient à l'interface (`03-UI-SPEC.md` 9.3). Le serveur livre
    donc un libellé et sa nature, jamais une phrase à afficher telle quelle — une phrase
    assemblée ici serait impossible à corriger sans redéployer le serveur.
    """

    le = serializers.DateTimeField(read_only=True)
    action = serializers.CharField(read_only=True)
    nature = serializers.CharField(read_only=True)
    cible = serializers.CharField(read_only=True)
    libelle = serializers.CharField(read_only=True)
    par = serializers.CharField(read_only=True)


def charge_utile_journal(entrees, codes_visibles, magasins_visibles) -> list[dict]:
    """Le journal d'un compte, **intersecté** comme le catalogue et la fiche.

    Une entrée dont la cible sort de l'intersection est **retirée**, pas anonymisée : un
    « (droit masqué) » dirait qu'il y a quelque chose à voir et combien de fois, ce qui
    est la même divulgation en plus discret. Sans ce filtre, il suffirait d'ouvrir le
    repli d'un historique pour contourner tout ce que `catalogue_offrable` retire.

    Une entrée dont la cible n'est plus dans le catalogue **ni** dans les magasins — un
    magasin désactivé depuis, par exemple — tombe dans le même cas. C'est un appauvrissement
    assumé de l'historique, et l'alternative serait de servir le code brut à l'écran.
    """
    charge = []
    for entree in entrees:
        if entree.cible in codes_visibles:
            nature, libelle = "droit", _libelle(entree.cible)
        elif entree.cible in magasins_visibles:
            nature, libelle = "magasin", magasins_visibles[entree.cible]
        else:
            continue
        charge.append(
            {
                "le": entree.le,
                "action": entree.action,
                "nature": nature,
                "cible": entree.cible,
                "libelle": libelle,
                "par": entree.par.nom_complet,
            }
        )
    return charge


class CompteDetailSerializer(CompteSerializer):
    """La fiche (`03-UI-SPEC.md` 7.3), qui porte en plus **l'état de chaque droit**.

    Un sérialiseur distinct de celui de la liste, et c'est le point : vingt et un états
    par ligne de tableau est précisément le coût que `resume_des_droits` existe pour
    éviter (7.2). La liste affiche un nombre et un badge ; la fiche a besoin de chaque
    interrupteur, et elle est seule à l'écran.

    `droits` et `magasins_accordes` sont **déjà intersectés** avec ce que l'appelant peut
    accorder : les codes viennent du même `catalogue_offrable` qui sert le catalogue, et
    les magasins de son propre `Acces`. Un état servi pour un code hors catalogue le
    réintroduirait par la porte de service, et le grisage que 7.7 refuse serait alors
    fait par la SPA faute de mieux.
    """

    droits = serializers.SerializerMethodField()
    magasins_accordes = serializers.SerializerMethodField()

    class Meta(CompteSerializer.Meta):
        fields = [*CompteSerializer.Meta.fields, "droits", "magasins_accordes"]

    def _etat(self, compte):
        """Résolu une fois par réponse : les deux champs le lisent."""
        from plateforme.comptes.services import etat_des_droits

        cache = self.context.setdefault("_etats", {})
        if compte.pk not in cache:
            cache[compte.pk] = etat_des_droits(
                compte,
                self.context.get("codes_offrables") or (),
                self.context.get("magasins_offrables"),
            )
        return cache[compte.pk]

    @extend_schema_field(LigneDeDroitSerializer(many=True))
    def get_droits(self, compte):
        _accordes, lignes = self._etat(compte)
        return [
            {"code": ligne.code, "etat": ligne.etat, "magasins": list(ligne.magasins)}
            for ligne in lignes
        ]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_magasins_accordes(self, compte):
        accordes, _lignes = self._etat(compte)
        return accordes


# ======================================================================================
# PERM-06 — le catalogue **offrable**, intersecté avant sérialisation (plan 03-09)
# ======================================================================================


class CatalogueOffrableSerializer(CatalogueSerializer):
    """La forme de `GET /api/comptes/catalogue/`. Déclarée pour le schéma, pas pour sérialiser.

    Le catalogue **complet** est servi par `/api/auth/moi/` via `catalogue_des_droits()` :
    il est identique pour chaque affaire du produit, donc il ne divulgue rien, et l'écran
    403 de `03-UI-SPEC.md` 8.6 nomme le droit manquant précisément pour cette raison.

    Celui-ci répond à une autre question — **ce que l'appelant peut accorder** — et sa
    réponse dépend donc de l'appelant. Elle porte en plus les magasins qu'il détient,
    parce que l'écran de droits a besoin des deux axes pour dessiner une ligne.
    """

    magasins = MagasinSerializer(many=True, read_only=True)


def catalogue_offrable(acces, magasins) -> dict:
    """Le catalogue **déjà intersecté** avec les droits et les magasins de l'appelant.

    C'est la seule recommandation de fond du `03-UI-CHECK.md`, et elle est appliquée ici
    plutôt que dans la SPA pour une raison précise, écrite dans `03-UI-SPEC.md` 7.7 :
    **« This is a wire-level guarantee, not a rendering rule. »** Un code que l'éditeur
    ne détient pas est **absent du JSON**, exactement comme un champ non autorisé est
    absent d'une charge utile de ligne. Le client rend ce qu'il reçoit et n'a **aucune
    branche de filtrage** à lui, donc il n'existe aucune liste de codes cachés à extraire
    d'une inspection du navigateur, d'une réponse en cache ou d'un remaniement futur.

    Griser la ligne aurait été l'autre option, et c'est celle qu'on écrit sans y penser.
    Elle apprend au gérant-gestionnaire que la permission existe et qu'il ne la détient
    pas — ce qui est exactement ce que « absent, pas désactivé » refuse. L'interface ne
    doit donc pas avoir à la masquer : elle ne la reçoit pas.

    **`peut_quelque_part` est l'union, et c'est ici l'outil juste** — pour la seule fois
    avec la navigation. La question posée n'est pas « a-t-il le droit d'agir ici ? » mais
    « cette case a-t-elle un sens pour lui ? », et un gérant qui détient
    `article.voir_prix_achat` à Anfa doit pouvoir l'accorder à un collègue d'Anfa. Le
    refus par magasin, lui, est appliqué au moment de l'octroi par
    `plateforme.comptes.services`, qui interroge `peut(code, magasin_id)` — la question
    précise. L'union propose, la conjonction dispose.

    Conséquence que `03-UI-SPEC.md` 7.4 tire et qui vaut d'être écrite : un code ajouté
    en phase 8 apparaît dans l'écran **sans aucun changement côté SPA**, et un libellé ne
    peut jamais dériver de son code — les deux viennent d'ici.
    """
    visibles = {
        str(code)
        for code in Permission.values
        # usage-sanctionne: peut_quelque_part catalogue
        if acces.peut_quelque_part(code)
    }

    sections = []
    for section in SECTIONS:
        droits = [
            {
                "code": str(code),
                "libelle": _libelle(code),
                "explication": EXPLICATIONS[code],
            }
            for code in section.codes
            if str(code) in visibles
        ]
        # Une section vide n'est pas servie : un titre sans ligne dirait « il y a des
        # droits ici, mais pas pour vous », ce qui est la version typographique du
        # grisage.
        if droits:
            sections.append({"titre": section.titre, "droits": droits})

    # La carte des prérequis est restreinte aux codes visibles, des deux côtés. Une
    # entrée nommant un code absent réintroduirait par la porte de service ce que
    # l'intersection vient de retirer.
    prerequis = {}
    for code, requis in PREREQUIS.items():
        if str(code) not in visibles:
            continue
        retenus = [str(r) for r in requis if str(r) in visibles]
        if retenus:
            prerequis[str(code)] = retenus

    return {
        "sections": sections,
        "prerequis": prerequis,
        "magasins": MagasinSerializer(magasins, many=True).data,
    }
