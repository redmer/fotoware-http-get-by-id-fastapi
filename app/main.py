import mimetypes
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse

from . import fotoware, previews

app = FastAPI()


@app.get("/r/{field}/{value}", response_class=RedirectResponse)
def redirect_to_asset_by_field_value(field: int | str, value: str):
    asset = fotoware.find(fotoware.PREFERRED_ARCHIVE, field, value)
    filename = asset["filename"]
    return f"/r/{field}/{value}/{filename}"


@app.get("/r/{field}/{value}/{filename}")
async def retrieve_asset_by_field_value(
    field: int | str,
    value: str | int,
    filename,
    size: int = 0,
    width: int = 0,
    height: int = 0,
    square: bool | None = None,
):
    """Retrieves asset by first search result of field with value in configured ALL archive."""

    asset = fotoware.find(fotoware.PREFERRED_ARCHIVE, field, str(value))
    mime_type = mimetypes.guess_type(filename, strict=True)

    if True:
        href = previews.export_asset(href=asset["href"])
        return href

    if "previews" in asset and (size + width + height > 0 or square is not None):
        contents = previews.find_appropriate_preview(
            asset["previews"],
            min_size=size,
            min_width=width,
            min_height=height,
            must_be_square=square,
        )

        stream = previews.stream_preview(contents, asset["previewToken"])
        return StreamingResponse(stream, media_type=mime_type[0])

    if "renditions" in asset:
        href = previews.original_rendition(asset["renditions"])
        stream = previews.stream_rendition(href)
        mime_type = mimetypes.guess_type(filename, strict=True)
        return StreamingResponse(stream, media_type=mime_type[0])

    raise HTTPException(status_code=500)


if "ENV" in os.environ and os.environ["ENV"] == "DEBUG":

    @app.get("/fotoweb/{rest:path}")
    def fotoweb_proxy(rest, request: Request):
        return fotoware.GET(f"/fotoweb/{rest}?{request.query_params}")

    @app.get("/j/{field}/{value}")
    def json_by_field_value(field: int | str, value: str):
        return fotoware.find(fotoware.PREFERRED_ARCHIVE, field, value)
