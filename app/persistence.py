from typing import TypeAlias

from cashews import cache
from .config import REDIS_HOST

_Value: TypeAlias = bytes | float | int | str

cache.setup(f"redis://{REDIS_HOST}", suppress=True)


async def set(name: str, value: _Value) -> bool | None:
    """Set a value in the cache, optionally with expiration"""
    return await cache.set(name, value)


async def get(name: str, default: None = None) -> bytes | None:
    """Get a value from cache"""
    return await cache.get(name, default=default)
