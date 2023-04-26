import datetime
from hashlib import sha256
from typing import TypeAlias

import pymemcache
from pymemcache.client.retrying import RetryingClient
from pymemcache.exceptions import MemcacheUnexpectedCloseError

from .config import FOTOWARE_FIELDNAME_UUID, MEMCACHED_HOST
from .fotoware.apitypes import *
from pymemcache.client.murmur3 import murmur3_32

_Value: TypeAlias = bytes | float | int | str

base_client = pymemcache.Client(
    server=MEMCACHED_HOST,
    allow_unicode_keys=True,
    no_delay=True,
)
MEMCACHED = RetryingClient(
    base_client,
    attempts=5,
    retry_delay=0.01,  # type: ignore
    retry_for=[MemcacheUnexpectedCloseError],
)


def set(name: str, value: _Value, *, expires_in: int | None = 0) -> bool | None:
    """Set a value in the cache, optionally with expiration"""
    return MEMCACHED.set(name, value, expire=expires_in)


def get(name: str, default: None = None) -> bytes | None:
    """Get a value from cache"""
    return MEMCACHED.get(name, default)


def calc_asset_key(
    asset: Asset, type: Literal["original", "rendition", "preview"], id: str
) -> str:
    """Some caching key. This may be before any persistent keys are available"""
    base = (
        asset.get("metadata", {}).get(FOTOWARE_FIELDNAME_UUID, {}).get("value")
        or asset.get("physicalFileId")
        or asset.get("href")
    )
    digest = murmur3_32(base, seed=1682083140)
    return f"{digest}/{type}/{id}"
