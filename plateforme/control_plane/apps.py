from django.apps import AppConfig


class ControlPlaneConfig(AppConfig):
    """The control plane. Its models live on the `default` alias and nowhere else.

    `TenantRouter.allow_migrate` (plan 02-03) pins this app's tables to `default`, and
    the `tenancy.E001` system check refuses to start if any installed app is classified
    as neither control-plane nor business.
    """

    name = "plateforme.control_plane"
    label = "control_plane"
    verbose_name = "Control plane"
