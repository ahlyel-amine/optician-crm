"""TENANT-09 — per-client logical backup and verified single-client restore.

The requirement is explicit that per-instance PITR does not satisfy it: *"restoring one
client's logical database alone has been performed and verified — not assumed. Per-instance
PITR that only restores a whole server does not satisfy this, because many client databases
share one instance."* So this is implemented here, provider-independent. Two further
reasons: a provider feature can only ever be *assumed* to work, and keeping it
provider-independent stops the Phase 1 hosting decision from becoming a hard dependency of
Phase 2.

Everything here goes **direct to PostgreSQL**, never through PgBouncer: `pg_dump` needs a
session it owns end to end, and `pg_restore` runs DDL.

**Subprocesses are invoked with an argument list and never through a shell** — the
`subprocess.run` keyword that would hand the command to `/bin/sh` appears nowhere in this
file, and an acceptance grep enforces that. The password travels in `PGPASSWORD` in the
subprocess environment rather than on the command line, where it would appear in `ps`
output and in shell history (threat T-02-46).
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.connection import ConnectionDoesNotExist

from plateforme.control_plane.models import BackupRun, Client
from plateforme.control_plane.storage import get_storage
from plateforme.tenancy.maintenance import database_exists
from plateforme.tenancy.provisioner import get_provisioner
from plateforme.tenancy.registry import alias_for, evict_alias, register_client_database

#: Read in 1 MiB blocks rather than whole — a dump is arbitrarily large and this runs on a
#: worker alongside everything else.
_HASH_BLOCK = 1024 * 1024


def _timestamp() -> str:
    """`YYYYMMDDTHHMMSSZ`.

    Seconds, not minutes. The research writes `YYYYMMDDTHHMMZ`, and minute granularity is
    wrong in both places it is used: two backups in one minute would overwrite each
    other's artifact — leaving a `BackupRun` row pointing at another run's data, in the
    table whose whole purpose is to be auditable — and two restores in one minute would
    collide on the target database name. Both were observed, not theorised; see
    `restore_client`.
    """
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def object_key_for(client: Client, stamp: str, run_pk: int) -> str:
    """`client/<code>/<YYYY>/<YYYYMMDDTHHMMSSZ>-<run_pk>.dump`.

    Grouped by client then year, so "every backup for this optician" and "everything older
    than N years" are both a prefix listing rather than a scan.

    The `BackupRun` primary key is in the name so a key is unique by construction rather
    than by assuming no two dumps of one client start in the same second. An artifact
    silently overwritten by a later run is the worst kind of backup bug: the audit row
    still says `ok`, and it points at somebody else's snapshot.
    """
    return f"client/{client.code}/{stamp[:4]}/{stamp}-{run_pk}.dump"


def _sha256(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(_HASH_BLOCK), b""):
            digest.update(block)
    return digest.hexdigest()


def _pg_env(password: str) -> dict:
    """A subprocess environment carrying the password, never a command line carrying it.

    `PGPASSWORD` rather than `--password` or a URI: the command line of a running process
    is readable by anyone via `ps`, and it lands in shell history (threat T-02-46).
    """
    env = dict(os.environ)
    env["PGPASSWORD"] = password
    return env


def backup_client(client_id: int) -> BackupRun:
    """Dump one client's database, upload it, and record the attempt. TENANT-09.

    The `BackupRun` row is created **first**, in `running`, so a crash mid-dump leaves a
    row that never finished rather than leaving nothing — and nobody notices an absence.

    **What this artifact does NOT cover, written down rather than discovered later.**
    This produces one `pg_dump` and nothing else, so anything a client owns *outside*
    its database is outside TENANT-09's promise. As of Phase 4 that is the ordonnance
    photograph store (`domaine/ordonnances/stockage.py`): restoring this dump alone
    gives back every row, including the stored path of each photo, and **none of the
    image files**. Recorded as **D-4-1** in
    `.planning/phases/04-clients-ordonnances/deferred-items.md`, with the reason the
    artifact was not extended in Phase 4 and who picks it up.
    """
    client = Client.objects.using("default").get(pk=client_id)
    stamp = _timestamp()
    run = BackupRun.objects.using("default").create(
        client=client,
        status=BackupRun.RUNNING,
        schema_digest=client.schema_digest,
    )
    run.object_key = object_key_for(client, stamp, run.pk)
    run.save(using="default", update_fields=["object_key"])

    handle = tempfile.NamedTemporaryFile(suffix=".dump", delete=False)
    handle.close()
    tmp = Path(handle.name)
    try:
        command = [
            settings.PG_DUMP_BIN,
            f"--host={settings.PG_ADMIN_HOST}",
            f"--port={settings.PG_ADMIN_PORT}",
            f"--username={settings.PG_ADMIN_USER}",
            f"--dbname={client.db_name}",
            # Custom format: selective restore, index rebuilding, and a table of contents
            # `pg_restore --list` can parse — which is how "a valid archive" is checked.
            "--format=custom",
            f"--compress={settings.BACKUP_COMPRESSION}",
            # Both matter for a real reason: the restore target may be a different role,
            # and without them pg_restore emits ALTER OWNER statements that fail.
            "--no-owner",
            "--no-privileges",
            f"--file={tmp}",
        ]
        result = subprocess.run(
            command,
            env=_pg_env(settings.PG_ADMIN_PASSWORD),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"pg_dump exited {result.returncode} for {client.db_name}: "
                f"{result.stderr.strip()[:1000]}"
            )

        size = tmp.stat().st_size
        if size == 0:
            raise RuntimeError(f"pg_dump wrote an empty file for {client.db_name}.")

        digest = _sha256(tmp)
        key = get_storage().put(tmp, run.object_key)

        BackupRun.objects.using("default").filter(pk=run.pk).update(
            status=BackupRun.OK,
            finished_at=timezone.now(),
            bytes=size,
            sha256=digest,
            object_key=key,
            error="",
        )
        run.refresh_from_db(using="default")
        return run
    except Exception as exc:
        BackupRun.objects.using("default").filter(pk=run.pk).update(
            status=BackupRun.FAILED,
            finished_at=timezone.now(),
            error=repr(exc)[:2000],
        )
        run.refresh_from_db(using="default")
        raise
    finally:
        # A dump of a client database is health data at rest. /tmp is world-readable on
        # most systems and survives the process (threat T-02-45). Removed on every path,
        # including the failure path — which is what a finally is for.
        tmp.unlink(missing_ok=True)


# --------------------------------------------------------------------------------------
# Restore
# --------------------------------------------------------------------------------------
class RestoreRefused(RuntimeError):
    """The restore was stopped before it touched anything."""


def restore_target_name(client: Client, stamp: str | None = None) -> str:
    """`<db_name>_restore_<YYYYMMDDTHHMMSSZ>` — **never** `db_name` itself.

    Restoring in place over a live database is irreversible; restoring beside it is not.
    The control-plane row is the switch (threat T-02-43).

    The name deliberately does not match `is_client_database_name`, so
    `reap_orphan_databases` can never drop a restore that is in flight or awaiting
    acceptance.
    """
    return f"{client.db_name}_restore_{stamp or _timestamp()}"


def restore_client(
    client: Client,
    backup_run: BackupRun,
    *,
    cutover: bool = False,
    force: bool = False,
    stdout=None,
) -> dict:
    """Restore one client's database beside the live one, verify it, optionally cut over.

    The order is the procedure, and every step earns its place:

    1. **Schema-version check.** A `tenant_checksum` is only comparable within one schema
       version, because a column added by a later migration changes every table's digest.
       Refuse on a mismatch unless `force` (threat T-02-48).
    2. **Download and verify `sha256`.** A corrupted or substituted archive must fail here
       rather than halfway through `pg_restore` (threat T-02-49).
    3. **`create_role_if_absent`.** `pg_dump` dumps a single database; roles are
       cluster-wide and are not in it. Without this, a restore onto a fresh instance
       succeeds and then nothing can connect — the single most commonly missed step in
       logical restore (Pitfall 10, threat T-02-47). Through the provisioner, so an
       API-based implementation works too.
    4. **Create a new database**, never the live one.
    5. **`pg_restore --exit-on-error`.** The default is to continue past errors and report
       at the end, which produces a partially restored database that looks successful
       (threat T-02-44).
    6. **Verify with `tenant_checksum` *before* any cutover**, not after.
    7. **Cut over only when asked**: one transactional `UPDATE` of `Client.db_name`, plus
       `evict_alias` so no worker keeps using the old connection.

    Returns a dict with `restored_db`, `checksum`, `cutover`, `previous_db`.
    """
    from plateforme.control_plane.checksum import tenant_checksum

    def _say(line):
        if stdout is not None:
            stdout.write(line)

    if backup_run.client_id != client.pk:
        raise RestoreRefused(
            f"Backup {backup_run.pk} belongs to client {backup_run.client_id}, not to "
            f"{client.code}. Restoring another client's data into this database would be "
            "a cross-client leak, not a mistake to warn about."
        )

    # 1. Schema version.
    if backup_run.schema_digest != client.schema_digest and not force:
        raise RestoreRefused(
            f"The dump was taken at schema {backup_run.schema_digest[:12] or '(none)'} "
            f"but {client.code} is now at {client.schema_digest[:12] or '(none)'}. "
            "Checksums are only comparable within one schema version, so verification "
            "would be meaningless. Pass --force if you have decided that is acceptable."
        )

    # 2. Download and verify the artifact.
    local = get_storage().get(backup_run.object_key, None)
    try:
        if backup_run.sha256:
            actual = _sha256(local)
            if actual != backup_run.sha256:
                raise RestoreRefused(
                    f"Artifact {backup_run.object_key} hashes to {actual[:12]}, recorded "
                    f"as {backup_run.sha256[:12]}. It is corrupted or substituted; "
                    "nothing has been restored."
                )

        provisioner = get_provisioner()
        with maintenance() as cur:
            # 3. The role. Cluster-wide, not in the dump.
            create_role = getattr(provisioner, "create_role_if_absent", None)
            if create_role is not None:
                create_role(cur, user=client.db_user, password=client.db_password)

            # 4. A NEW database, beside the live one — and it must genuinely be new.
            #
            # `create_database` is guarded by an existence check, which is right for
            # provisioning (a killed run must adopt the database it already created) and
            # wrong here: adopting a populated database means `pg_restore` runs into
            # existing objects, and with --exit-on-error it aborts partway, leaving a
            # half-restored database behind. Observed during this plan's own drill, on
            # exactly the flow the runbook prescribes — restore to verify, then restore
            # again to cut over, both within the same timestamp.
            target = restore_target_name(client)
            if database_exists(cur, target):
                raise RestoreRefused(
                    f"{target} already exists. A restore must create its own database; "
                    "restoring into a populated one aborts partway and leaves something "
                    "that looks restored. Drop it first, or wait a second and retry."
                )
            provisioner.create_database(cur, name=target, owner=client.db_user)
        _say(f"restoring into {target}")

        # 5. pg_restore, **connected as the client's own role**.
        #
        # This is what `--no-owner` costs, and it is not optional. `--no-owner` strips the
        # ALTER OWNER statements — necessary, because the dump names an owner that may not
        # exist on the restore target — but it means every object ends up owned by
        # whoever ran the restore. Restoring as the superuser therefore produces a
        # database the client's own role can connect to and cannot read:
        #     psycopg.errors.InsufficientPrivilege: permission denied for table
        #     stock_mouvementstock
        # Observed, not anticipated. Connecting as `client.db_user` makes it the owner of
        # every restored object, which is also what `migrate` produces during provisioning,
        # so a restored database is indistinguishable from a provisioned one. It is
        # least-privilege as a side effect rather than as the reason.
        #
        # The role owns the target database, and since PostgreSQL 15 the `public` schema
        # belongs to `pg_database_owner`, so it has the rights to create in it.
        command = [
            settings.PG_RESTORE_BIN,
            f"--host={settings.PG_ADMIN_HOST}",
            f"--port={settings.PG_ADMIN_PORT}",
            f"--username={client.db_user}",
            f"--dbname={target}",
            "--no-owner",
            "--no-privileges",
            # The default is to continue past errors and report at the end, which produces
            # a partially restored database that looks successful (threat T-02-44).
            "--exit-on-error",
            "--jobs=4",
            str(local),
        ]
        result = subprocess.run(
            command,
            env=_pg_env(client.db_password),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"pg_restore exited {result.returncode} into {target}: "
                f"{result.stderr.strip()[:2000]}"
            )

        # 6. Verify BEFORE cutover.
        probe_alias = f"{alias_for(client.pk)}_restore"
        register_client_database(
            alias=probe_alias,
            name=target,
            host=settings.PG_ADMIN_HOST,
            port=settings.PG_ADMIN_PORT,
            user=client.db_user,
            password=client.db_password,
        )
        digest = tenant_checksum(probe_alias)
        _say(f"tenant_checksum({target}) = {digest}")

        previous = client.db_name
        if cutover:
            # 7. One transactional UPDATE. The control-plane row is the switch, which is
            # what makes the restore reversible: the old database is still there.
            with transaction.atomic(using="default"):
                Client.objects.using("default").filter(pk=client.pk).update(
                    db_name=target
                )
            client.db_name = target
            for alias in (alias_for(client.pk), probe_alias):
                try:
                    evict_alias(alias)
                except (ConnectionDoesNotExist, AttributeError, KeyError):
                    pass
            _say(
                f"cutover: {client.code} now points at {target}. "
                f"The previous database {previous} is RETAINED and must be dropped "
                f"explicitly once you have accepted the restore:\n"
                f"    manage.py shell -c \"...drop {previous}...\"\n"
                f"To roll back, point Client.db_name at {previous} again."
            )
        else:
            _say(
                f"{target} is restored and verified. No cutover was performed: "
                f"{client.code} still points at {previous}. Re-run with --cutover to "
                "switch."
            )

        return {
            "restored_db": target,
            "checksum": digest,
            "cutover": cutover,
            "previous_db": previous,
        }
    finally:
        # Same reasoning as the dump: the downloaded artifact is health data at rest.
        Path(local).unlink(missing_ok=True)


def maintenance():
    """Indirection so tests can see one import site. Returns `maintenance_connection()`."""
    from plateforme.tenancy.maintenance import maintenance_connection

    return maintenance_connection()
