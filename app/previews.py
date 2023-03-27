from typing import Any, Iterator
import os
import sys
import time
from dataclasses import dataclass

import requests
from fastapi import HTTPException

from . import fotoware


@dataclass
class Preview:
    size: int
    width: int
    height: int
    href: str
    square: bool


@dataclass
class SizePref:
    min_size: int | None = 0
    min_width: int | None = 0
    min_height: int | None = 0
    must_be_square: bool | None = None


def find_appropriate_preview(
    data: list,
    *,
    min_size: int | None = 0,
    min_width: int | None = 0,
    min_height: int | None = 0,
    must_be_square: bool | None = None,
) -> str:
    """Find the first preview that qualifies with the specified constraints."""
    qualified = filter(lambda i: min_size < i["size"], data)
    qualified = filter(lambda i: min_width < i["width"], qualified)
    qualified = filter(lambda i: min_height < i["height"], qualified)
    if must_be_square is not None:
        qualified = filter(lambda i: i["square"] is must_be_square, qualified)

    return next(qualified)["href"]


def original_rendition(data: list) -> str:
    """Return the original rendition of the file"""
    return next(filter(lambda r: True == r["original"], data))["href"]


def rendition_request_service_url() -> str:
    api_descriptor = fotoware.GET("/fotoweb/me/")
    if (
        "services" in api_descriptor
        and "rendition_request" in api_descriptor["services"]
    ):
        return api_descriptor["services"]["rendition_request"]
    else:
        print(api_descriptor)
        raise HTTPException(status_code=500)


NUM_RETRIES = 5


def export_asset(href: str) -> Any:
    # TODO: Response@2x
    # TODO: Request min_size
    response = requests.request(
        "EXPORT",
        fotoware.ENDPOINT + href,
        headers={
            "Content-Type": "application/vnd.fotoware.export-request+json",
            "Accept": "application/vnd.fotoware.export-data+json",
            **fotoware.auth_header(),
        },
        json={
            "width": 0,
            "height": 0,
            "publication": os.environ["NAME"],
            "preset": f"/fotoweb/me/presets/export/{ os.environ['EXPORT_PRESET_GUID'] }",
        },
    )
    print(f"File export API response: ", response, response.request)
    return response.json()


def stream_preview(href: str, previewToken: str) -> Iterator[bytes]:
    content = requests.get(
        fotoware.ENDPOINT + href,
        headers={"Authorization": f"Bearer {previewToken}"},
        stream=True,
    )
    if not content.ok:
        raise HTTPException(status_code=404)
    return content.iter_content()


def stream_rendition(href: str) -> Iterator[bytes]:
    start_render = requests.post(
        fotoware.ENDPOINT + rendition_request_service_url(),
        headers={
            "Content-Type": "application/vnd.fotoware.rendition-request+json",
            "Accept": "application/vnd.fotoware.rendition-response+json",
            **fotoware.auth_header(),
        },
        json={"href": href},
    )
    if not start_render.ok:
        print(f"Request '{href}' failed ({start_render.status_code})", file=sys.stderr)
        raise HTTPException(status_code=500)
    rendition = start_render.headers["Location"]
    print(f"Started render at '{start_render.url}' of '{href}': see '{rendition}'")

    retries = int(NUM_RETRIES)
    while True:
        content = requests.get(rendition, headers=fotoware.auth_header(), stream=True)
        if content.status_code == 200:
            return content.iter_content()
        if retries == 0:
            print(
                f"ERROR:\tDownload '{href}' failed ({content.status_code}) after {NUM_RETRIES}",
                file=sys.stderr,
            )
            raise HTTPException(status_code=521)

        retries -= 1
        time.sleep(0.5)
