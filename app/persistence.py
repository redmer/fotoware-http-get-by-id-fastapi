from typing import Optional

from cashews import cache
from cashews._typing import TTL

from .config import REDIS_HOST

type _Value = bytes | float | int | str

cache.setup(f"redis://{REDIS_HOST}", suppress=True)


async def set(name: str, value: _Value, *, expire: Optional[TTL] = None) -> bool | None:
    """Set a value in the cache, optionally with expiration"""
    return await cache.set(name, value, expire=expire)


async def get(name: str, default: None = None) -> bytes | None:
    """Get a value from cache"""
    return await cache.get(name, default=default)
