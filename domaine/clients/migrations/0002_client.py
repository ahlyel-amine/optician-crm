"""La table `clients_client`, et l'index GIN qui a besoin d'une extension.

**La dépendance sur `0001_extensions` est explicite et load-bearing.** Django applique
les migrations d'une application dans l'ordre de leurs dépendances ; sans celle-ci, la
création de l'index `gin_trgm_ops` courrait contre la création de `pg_trgm` sur une base
neuve, et la course se perdrait silencieusement selon l'ordre du graphe. Sur les bases
déjà migrées le problème ne se verrait jamais — c'est-à-dire qu'il n'apparaîtrait que
chez le prochain client provisionné.

Fichier renommé à la main en `0002_client` : `makemigrations` l'avait nommé
`0002_initial`, ce qui est exact du point de vue de Django (aucun modèle avant lui) et
trompeur du point de vue d'un lecteur, puisque `0001_extensions` porte déjà
`initial = True`.
"""

import django.contrib.postgres.indexes
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("clients", "0001_extensions"),
    ]

    operations = [
        migrations.CreateModel(
            name='Client',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=160)),
                ('nom_recherche', models.CharField(editable=False, max_length=160)),
                ('cle_phonetique', models.CharField(blank=True, editable=False, max_length=16)),
                ('telephone', models.CharField(blank=True, max_length=30)),
                ('telephone_normalise', models.CharField(blank=True, db_index=True, editable=False, max_length=24)),
                ('date_naissance', models.DateField(blank=True, null=True)),
                ('adresse', models.TextField(blank=True)),
                ('notes', models.TextField(blank=True)),
                ('actif', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'client',
                'verbose_name_plural': 'clients',
                'ordering': ['nom'],
                'indexes': [django.contrib.postgres.indexes.GinIndex(django.contrib.postgres.indexes.OpClass(models.F('nom_recherche'), name='gin_trgm_ops'), name='idx_client_nom_trgm'), models.Index(condition=models.Q(('cle_phonetique', ''), _negated=True), fields=['cle_phonetique'], name='idx_client_phonetique'), models.Index(fields=['nom'], name='idx_client_nom')],
            },
        ),
    ]
