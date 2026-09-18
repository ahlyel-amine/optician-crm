from django.apps import AppConfig


class OrdonnancesConfig(AppConfig):
    """Application métier. Son label doit aussi être dans `BUSINESS_APPS` (Pitfall 12).

    **Les tables de cette application vivent dans la base du client, jamais sur
    `default`.** C'est la classification qui le garantit, pas une intention : une
    ordonnance est une donnée de santé au sens de la loi 09-08, et une seule table
    d'ordonnances posée sur le plan de contrôle mettrait les prescriptions de toute la
    flotte dans une base partagée. `manage.py check` échoue avec `tenancy.E001` tant que
    le label n'est pas classé — c'est ce qui rend l'oubli impossible plutôt
    qu'improbable.
    """

    name = "domaine.ordonnances"
    label = "ordonnances"
    verbose_name = "ordonnances"
