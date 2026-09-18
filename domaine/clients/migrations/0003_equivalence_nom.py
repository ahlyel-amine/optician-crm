"""La table `clients_equivalencenom` — la couche 4 du rappel, en donnée.

**Le fichier crée la table, jamais son contenu.** L'amorce est écrite par
`plateforme/control_plane/seeding.py`, au point d'extension de `seed_new_client`, en
`get_or_create`. Un `RunPython` de peuplement ici aurait deux défauts : il devrait porter
sa propre garde `allow_migrate` (convention vérifiée par
`tests/test_migration_conventions.py`), et surtout il **figerait l'amorce dans
l'historique** — une ligne ajoutée à la liste six mois plus tard n'atteindrait jamais les
clients déjà migrés, alors que `seed_new_client` est rejouable.

Le revers, écrit pour qu'il ne soit pas découvert : les clients **déjà provisionnés** ne
reçoivent pas l'amorce par `migrate_all`. Ils la recevront au prochain appel de
`seed_new_client`, ou par une commande de reprise. Les couches 1 à 3 fonctionnent sans
elle ; seule la traîne des équivalences curées manque en attendant.

Fichier renommé à la main en `0003_equivalence_nom` : `makemigrations` écrit
`0003_equivalencenom`, qui se lit mal.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("clients", "0002_client"),
    ]

    operations = [
        migrations.CreateModel(
            name="EquivalenceNom",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("forme_normalisee", models.CharField(db_index=True, max_length=80)),
                ("groupe", models.CharField(db_index=True, max_length=80)),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("amorce", "Livrée avec le produit"),
                            ("opticien", "Ajoutée par l'opticien"),
                        ],
                        default="amorce",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "équivalence de nom",
                "verbose_name_plural": "équivalences de noms",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("forme_normalisee", "groupe"),
                        name="unique_forme_dans_un_groupe",
                    )
                ],
            },
        ),
    ]
