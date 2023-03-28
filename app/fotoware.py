import datetime
import json
import logging
from typing import Any, Tuple
from urllib.parse import quote

import requests
from fastapi import HTTPException

from . import persistence
from .config import (
    FOTOWARE_CLIENT_ID,
    FOTOWARE_CLIENT_SECRET,
    FOTOWARE_HOST,
    FOTOWARE_SEARCH_EXPRESSION_SUFFIX,
)

FOTOWARE_QUERY_PLACEHOLDER = "{?q}"


def access_token() -> str:
    """Get the OAuth2 Access Token from the environment variables CLIENT_ID and CLIENT_SECRET"""

    def request_new_access_token() -> Tuple[str, float]:
        logging.debug(f"Fotoware:\tRequesting NEW access token")
        r = requests.post(
            FOTOWARE_HOST + "/fotoweb/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": FOTOWARE_CLIENT_ID,
                "client_secret": FOTOWARE_CLIENT_SECRET,
            },
            allow_redirects=True,
            headers={"Accept": "application/json"},
        )
        response = r.json()
        return response["access_token"], response["expires_in"]

    value = persistence.get("fotoware_access_token")
    if value is not None:
        return str(value, encoding="utf-8")
    if value is None:
        value, expiration = request_new_access_token()
        logging.info(
            f"Fotoware:\tNew token expires at",
            datetime.datetime.now() + datetime.timedelta(0, expiration),
        )
        persistence.set(
            "fotoware_access_token",
            value,
            expires_in=datetime.timedelta(seconds=expiration),
        )
        return value
    return value


def GET(path, *, headers={}, **get_kwargs) -> dict:
    """GET request on the Fotoware ENDPOINT_HOST"""
    logging.debug(f"Fotoware:\tGET {path} (with auth)")
    r = requests.get(
        f"{FOTOWARE_HOST}{path}",
        headers={"Accept": "application/json", **auth_header(), **headers},
        allow_redirects=True,
        **get_kwargs,
    )
    return r.json()


def auth_header() -> dict[str, str]:
    """Return Authorization header as a dict"""
    return {"Authorization": f"Bearer {access_token()}"}


def find_all(archive_id: str, field: int | str, value: str) -> Any:
    """Find all assets that match field=value in an archive"""
    preferred_archive = GET(f"/fotoweb/archives/{archive_id}/")

    if not "searchURL" in preferred_archive:
        logging.error(f"Archive '{archive_id}' cannot be searched")
        raise HTTPException(status_code=503)

    search_base_url: str = preferred_archive["searchURL"]

    # order always by oldest-first
    query = ";o=+?q=" + quote(f"{field}:{value} {FOTOWARE_SEARCH_EXPRESSION_SUFFIX}")

    search_query = search_base_url.replace(FOTOWARE_QUERY_PLACEHOLDER, query)
    search_results = GET(search_query)

    return {"assets": {"data": []}, **search_results}["assets"]["data"]


def find_single(archive_id: str, field: int | str, value: str):
    """Find a single asset that matches field=value in an archive"""

    assets = find_all(archive_id, field, value)

    if len(assets) == 0:
        logging.error(f"No assets in archive '{archive_id}' match {field}='{value}'")
        raise HTTPException(status_code=404)

    if len(assets) > 1:
        logging.error(
            f"Multiple assets in archive '{archive_id}' match {field}='{value}'",
            json.dumps(map(lambda i: i["href"], assets)),
        )
        raise HTTPException(status_code=404)

    return assets[0]


def rendition_request_service_url() -> str:
    api_descriptor = GET("/fotoweb/me/")
    if (
        "services" in api_descriptor
        and "rendition_request" in api_descriptor["services"]
    ):
        return api_descriptor["services"]["rendition_request"]
    else:
        logging.error(f"Unexpected API description", json.dumps(api_descriptor))
        raise HTTPException(status_code=500)
