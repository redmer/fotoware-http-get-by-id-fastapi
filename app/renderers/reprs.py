import io
from mimetypes import guess_type

from fastapi import HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from .. import fotoware, persistence
from ..config import FOTOWARE_FIELDNAME_UUID as UUID_FIELD
from ..fotoware.apitypes import Asset, PreviewTrait, RenditionTrait
from ..fotoware.assets import metadata_field
from ..log import AppLog
from ..slugify import slugify
from .html import htmlrender
from .jsonld import jsonldrender


async def json(asset: Asset) -> JSONResponse:
    """Retrieves the file's JSON-LD representation"""
    return JSONResponse(jsonldrender(asset), media_type="application/ld+json")


async def html(asset: Asset, status_code: int = 200) -> HTMLResponse:
    """Retrieves the file's HTML representation"""
    return HTMLResponse(content=htmlrender(asset), status_code=status_code)


async def filerendition(
    asset: Asset, traits: RenditionTrait, *, filename: str | None = None
) -> StreamingResponse:
    """Retrieves the file's binary rendition"""

    rendition = fotoware.renditions.find_rendition(asset["renditions"], **traits)
    if rendition is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST)

    if filename is None:
        basename, ext = asset["filename"].rsplit(".", maxsplit=1)
        filename = slugify(basename) + "." + ext
    media_type = guess_type(asset["filename"])[0] or "application/octet-stream"

    identifier = metadata_field(asset, UUID_FIELD)
    if type(identifier) != str:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "No one identifier")

    cachekey = identifier + ":" + fotoware.apitypes.traitkey(traits)
    content = await persistence.get(cachekey)
    AppLog.info(f"cache: result ({type(content)}) for cachekey: {cachekey}")

    if content is None:
        location = await fotoware.renditions.rendition_location(rendition)  # expensive
        r = await fotoware.assets.retrying_response(location)
        content = await r.read()
        await persistence.set(cachekey, content)

    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


async def filepreview(
    asset: Asset, traits: PreviewTrait, *, filename: str | None = None
) -> StreamingResponse:
    """Retrieves a file's preview"""

    if filename is None:
        basename, ext = asset["filename"].rsplit(".", maxsplit=1)
        filename = slugify(basename) + "." + ext
    media_type = guess_type(asset["filename"])[0] or "application/octet-stream"

    identifier = metadata_field(asset, UUID_FIELD)
    if type(identifier) != str:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "No one identifier")

    cachekey = identifier + ":" + fotoware.apitypes.traitkey(traits)
    content = await persistence.get(cachekey)
    AppLog.info(f"Cached result ({type(content)}) for cachekey: {cachekey}")

    if content is None:
        # Check if preview-able
        preview_url = fotoware.previews.find_preview(asset["previews"], **traits)
        if preview_url is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST)

        r = await fotoware.previews.preview_response(preview_url, asset["previewToken"])
        content = await r.read()
        await persistence.set(cachekey, content)

    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
