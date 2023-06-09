from typing import Annotated

from fastapi import APIRouter, Path, Query, Request, Response
from fastapi.responses import RedirectResponse

from .. import fotoware
from ..config import FOTOWARE_ARCHIVES as ARCHIVES
from ..config import FOTOWARE_FIELDNAME_UUID as UUID_FIELD
from ..fotoware.search_expression import SE
from ..renderers import reprs
from ..slugify import slugify
from ..tasks.uuid import IDENTIFIER_RE
from .responsetype import ResponseMediaType

router = APIRouter()


@router.get(
    "/id/{identifier}",
    response_class=Response,
    tags=["find and redirect", "json-ld"],
)
async def identify_file(
    request: Request,
    identifier: Annotated[str, Path(regex=IDENTIFIER_RE)],
    as_: Annotated[
        ResponseMediaType, Query(title="Force response type", alias="as")
    ] = ResponseMediaType.Original,
):
    """
    Find an file by identifier, determine its best repr and 307 redirect to it.

    This endpoint is unauthenticated and does NOT pass on query parameters.
    The best representation is:
    - JSON, when JSON is requested in the Accept header.
    - When the file is public or request is authenticated, the file binary.
    - Else: the index HTML.
    """

    asset = await fotoware.search.find(ARCHIVES, SE.eq(UUID_FIELD, identifier))

    # Alternative representations are forced
    if as_ == ResponseMediaType.AsHTML:
        return await reprs.html(asset)

    if as_ == ResponseMediaType.AsJSON or any(
        [
            type in request.headers.getlist("Accept")
            for type in ["application/json", "application/ld+json"]
        ]
    ):
        return await reprs.json(asset)

    basename, ext = asset["filename"].rsplit(".", maxsplit=1)
    slug = slugify(basename) + "." + ext
    return RedirectResponse(f"/doc/{identifier}/{slug}")
