from django.apps import AppConfig


class ClientsConfig(AppConfig):
    """Application métier. Son label doit aussi être dans `BUSINESS_APPS` (Pitfall 12).

    **Le label est `clients`, et il désigne la fiche d'une personne qui achète chez
    l'opticien** — pas l'affaire d'un opticien, qui est `control_plane.Client` et vit dans
    la base du plan de contrôle (CLAUDE.md #11). Les deux noms coexistent délibérément :
    renommer l'un des deux « pour lever l'ambiguïté » déplacerait le vocabulaire loin de
    celui du comptoir, où « le client » est la personne en face.
    """

    name = "domaine.clients"
    label = "clients"
    verbose_name = "clients"
