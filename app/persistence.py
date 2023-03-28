import datetime
import logging
import time
from functools import wraps
from typing import TypeAlias

import redis
from fastapi import HTTPException

_Value: TypeAlias = bytes | float | int | str

CACHE = redis.Redis(host="redis", port=6379, retry_on_timeout=True)


def try_redis(num_retries=5):
    """Wrap a function that calls Redis and retries in case of ConnectionErrors"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = num_retries
            while True:
                try:
                    return func(*args, **kwargs)
                except redis.exceptions.ConnectionError as exc:
                    if retries == 0:
                        logging.error(f"Connection timeout with Redis", exc)
                        raise HTTPException(status_code=500)
                    retries -= 1
                    time.sleep(0.5)
                except redis.exceptions.RedisError as exc:
                    logging.error(f"Unexpected problem with Redis", exc)
                    raise HTTPException(status_code=500)

        return wrapper

    return decorator


@try_redis()
def set(
    name: str, value: _Value, *, expires_in: datetime.timedelta | None = None
) -> bool | None:
    """Set a value in the cache, optionally with expiration"""
    return CACHE.set(name, value, ex=expires_in)


@try_redis()
def get(name: str, default: None = None) -> bytes | None:
    """Get a value from cache"""
    value = CACHE.get(name)
    return value if value is not None else default


def key(asset: dict):
    """A (quasi) unique file ID that, upon modification, immediately expires"""
    return (asset["physicalFileId"] or asset["href"]) + asset["modified"]
