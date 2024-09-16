import json
from pathlib import Path

from joserfc.jwk import KeySet

_CLIENT_KEYSET: KeySet | None = None
_GLOB_TRUSTED_JWKS = "/var/lib/fwapi/data/*.jwk.json"


def reload_public_key_file():
    """Load the public keys from the JWKS configuration path."""

    global _CLIENT_KEYSET
    _CLIENT_KEYSET = KeySet([])

    for jwks in Path("/").glob(_GLOB_TRUSTED_JWKS[1:]):
        with open(jwks, "r") as f:
            data = json.load(f)
            ks = KeySet.import_key_set(data)
            _CLIENT_KEYSET = KeySet([*_CLIENT_KEYSET, *ks])


def public_keys() -> KeySet:
    """Return the KeySet with all registered clients' public keys."""

    if _CLIENT_KEYSET is None:
        reload_public_key_file()
        assert _CLIENT_KEYSET is not None, "Failed to load client public keys"

    return _CLIENT_KEYSET


__all__ = ["public_keys", "reload_public_key_file"]
