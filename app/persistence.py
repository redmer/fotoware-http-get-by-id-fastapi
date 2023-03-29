import datetime
from typing import TypeAlias

import pymemcache
from pymemcache.client.retrying import RetryingClient
from pymemcache.exceptions import MemcacheUnexpectedCloseError

from .config import MEMCACHED_HOST

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


def set(
    name: str, value: _Value, *, expires_in: datetime.timedelta | None = None
) -> bool | None:
    """Set a value in the cache, optionally with expiration"""
    seconds = expires_in.seconds if expires_in else 0
    return MEMCACHED.set(name, value, expire=seconds)


def get(name: str, default: None = None) -> bytes | None:
    """Get a value from cache"""
    return MEMCACHED.get(name, default)


def key(asset: dict):
    """A (quasi) unique file ID that, upon modification, immediately expires"""
    return (asset["physicalFileId"] or asset["href"]) + asset["modified"]
