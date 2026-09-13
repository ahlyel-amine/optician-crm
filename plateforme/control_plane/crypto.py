"""Fernet encryption of the client database password.

Nothing here is hand-rolled, deliberately. `02-RESEARCH.md` § Don't Hand-Roll: this is a
credential for a database holding ordonnances, which are health data under law 09-08. A
byte-mixing trick, a base64 round-trip and a bespoke AES wrapper all *look* like
encryption in a code review, and all three fail the moment they matter.
`cryptography.fernet` gives authenticated encryption (AES-128-CBC plus HMAC-SHA256) and,
through `MultiFernet`, key rotation without a schema migration.

`MultiFernet` is used even when there is only one key. Rotation then costs an environment
change rather than a code change: prepend the new key to `TENANCY_FERNET_KEY` and every
existing token still decrypts with the old one, which stays in the list until
`MultiFernet.rotate()` has been run over the table.

The key lives in the environment, never in the database and never in git — an attacker who
reads the control-plane table must not thereby hold every client's database password
(threat T-02-07).
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@lru_cache(maxsize=4)
def _build(key_spec: str) -> MultiFernet:
    keys = [part.strip() for part in key_spec.split(",") if part.strip()]
    try:
        return MultiFernet([Fernet(key) for key in keys])
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(
            "TENANCY_FERNET_KEY is not a valid Fernet key (or comma-separated list of "
            "them). Generate one with: python -c \"from cryptography.fernet import "
            'Fernet; print(Fernet.generate_key().decode())"'
        ) from exc


def _fernet() -> MultiFernet:
    """The first key encrypts; every key in the list can decrypt. That is rotation."""
    key_spec = getattr(settings, "TENANCY_FERNET_KEY", "") or ""
    if not key_spec.strip():
        raise ImproperlyConfigured(
            "TENANCY_FERNET_KEY is empty. Without it a client database password would "
            "have to be stored in plaintext beside the host and user that reach the "
            "database it opens. Refusing to run."
        )
    return _build(key_spec)


def encrypt(plaintext: str) -> bytes:
    """Encrypt a database password for storage in `Client.db_password_encrypted`."""
    if not isinstance(plaintext, str):
        raise TypeError("encrypt() takes str; pass the password, not bytes or a model.")
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt(token: bytes) -> str:
    """Decrypt a stored token. Raises `cryptography.fernet.InvalidToken` if tampered.

    That exception is a feature: Fernet is authenticated, so a row edited directly in
    the control-plane database fails loudly instead of yielding attacker-chosen bytes.
    """
    return _fernet().decrypt(bytes(token)).decode("utf-8")
