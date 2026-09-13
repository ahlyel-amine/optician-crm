"""Where dump artifacts go. Two methods, behind an interface, for a procurement reason.

The same reasoning as `DatabaseProvisioner`: the object-storage provider is a **Phase 1
procurement decision** and it is not made yet. An interface now makes an S3-compatible
implementation a small change; a `boto3` call inlined into `backup.py` would make it a
rewrite of the backup path.

`LocalFilesystemStorage` is the default and is honest about being development-only. It is
deliberately *not* a plausible-looking bucket with a placeholder name, because that is the
shape of thing that gets shipped.

**Production storage must be EU-resident and encrypted at rest.** A dump of a client
database is a complete copy of one optician's ordonnances — health data under law 09-08 —
and its protection is not the database's protection (threat T-02-45). That requirement is
gated on the Phase 1 LEGAL-02 hosting-jurisdiction decision.
"""

from __future__ import annotations

import abc
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.utils.module_loading import import_string


class BackupStorage(abc.ABC):
    """Put an artifact somewhere durable; get it back."""

    @abc.abstractmethod
    def put(self, local_path, key: str) -> str:
        """Store `local_path` under `key`. Returns the key actually used."""

    @abc.abstractmethod
    def get(self, key: str, local_path) -> Path:
        """Fetch `key` to `local_path`, or to a fresh temporary file when it is None."""


class LocalFilesystemStorage(BackupStorage):
    """Artifacts under `settings.BACKUP_LOCAL_ROOT`. Development and CI only.

    `/backups/` and `*.dump` are gitignored (plan 02-01), which is a guard against
    committing health data, not housekeeping.
    """

    @property
    def root(self) -> Path:
        return Path(settings.BACKUP_LOCAL_ROOT)

    def _path(self, key: str) -> Path:
        # `key` is composed by `backup.object_key_for`, from a client code and a
        # timestamp, never from request input. Resolving and re-checking anyway, because
        # the cost is one comparison and the failure mode is a write outside the root.
        candidate = (self.root / key).resolve()
        root = self.root.resolve()
        if not candidate.is_relative_to(root):
            raise ValueError(f"Backup key {key!r} escapes {root}.")
        return candidate

    def put(self, local_path, key: str) -> str:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local_path, target)
        # 0600: the artifact is health data at rest, and the default umask is not.
        target.chmod(0o600)
        return key

    def get(self, key: str, local_path) -> Path:
        source = self._path(key)
        if not source.exists():
            raise FileNotFoundError(f"No backup artifact at {key!r}.")
        if local_path is None:
            handle = tempfile.NamedTemporaryFile(suffix=".dump", delete=False)
            handle.close()
            local_path = handle.name
        shutil.copyfile(source, local_path)
        Path(local_path).chmod(0o600)
        return Path(local_path)


def get_storage() -> BackupStorage:
    """The configured storage backend, `LocalFilesystemStorage` unless overridden."""
    return import_string(settings.BACKUP_STORAGE)()
