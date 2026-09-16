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
from rest_framework import serializers

from domaine.magasins.models import Magasin
from plateforme.comptes.models import Utilisateur
from plateforme.comptes.permissions_catalogue import EXPLICATIONS, PREREQUIS, SECTIONS
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
    """Le changement par l'intéressé. L'ancien mot de passe est exigé.

    Sans lui, un poste laissé déverrouillé une minute — ou un CSRF réussi — ne donne plus
    une session mais un compte, définitivement. C'est la différence entre un incident et
    une perte de contrôle.

    `validate_password` applique `AUTH_PASSWORD_VALIDATORS`, qui est **posé** dans
    `config/settings/base.py` : sans validateurs déclarés, cet appel valide `1234` en
    silence, et le point de terminaison aurait l'air protégé sans l'être.
    """

    mot_de_passe_actuel = serializers.CharField(write_only=True, trim_whitespace=False)
    nouveau_mot_de_passe = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_mot_de_passe_actuel(self, valeur: str) -> str:
        utilisateur = self.context["utilisateur"]
        if not utilisateur.check_password(valeur):
            raise serializers.ValidationError("Le mot de passe actuel est incorrect.")
        return valeur

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
