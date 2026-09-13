# Restore runbook — one client, one database

**Who this is for:** the operator restoring a single optician's data, probably under
pressure, probably at an awkward hour.

**The one thing to know before you start:** the restore does **not** overwrite the live
database. It restores into a new one beside it and leaves the old one alone. Nothing is
destroyed until you explicitly drop the old database yourself, which is a separate step
you take days later, not now.

TENANT-09 requires this to have been *performed and verified, not assumed*. It has been —
see "The drill" at the bottom.

---

## 0. Before you touch anything

```bash
manage.py shell -c "
from plateforme.control_plane.models import Client, BackupRun
c = Client.objects.using('default').get(code='OPT001')
print(c.code, c.status, c.db_name, c.db_host, c.schema_digest)
for r in BackupRun.objects.using('default').filter(client=c).order_by('-started_at')[:10]:
    print(r.pk, r.started_at, r.status, r.bytes, r.schema_digest, r.object_key)
"
```

Or the same thing in the operator admin, under **Backup runs**, filtered by client.

Pick a run with `status = ok` and a **`schema_digest` equal to the client's current one**.
If it is not equal, read step 3 before going further.

---

## 1. Restore, without cutting over

```bash
manage.py restore_client --code OPT001 --backup 4218
```

This does, in order, and stops at the first thing that is wrong:

1. Refuses if the backup belongs to a different client. (A `--code` typo during an
   incident is the likeliest mistake anyone makes here, and restoring another optician's
   data into this database would be a cross-client leak.)
2. Refuses if the dump's `schema_digest` differs from the client's — see step 3.
3. Downloads the artifact and verifies its `sha256` against the recorded value. A
   corrupted or substituted archive fails **here**, before anything is created, rather
   than halfway through `pg_restore`.
4. **Creates the client's role if it is absent.** ← *this is the step everyone forgets*
5. Creates a **new** database, `optique_c000047_restore_20260913T1912Z`.
6. Runs `pg_restore --exit-on-error`, connected as the client's own role.
7. Prints `tenant_checksum` of the restored database.

It prints the restored database name and the digest. **The live database has not been
touched.** Both databases now exist.

Each invocation creates **its own** restore database and refuses to reuse an existing one
— restoring into a populated database aborts partway and leaves something that looks
restored. So running step 1 and then step 4 leaves two restore databases, both retained.
That is deliberate; drop the one you did not keep (step 6). If the database is large
enough that restoring twice is not acceptable, skip step 1 and go straight to `--cutover`,
which performs the same verification and prints the digest **before** it switches.

### Why step 4 is called out

`pg_dump` dumps **a single database**. Roles are cluster-wide and are **not in the dump**.
On a fresh PostgreSQL instance — which is what a real disaster recovery means — a restore
without this step succeeds, produces a perfectly good database, and nobody can connect to
it. It is the single most commonly missed step in logical restore. It has its own test
(`test_tenant09_restore_creates_the_role_when_it_is_absent`), which asserts the restored
database is *connectable as that role*, not merely that the role exists.

There is a second half to the same problem, and it is why the restore connects as the
client's role rather than as the superuser: `pg_restore --no-owner` strips the ownership
statements, so every object ends up owned by whoever ran the restore. Restore as
`postgres` and the client's role gets `permission denied for table stock_mouvementstock`
on a database it supposedly owns.

---

## 2. Verify, before cutting over

```bash
manage.py tenant_checksum --code OPT001                    # the LIVE database
manage.py tenant_checksum --alias tenant_47_restore        # printed by step 1
```

An ordered per-table `md5` folded into one `sha256`, including `pg_sequences.last_value`.
**Row counts are not verification** — they match while every column value is wrong.

If they differ (they normally will; that is usually the point — the live database has
drifted since the backup), localise it:

```bash
manage.py tenant_checksum --code OPT001 --detail
```

`__sequences__` differing on its own means the data matches but the counters do not. Do
not cut over to that: Phase 6's facture numbering depends on counters, and a database with
rewound sequences will re-issue numbers that already exist.

---

## 3. If the schema versions do not match

The restore refuses, and `--force` overrides it.

A digest is only comparable **within one schema version**: a column added by a later
migration changes every table's digest, so verification across versions is meaningless
rather than merely noisy.

The usual right answer is not `--force`. It is:

1. restore without cutover (`--force` to get the database created),
2. run `manage.py migrate_all --client OPT001` **after** cutover to bring the restored
   database up to the code's head,
3. verify afterwards, against the new schema, not the old one.

---

## 4. Cut over

```bash
manage.py restore_client --code OPT001 --backup 4218 --cutover
```

Cutover is a single transactional `UPDATE` of `Client.db_name` on the control plane, plus
`evict_alias` so no worker keeps using the old connection. **The control-plane row is the
switch.** That is what makes this reversible.

The old database is **retained**. Write its name down; the command prints it.

---

## 5. Rolling back

Point `Client.db_name` at the old database again. That is the whole of it.

```bash
manage.py shell -c "
from plateforme.control_plane.models import Client
from plateforme.tenancy.registry import alias_for, evict_alias
c = Client.objects.using('default').get(code='OPT001')
Client.objects.using('default').filter(pk=c.pk).update(db_name='optique_c000047')
try:
    evict_alias(alias_for(c.pk))
except Exception:
    pass
print('rolled back to', 'optique_c000047')
"
```

---

## 6. Dropping the old database — days later, not today

Only once the client has used the restored database and confirmed it is right.

```bash
manage.py shell -c "
from plateforme.tenancy.maintenance import drop_database_force, maintenance_connection
with maintenance_connection() as cur:
    drop_database_force(cur, 'optique_c000047')   # the EXACT name, typed by hand
"
```

`reap_orphan_databases` will **not** do this for you, deliberately: a
`..._restore_<timestamp>` name does not match the shape it recognises, so it can never
drop a restore that is in flight or awaiting acceptance. Dropping is a decision, not
housekeeping.

> **Do not write a loop over a prefix to tidy up.** `_` is a single-character wildcard in
> SQL `LIKE`, so `datname LIKE 'optique_c%'` matches **`optique_control`** — the control
> plane itself — and `str.startswith('optique_c')` has the same blind spot. That is not a
> hypothetical: it is why `reap_orphan_databases` matches on prefix **plus exactly six
> digits** (`is_client_database_name`), and it caught out an ad-hoc cleanup script during
> this very phase, minutes after the command was fixed. Type the exact name.

---

## The drill has been run

Not a plan. `test_tenant09_single_client_restore_produces_identical_data`:

- provisions **two** real clients on one PostgreSQL instance and seeds each with
  distinguishable data;
- records `tenant_checksum` of both;
- backs up client A;
- **mutates A afterwards** — deletes a row, changes a column, inserts a row — so a
  `restore_client` that did nothing at all cannot pass, and asserts the mutation moved the
  digest before going on;
- restores A with `--cutover`;
- asserts `tenant_checksum(A) == before_A` — the data really came back, not merely that
  `pg_restore` exited 0;
- asserts `tenant_checksum(B) == before_B` — **the neighbour was untouched.**

That last assertion is the one that makes this a *per-database* restore rather than a
per-instance one, which is exactly what TENANT-09 says PITR does not satisfy: B shares an
instance with A, so a server-level restore would have moved B's digest too.

Measured on the development stack (Compose, PostgreSQL 18.6, an empty client schema):
backup ~0.1 s producing a ~14 KB archive, restore including database creation and
verification ~0.6 s. **These numbers say nothing about a real client**, whose database
will be gigabytes and whose restore time scales with index count, because `pg_restore`
rebuilds indexes rather than copying them. Re-measure against a real dataset before
quoting an RTO to anyone.

---

## Open questions for Phase 1 procurement

Recorded here because the operator running this is the person who will hit them, and
because none of them blocks Phase 2 — this implementation is deliberately
provider-independent.

1. **Does the managed provider's application role have `CREATEDB`?** If not,
   `SqlProvisioner` is replaced by an API-based implementation of the two-method
   `DatabaseProvisioner` interface. Step 5 above changes; nothing else does.
   (`02-RESEARCH.md` Open Question 2 — the highest-value unknown in the phase.)
2. **Is there a cap on logical databases per instance?** It sets the sharding point.
   `Client.db_host` exists from day one so that sharding is a data change.
   (Open Question 3.)
3. **Object storage must be EU-resident and encrypted at rest.** A dump is a complete copy
   of one optician's ordonnances — health data under law 09-08. Gated on the LEGAL-02
   hosting-jurisdiction decision. Until then `BACKUP_STORAGE` is a local filesystem and is
   honest about being development-only.
4. **Retention is a legal question, not a technical one.** Art. 211 CGI's ten years is a
   *records* obligation, not a backup-rotation obligation; conflating them makes storage
   cost explode and over-collects personal data. `BACKUP_RETENTION` is a setting with a
   defensible default and **pruning is deliberately not implemented** until a lawyer
   confirms the policy. A rotation task written against a guessed policy deletes things.
   (`02-RESEARCH.md` assumption A5.)
