import logging
import time
from typing import Iterator

import requests
from fastapi import HTTPException

from . import fotoware
from .config import FOTOWARE_EXPORT_PRESET_GUID, FOTOWARE_HOST, NAME

ASSET_DOCTYPE = ["image", "movie", "audio", "document", "graphic", "generic"]
NUM_CONNECTION_RETRIES = 5


def has_previews(asset: dict):
    """This asset has pre-rendered previews"""
    return "previews" in asset and isinstance(asset["previews"], list)


def find_appropriate_preview(
    data: list,
    *,
    min_size: int | None = 0,
    min_width: int | None = 0,
    min_height: int | None = 0,
    must_be_square: bool | None = None,
) -> str:
    """Find the first preview that qualifies with the specified constraints"""
    qualified = filter(lambda i: min_size < i["size"], data)
    qualified = filter(lambda i: min_width < i["width"], qualified)
    qualified = filter(lambda i: min_height < i["height"], qualified)
    if must_be_square is not None:
        qualified = filter(lambda i: i["square"] is must_be_square, qualified)

    return next(qualified)["href"]  # next = first = qualified[0]


def stream_preview(preview_href: str, previewToken: str) -> Iterator[bytes]:
    """Return the preview image"""
    content = requests.get(
        preview_href, headers={"Authorization": f"Bearer {previewToken}"}, stream=True
    )

    if not content.ok:
        raise HTTPException(status_code=404)
    return content.iter_content(1024)


def can_be_exported(asset: dict):
    """This asset can be exported (i.e., is an image)"""
    return asset["doctype"] in ["image"]


def stream_asset(asset_href: str) -> Iterator[bytes]:
    # TODO: Response@2x
    # TODO: Request min_size
    response = requests.request(
        "EXPORT",
        FOTOWARE_HOST + asset_href,
        headers={
            "Content-Type": "application/vnd.fotoware.export-request+json",
            "Accept": "application/vnd.fotoware.export-data+json",
            **fotoware.auth_header(),
        },
        json={
            "width": 0,
            "height": 0,
            "publication": NAME,
            "preset": f"/fotoweb/me/presets/export/{ FOTOWARE_EXPORT_PRESET_GUID }",
        },
    )
    href = response.json()["export"]["image"]["doubleResolution"]
    return stream_get_binary(href)


def has_renditions(asset: dict):
    """This asset can be rendered"""
    return "renditions" in asset and isinstance(asset["renditions"], list)


def original_rendition(renditions: list) -> str:
    """Return the original rendition of the asset"""
    return next(filter(lambda r: True == r["original"], renditions))["href"]


def stream_rendition(rendition_href: str) -> Iterator[bytes]:
    start_render = requests.post(
        fotoware.FOTOWARE_HOST + fotoware.rendition_request_service_url(),
        headers={
            "Content-Type": "application/vnd.fotoware.rendition-request+json",
            "Accept": "application/vnd.fotoware.rendition-response+json",
            **fotoware.auth_header(),
        },
        json={"href": rendition_href},
    )
    if not start_render.ok:
        logging.error(f"Request '{rendition_href}' failed ({start_render.status_code})")
        raise HTTPException(status_code=500)
    rendition = start_render.headers["Location"]
    logging.debug(
        f"Started render at '{start_render.url}' of '{rendition_href}': see '{rendition}'"
    )

    return stream_get_binary(rendition)


def stream_get_binary(href) -> Iterator[bytes]:
    retries = int(NUM_CONNECTION_RETRIES)
    while True:
        asset = requests.get(href, headers=fotoware.auth_header(), stream=True)
        if asset.status_code == 200:
            return asset.iter_content()
        if retries == 0:
            logging.error(
                f"Download '{href}' failed ({asset.status_code}) after {NUM_CONNECTION_RETRIES}"
            )
            raise HTTPException(status_code=521)

        retries -= 1
        time.sleep(0.5)


def get_contents(asset: dict) -> bytes:
    """Get file contents of a Fotoware asset"""

    def unstream(stream: Iterator[bytes]) -> bytes:
        return b"".join(stream) or b""

    return unstream(stream(asset))


def stream(asset: dict) -> Iterator[bytes]:
    """Returns the most appropriate filestream"""

    # -> if the asset is an image, the exports API is the best (and cached) option
    if can_be_exported(asset):
        return stream_asset(asset["href"])

    # -> Otherwise, the original renditions should be requested
    if has_renditions(asset):
        orig = original_rendition(asset["renditions"])
        return stream_rendition(orig)

    logging.error(f"No export nor rendition found for asset '{asset['href']}'")
    raise HTTPException(status_code=404)
