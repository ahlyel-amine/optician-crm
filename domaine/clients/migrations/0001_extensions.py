"""Les deux extensions PostgreSQL de CLIENT-10, dans chaque base client.

Trois faits décident de l'existence de ce fichier, et aucun n'est une préférence.

1. **Migration, et non provisionnement.** `provision_client()` rend la main tôt sur
   `status == ACTIVE` — il n'existe aucun chemin qui rejoue le provisionnement d'un
   client déjà actif. Une extension créée au provisionnement existerait donc chez les
   clients provisionnés *après* ce changement et chez personne d'autre, y compris les
   deux bases de développement d'aujourd'hui. `migrate_all` est le seul mécanisme du
   produit qui atteigne chaque client existant et qui **rapporte** qui a échoué et qui
   est en retard (TENANT-02, TENANT-03).

2. **Le privilège requis est la propriété de la base, pas un attribut de rôle.**
   Mesuré sur PostgreSQL 18.6 : `pg_trgm` et `fuzzystrmatch` sont *trusted*, donc
   `CREATE EXTENSION` demande `CREATE` sur la base et sur le schéma cible, pas
   `SUPERUSER` ; et `SqlProvisioner.create_database` émet
   `CREATE DATABASE … OWNER <rôle du client>`, ce qui donne exactement ce privilège.
   **La condition qui invalide ceci**, en une phrase : un hébergeur géré qui livrerait un
   rôle applicatif **non propriétaire** de la base (`02-RESEARCH.md` question ouverte 2,
   toujours ouverte). Le mode d'échec serait alors bruyant — `migrate_all` rapporte par
   client — et non silencieux.

3. **La DDL ne passe pas par PgBouncer**, et rien n'est à faire ici pour cela :
   `migrate_all` migre avec `client.connection_params(direct=True)`, qui substitue
   `PG_ADMIN_HOST` / `PG_ADMIN_PORT`. C'est écrit pour que personne n'ajoute un
   contournement dont il n'y a pas besoin.

**Ces deux extensions sont la liste entière, et la troisième que `04-CONTEXT.md` zone
grise 4 proposait a été écartée par la mesure** (`04-RESEARCH.md` §5.3) : elle est
`STABLE`, donc PostgreSQL refuse de l'employer dans une expression d'index — `42P17`,
colonne générée comprise — et l'enveloppe `IMMUTABLE` que la communauté écrit pour la
contourner est un mensonge sur la volatilité, qu'il faudrait en plus doter d'un
`REVOKE EXECUTE … FROM PUBLIC` et de son test (CLAUDE.md #12).
`normaliser_pour_recherche`, dans `domaine/clients/recherche.py`, rend le même service en
Python, immuable par construction, et réduit d'un tiers la surface à prouver sur trois
cents bases. **Le raisonnement complet, extension nommée, est dans la docstring de cette
fonction** — il n'est pas répété ici parce que la garde G3 de `04-VALIDATION.md` cherche
ce nom, littéralement, dans ce fichier.

`CreateExtension.database_forwards` appelle `router.allow_migrate(alias, app_label)` sans
`model_name` ; `TenantRouter.allow_migrate` accepte cette signature et rend
`is_tenant_alias(db)` pour une application métier. L'extension va donc sur les alias
client et **jamais** sur `default` — ce que
`test_client10_aucune_extension_metier_n_atterrit_sur_default` tient.
"""

from django.contrib.postgres.operations import CreateExtension
from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        # Le rappel indexé par trigramme (couche 2 de la recherche). Le seul moyen
        # d'obtenir une correspondance floue *indexée* : l'opérateur `<%` est servi par un
        # index GIN `gin_trgm_ops`, mesuré à 4,3 ms sur 20 400 lignes.
        CreateExtension("pg_trgm"),
        # `metaphone()`, qui est `IMMUTABLE` donc indexable sur un btree ordinaire. C'est
        # la couche 3, et la seule qui rapproche `Mhamed` de `Mohammed` — mesuré, aucun
        # seuil de trigramme ne le fait sans rapprocher aussi Fatima de Fatiha.
        CreateExtension("fuzzystrmatch"),
    ]
