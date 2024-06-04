from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    status,
)
from fastapi.responses import RedirectResponse, Response

from .. import fotoware
from ..apptoken import QueryHeaderAuth, TokenAud
from ..assign_metadata_tasks import Task, exec_update_tasks
from ..config import FOTOWARE_ARCHIVES as ARCHIVES
from ..config import FOTOWARE_FIELDNAME_UUID as UUID_FIELD
from ..config import TOKEN_MAX_DURATION_SHORT
from ..fotoware.apitypes import PreviewTrait, RenditionTrait
from ..fotoware.search_expression import SE
from ..renderers import reprs
from ..resource_identifier import getidentifier, getresourceurl
from ..tasks.uuid import IDENTIFIER_RE
from .responsetype import ResponseMediaType

router = APIRouter()


@router.get("/-/about", response_class=Response, tags=["metadata"])
async def present_resource(
    request: Request,
    resource: Annotated[str, Query()],
    background_tasks: BackgroundTasks,
    format: Annotated[
        ResponseMediaType, Query(title="Force response type")
    ] = ResponseMediaType.AsHTML,
):
    """
    Show a public metadata description of the file.

    Default HTML or JSON if so requested.

    The HTML description contains a reference to a render, that only appears if the file
    is public.
    """

    identifier = getidentifier(fromresource=resource)
    asset = await fotoware.search.find(ARCHIVES, SE.eq(UUID_FIELD, identifier))

    # Alternative representations are forced
    if format == ResponseMediaType.AsJSON or any(
        [
            type in request.headers.getlist("Accept")
            for type in ["application/json", "application/ld+json"]
        ]
    ):
        return await reprs.json(asset)

    # default representation is HTML
    return await reprs.html(asset)


@router.get(
    "/doc/{identifier}/{filename}",
    response_class=Response,
    tags=["render", "metadata"],
    deprecated=True,
)
async def file_representation(
    request: Request,
    identifier: Annotated[str, Path(regex=IDENTIFIER_RE)],
    filename: Annotated[str, Path()],
    as_: Annotated[
        Literal["original", "json", "html"],
        Query(title="Force response type", alias="as"),
    ] = "original",
):
    """
    Deprecated.
    Replaced by `/-/about?resource=` for asset information (HTML, JSON) and
    `/-/asset/render` for original file renders.
    """

    res = getresourceurl(fromidentifier=identifier)
    if as_ == "original":
        return RedirectResponse(
            str(request.url_for("render_asset")) + f"?original=1&resource={res}"
        )

    # else: renamed query parameter
    if format := request.query_params.get("as"):
        formatsfx = f"&format={format}"
    else:
        formatsfx = ""

    res = getresourceurl(fromidentifier=identifier)
    return RedirectResponse(
        str(request.url_for("present_resource")) + f"?resource={res}" + formatsfx,
    )


@router.get("/-/asset/preview", tags=["render"])
async def resource_preview(
    authed: Annotated[
        bool,
        Depends(
            QueryHeaderAuth(
                required=False,
                aud=TokenAud.PreviewAsset,
                maxdur=TOKEN_MAX_DURATION_SHORT,
            )
        ),
    ],
    resource: Annotated[str, Query()],
    size: Annotated[int, Query(title="longest of width or height", ge=0)] = 0,
    w: Annotated[int, Query(title="width", ge=0)] = 0,
    h: Annotated[int, Query(title="height", ge=0)] = 0,
    square: Annotated[bool, Query()] = False,
):
    """Preview an asset"""
    identifier = getidentifier(fromresource=resource)
    asset = await fotoware.search.find(ARCHIVES, SE.eq(UUID_FIELD, identifier))
    is_public = fotoware.assets.is_public(asset)
    if not (not is_public and not authed):  # NAND
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)

    return await reprs.filepreview(
        asset,
        PreviewTrait(height=h, size=size, width=w, square=square),
    )


@router.get("/img/{identifier}/preview/{filename}", tags=["render"], deprecated=True)
async def render_preview(
    identifier: Annotated[str, Path(regex=IDENTIFIER_RE)],
    request: Request,
    filename: str,
    size: Annotated[int, Query(title="longest of width or height", ge=0)] = 0,
    w: Annotated[int, Query(title="width", ge=0)] = 0,
    h: Annotated[int, Query(title="height", ge=0)] = 0,
    square: Annotated[bool | None, Query()] = None,
):
    """Deprecated. Replaced by /-/asset/preview?resource="""
    res = getresourceurl(fromidentifier=identifier)
    return RedirectResponse(
        str(request.url_for("resource_preview"))
        + f"?{request.query_params}&resource={res}"
    )


@router.get("/-/asset/render", tags=["render"])
async def render_asset(
    authed: Annotated[
        bool,
        Depends(
            QueryHeaderAuth(
                required=False,
                aud=TokenAud.RenderAsset,
                maxdur=TOKEN_MAX_DURATION_SHORT,
            )
        ),
    ],
    resource: Annotated[str, Query()],
    background_tasks: BackgroundTasks,
    original: Annotated[bool | None, Query()] = None,
    profile: Annotated[str | None, Query()] = None,
    size: Annotated[int, Query(title="longest of width or height", ge=0)] = 0,
    w: Annotated[int, Query(title="width", ge=0)] = 0,
    h: Annotated[int, Query(title="height", ge=0)] = 0,
):
    """Return an asset rendition."""
    if profile is None and original is None and size + w + h == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST)

    identifier = getidentifier(fromresource=resource)
    asset = await fotoware.search.find(ARCHIVES, SE.eq(UUID_FIELD, identifier))
    is_public = fotoware.assets.is_public(asset)

    if not (not is_public and not authed):  # NAND
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)

    if original is True:
        # when this request is done, the file original is in the cache. Great
        # opportunity to calculate its SHA-256.
        background_tasks.add_task(
            exec_update_tasks, assets=[asset], tasks=[Task.sha256]
        )

    return await reprs.filerendition(
        asset,
        RenditionTrait(
            profile=profile, original=original, size=size, width=w, height=h
        ),
    )


@router.get("/img/{identifier}/rendition/{filename}", tags=["render"], deprecated=True)
async def render_rendition(
    identifier: Annotated[str, Path(regex=IDENTIFIER_RE)],
    request: Request,
    filename: str,
    profile: Annotated[str | None, Query()] = None,
    original: Annotated[bool | None, Query()] = None,
    size: Annotated[int, Query(title="longest of width or height", ge=0)] = 0,
    w: Annotated[int, Query(title="width", ge=0)] = 0,
    h: Annotated[int, Query(title="height", ge=0)] = 0,
):
    """Deprecated. Replaced by /-/asset/render"""
    res = getresourceurl(fromidentifier=identifier)
    return RedirectResponse(
        str(request.url_for("render_asset"))
        + f"?resource={res}&{request.query_params}",
    )
