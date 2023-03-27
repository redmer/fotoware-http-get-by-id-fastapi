import datetime
import os
import sys
import time

import redis
import requests
from fastapi import HTTPException

PREFERRED_ARCHIVE = os.environ["PREFERRED_ARCHIVE"]
ENDPOINT = os.environ["ENDPOINT"]
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
FOTOWARE_QUERY_PLACEHOLDER = "{?q}"

cache = redis.Redis(host="redis", port=6379, decode_responses=True)


def try_redis(num_retries=5):
    """Wrap a function that calls Redis and retries in case of ConnectionErrors."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = num_retries
            while True:
                try:
                    return func(*args, **kwargs)
                except redis.exceptions.ConnectionError as exc:
                    if retries == 0:
                        print(f"ERROR:\tCould not connect with Redis", file=sys.stderr)
                        raise HTTPException(status_code=521)
                    retries -= 1
                    time.sleep(0.5)

        return wrapper

    return decorator


def access_token():
    """Get the OAuth2 Access Token from the environment variables CLIENT_ID and CLIENT_SECRET"""

    @try_redis()
    def set_access_token(value, expires_in):
        print(
            f"Fotoware:\tToken expires at",
            datetime.datetime.now() + datetime.timedelta(0, expires_in),
        )
        cache.setex("access_token", int(expires_in), value)

    @try_redis()
    def get_access_token():
        return cache.get("access_token")

    def request_access_token():
        print(f"Fotoware:\tRequesting NEW access token")
        r = requests.post(
            f"{ENDPOINT}/fotoweb/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
            allow_redirects=True,
            headers={"Accept": "application/json"},
        )
        response = r.json()
        return response["access_token"], response["expires_in"]

    value = get_access_token()
    if value is None:
        value, expiration = request_access_token()
        set_access_token(value, expiration)
    return value


def GET(path):
    print(f"Fotoware:\tGET {path} (with auth)")
    r = requests.get(
        f"{ENDPOINT}{path}", headers={"Accept": "application/json", **auth_header()}
    )
    return r.json()


def auth_header():
    return {"Authorization": f"Bearer {access_token()}"}


def find(archive: str, field: int | str, value: str):
    preferred_archive = GET(f"/fotoweb/archives/{archive}/")

    if not "searchURL" in preferred_archive:
        raise HTTPException(
            status_code=503, detail=f"Archive '{archive}' cannot be searched."
        )

    search_base_url: str = preferred_archive["searchURL"]

    # order always by oldest-first
    query = f";o=+?{field}={value}"

    search_query = search_base_url.replace(FOTOWARE_QUERY_PLACEHOLDER, query)
    search_results = GET(search_query)

    if (
        not "assets" in search_results
        or not "data" in search_results["assets"]
        or len(search_results["assets"]["data"]) == 0
    ):
        raise HTTPException(status_code=404)

    assets = search_results["assets"]["data"]

    if len(assets) > 1:
        print(
            "ERROR:\tMultiple matching assets:",
            map(lambda i: i["href"], assets),
            file=sys.stderr,
        )
        raise HTTPException(status_code=404)

    return search_results["assets"]["data"][0]
