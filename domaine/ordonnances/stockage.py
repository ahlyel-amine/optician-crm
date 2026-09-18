"""Où vit la photo d'une ordonnance, et pourquoi la forme évidente ne marche pas.

CLIENT-09. C'est le **premier fichier du produit** : avant ce module il n'existait ni
racine de média, ni `STORAGES`, ni `FileField` nulle part dans `config/`, `plateforme/`
ou `domaine/`.

======================================================================================
LA PROPRIÉTÉ QUI REND CECI SÛR, ET C'EST LA SEULE PHRASE À RETENIR
======================================================================================

    Le nom stocké est **relatif au locataire**, et le préfixe est **redérivé du
    contexte vivant à chaque accès**. Une ligne portant le chemin d'un autre
    locataire ne peut pas se résoudre, parce que le préfixe ne vient **jamais** de la
    ligne.

C'est la discipline de `TenantRouter` appliquée aux fichiers : l'appelant ne nomme pas
la frontière.

======================================================================================
POURQUOI CE N'EST PAS `storage=<appelable>` SUR LE CHAMP
======================================================================================

`django/db/models/fields/files.py`, `FileField.__init__`, lu dans le Django 6.1.1
installé :

    self.storage = storage if storage is not None else default_storage
    if callable(self.storage):
        self._storage_callable = self.storage
        self.storage = self.storage()      # <-- appelé UNE fois, à la construction

**Un appelable est évalué exactement une fois, à l'import du module.** Or l'alias du
locataire n'existe que dans un `contextvar`, au moment de la requête. La forme
évidente — `storage=lambda: StockageDuLocataire(current_alias())` — lierait donc
silencieusement le locataire qui se trouvait lié à l'import, c'est-à-dire aucun en
pratique et **un seul** au pire. C'est exactement la classe de bogue que CLAUDE.md #12
décrit : invisible en revue, parce que la garantie qu'elle casse est écrite un étage
plus haut.

La distinction que ce module tient, et qui règle les deux besoins d'un coup :

* **quel back-end** est un choix de *déploiement*, arrêté une fois — donc l'appelable
  `stockage_des_photos` est la bonne forme, et le champ l'utilise ;
* **quel locataire** est un choix par *requête* — donc il est redérivé dans chaque
  méthode, et il ne peut pas être un appelable de champ.

L'appelable a un second effet, qui n'est pas un détail : `FileField.deconstruct()`
resérialise `self._storage_callable`, donc la migration nomme **la fonction** et non
l'instance. Le fichier de migration ne dépend alors pas de la valeur du réglage, et
`makemigrations --check` reste vert quel que soit le back-end configuré.

======================================================================================
L'AVEU, ET IL EST LA VÉRITÉ DE CE MODULE
======================================================================================

L'isolation des **lignes** entre opticiens repose sur `REVOKE CONNECT` et une base
séparée — une frontière *sous* l'application. L'isolation des **fichiers** repose sur
Python et sur cette seule classe. **Il n'y a aucun `REVOKE` en dessous.**

Le contrôle compensatoire est donc le même que pour la projection : un test qui lie le
locataire B, lui présente un chemin du locataire A, et est refusé —
`tests/test_ordonnance_photo.py::test_client09_un_chemin_d_un_autre_client_est_refuse`,
et ses trois moitiés. Ce test n'est pas optionnel : il **est** la garantie.

Ce que le cadre ferme déjà, et qu'il ne faut donc pas confondre avec le risque réel :
`django/core/files/utils.py::validate_file_name(nom, allow_relative_path=True)` lève
`SuspiciousFileOperation` sur un chemin absolu ou sur tout composant `..`. Le risque
résiduel n'est **pas** `../../` — c'est un chemin relatif parfaitement valide
**appartenant à un autre opticien**. Seule la redérivation du préfixe le ferme.

======================================================================================
LE BACK-END DE PRODUCTION EST UNE SORTIE DE LA PHASE 1
======================================================================================

`LocalFilesystemStorage` de `plateforme/control_plane/storage.py` est le précédent
imité ici — le contrôle `is_relative_to`, le `chmod(0o600)` sur chaque artefact, et
l'honnêteté sur le statut de développement. Il n'est pas **réutilisé** : `FileField`
exige une sous-classe de `django.core.files.storage.Storage`, pas l'interface à deux
méthodes des sauvegardes. Le miroir, pas l'héritage.

**Le back-end de stockage de production est une sortie de la PHASE 1 (LEGAL-02,
juridiction d'hébergement), pas de la phase 4.** Le développement est sur système de
fichiers local. Le critère 3 de la phase 1 exige que l'infrastructure vive dans la
juridiction choisie *avant* qu'une donnée client réelle y soit stockée, et la phase 1
n'a pas commencé.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files import File
from django.core.files.storage import Storage
from django.core.files.utils import validate_file_name
from django.utils.deconstruct import deconstructible
from django.utils.module_loading import import_string

from plateforme.tenancy.context import current_alias

#: Le dossier d'une photo est le **numéro de version** de l'ordonnance, et rien d'autre.
#: Restreint à des chiffres pour une raison précise : c'est la seule partie du nom que
#: l'appelant fournit, et un dossier libre laisserait passer un nom de patient dans une
#: arborescence que personne ne relit jamais.
_DOSSIER = re.compile(r"^[0-9]+$")

#: L'extension retenue par type déclaré. Le suffixe du fichier envoyé n'est jamais
#: réutilisé : il est choisi par l'appelant, donc il ne prouve rien, et il fait partie
#: du nom que ce module refuse de conserver.
EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
}


@deconstructible
class StockageOrdonnances(Storage):
    """Un `Storage` Django dont le préfixe vient du contexte, à chaque accès.

    Voir l'en-tête du module pour le raisonnement complet : la propriété tenue, la
    raison pour laquelle un appelable de champ ne peut pas la tenir, et l'aveu sur ce
    qui ne soutient pas cette classe par en dessous.

    **Développement uniquement**, comme `LocalFilesystemStorage`. La racine est un
    chemin local ; la production est une sortie de la phase 1.
    """

    @property
    def racine(self) -> Path:
        """La racine de tous les locataires. Lue au réglage, jamais mise en cache.

        Non mémorisée exprès : la suite de tests la repointe, et une valeur figée à
        l'import écrirait dans l'arbre du dépôt depuis un test.
        """
        return Path(settings.ORDONNANCE_MEDIA_ROOT)

    def _prefixe(self) -> Path:
        """`<racine>/<alias du locataire lié>` — et **lève** quand rien n'est lié.

        `current_alias()` lève `NoTenantBound`. C'est le même échec fermé que le
        routeur : servir depuis une racine par défaut serait ici l'exact équivalent du
        `return None` qui fait retomber une requête sur la base du plan de contrôle.
        """
        return self.racine / current_alias()

    def _chemin(self, nom) -> Path:
        """Le chemin absolu d'un nom **relatif au locataire**, ou un refus.

        Trois contrôles, et ils ne font pas double emploi :

        1. `validate_file_name(..., allow_relative_path=True)` — le contrôle du cadre,
           qui refuse un chemin absolu et tout composant `..`. `Storage.save()`
           l'appelle déjà ; `Storage.open()` **ne l'appelle pas**, donc il est écrit
           ici pour que la lecture soit gardée comme l'écriture ;
        2. le dossier doit être un numéro de version, donc une suite de chiffres ;
        3. `is_relative_to(prefixe)` après résolution — le filet contre ce que les deux
           premiers ne voient pas, un lien symbolique par exemple.
        """
        nom = str(nom)
        validate_file_name(nom, allow_relative_path=True)

        dossier = Path(nom).parent
        if str(dossier) not in (".", "") and not _DOSSIER.match(str(dossier)):
            raise SuspiciousFileOperation(
                f"Le dossier {str(dossier)!r} n'est pas un numéro de version. Le seul "
                "segment de chemin qu'une photo porte est la version de l'ordonnance."
            )

        prefixe = self._prefixe()
        candidat = (prefixe / nom).resolve()
        if not candidat.is_relative_to(prefixe.resolve()):
            raise SuspiciousFileOperation(
                f"Le nom {nom!r} sort de l'arborescence du locataire lié. Un chemin "
                "n'est jamais résolu depuis la ligne : le préfixe vient du contexte."
            )
        return candidat

    # ----------------------------------------------------------------------------------
    # L'interface Storage
    # ----------------------------------------------------------------------------------
    def get_available_name(self, name, max_length=None) -> str:
        """Le nom est **fabriqué** : `<version>/<uuid4>.<ext>`. Jamais celui reçu.

        Fabriqué **ici**, dans le stockage, et non seulement dans le service appelant.
        La différence est la garantie : un futur appelant qui écrirait
        `ordonnance.photo.save(fichier.name, fichier)` — la forme la plus naturelle du
        monde — persisterait sinon `ordonnance_benali_ahmed.jpg`, donc le nom du
        patient, sur le disque et dans une colonne. Le nom reçu ne sert qu'à deux
        choses : son dossier (la version) et son extension.

        Un `uuid4` plutôt qu'une recherche de nom libre : la boucle de
        `Storage.get_available_name` interroge `exists()`, donc le disque, et sur 122
        bits d'aléa la collision n'est pas la chose à défendre.
        """
        nom = str(name).replace("\\", "/")
        dossier = Path(nom).parent
        extension = "".join(Path(nom).suffixes[-1:]).lower()
        fabrique = f"{uuid.uuid4().hex}{extension}"
        return fabrique if str(dossier) in (".", "") else f"{dossier}/{fabrique}"

    def _save(self, name, content) -> str:
        chemin = self._chemin(name)
        # 0700 sur les répertoires, 0600 sur les fichiers : une photo d'ordonnance est
        # une donnée de santé au repos, et le umask par défaut ne l'est pas.
        chemin.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with open(chemin, "wb") as sortie:
            for bloc in content.chunks():
                sortie.write(bloc)
        chemin.chmod(0o600)
        return str(name).replace("\\", "/")

    def _open(self, name, mode="rb") -> File:
        return File(open(self._chemin(name), mode), name=name)

    def exists(self, name) -> bool:
        return self._chemin(name).exists()

    def size(self, name) -> int:
        return self._chemin(name).stat().st_size

    def path(self, name) -> str:
        """Le chemin sur le disque. **Serveur seulement** — jamais une réponse HTTP.

        Implémenté parce que `Storage.path()` lève par défaut et qu'un chemin local est
        ce dont une vérification d'intégrité, une sauvegarde et un test ont besoin. Il
        n'est rendu à personne : ce qui sort d'une vue, ce sont des octets.
        """
        return str(self._chemin(name))

    def delete(self, name):
        """Refusé. Une photo est une pièce justificative, pas un brouillon.

        Une version d'ordonnance est immuable (CLIENT-06) et sa photo s'attache une
        fois (`04-UI-SPEC.md` §22.3, décision §28-Q5). Une photo posée sur la mauvaise
        version se corrige par une **nouvelle version**, comme tout le reste. Lever ici
        plutôt que ne rien écrire : le message atteint celui qui l'appellera.
        """
        raise NotImplementedError(
            "Une photo d'ordonnance ne s'efface pas. Elle justifie un remboursement AMO "
            "et une donnée clinique dix ans en arrière (art. 211 CGI). Pour corriger, "
            "enregistrez une nouvelle version."
        )

    def url(self, name):
        """Refusé, et le message est la décision.

        Les octets de cette photo ne sortent que par une vue qui a **déjà résolu**
        `ordonnance.voir`. Il n'existe aucune adresse directe, aucun service de fichiers
        statiques et aucune adresse pré-signée : une adresse qui contournerait la
        permission ferait de la couche de projection un théâtre.

        Une méthode qui lève est plus solide qu'une méthode absente — celle-ci porte son
        explication jusqu'à celui qui l'appelle, au lieu de le laisser devant le
        `NotImplementedError` générique de la classe de base.

        L'échappatoire, si le passage des octets par Python devenait coûteux, est
        `X-Accel-Redirect` depuis un emplacement interne, **après** la vérification du
        droit. Elle est consignée ici, pas construite.
        """
        raise NotImplementedError(
            "Une photo d'ordonnance n'a pas d'adresse directe. Les octets passent par "
            "GET /api/ordonnances/<id>/photo/, qui resout ordonnance.voir d'abord."
        )


def stockage_des_photos() -> Storage:
    """Le back-end configuré. **Appelé une fois**, à la construction du champ.

    Et c'est correct, pour la seule chose que cet appelable décide : quel back-end. Ce
    qu'il ne décide pas — quel locataire — est redérivé dans chaque méthode de la
    classe. Voir l'en-tête du module.

    Même précédent que `plateforme/control_plane/storage.py::get_storage()`, au réglage
    près : `import_string(settings.ORDONNANCE_STORAGE)`.
    """
    return import_string(settings.ORDONNANCE_STORAGE)()
