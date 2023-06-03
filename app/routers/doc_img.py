from typing import Annotated

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
from fastapi.responses import Response

from .. import fotoware
from ..apptoken import QueryHeaderAuth, TokenAud
from ..assign_metadata_tasks import Task, exec_update_tasks
from ..config import FOTOWARE_ARCHIVES as ARCHIVES
from ..config import FOTOWARE_FIELDNAME_UUID as UUID_FIELD
from ..config import TOKEN_MAX_DURATION_SHORT
from ..fotoware.apitypes import PreviewTrait, RenditionTrait
from ..fotoware.search_expression import SE
from ..renderers import reprs
from ..tasks.uuid import IDENTIFIER_RE

router = APIRouter()

DEFAULT_FILENAME = "getfile"


@router.get("/doc/{identifier}/{filename}", response_class=Response, tags=["rendition"])
async def file_representation(
    authed: Annotated[
        bool,
        Depends(
            QueryHeaderAuth(
                required=False,
                aud=TokenAud.RenderAssetOriginal,
                maxdur=TOKEN_MAX_DURATION_SHORT,
            )
        ),
    ],
    request: Request,
    identifier: Annotated[str, Path(regex=IDENTIFIER_RE)],
    filename: Annotated[str, Path()],
    background_tasks: BackgroundTasks,
):
    """
    Retrieves the original rendition of the file if authenticated or public.

    - `filename`: `"getfile"` will change the Content-Disposition header to the original name.
    """

    asset = await fotoware.search.find(ARCHIVES, SE.eq(UUID_FIELD, identifier))

    is_public = fotoware.assets.is_public(asset)
    if not is_public and (not authed and not is_public):
        # Q: should we even render in this case?
        return await reprs.html(asset, status.HTTP_401_UNAUTHORIZED)

    # when this request is done, the file original is in the cache. Great opportunity
    # to calculate its SHA-256.
    background_tasks.add_task(exec_update_tasks, assets=[asset], tasks=[Task.sha256])

    # we may render: the file is public or the request is authorized
    return await reprs.filerendition(
        asset,
        RenditionTrait(original=True),  # type: ignore
        filename=filename if not filename == DEFAULT_FILENAME else None,
    )


@router.get("/img/{identifier}/preview/{filename}", tags=["rendition"])
async def render_preview(
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
    identifier: Annotated[str, Path(regex=IDENTIFIER_RE)],
    filename: str,
    size: Annotated[int, Query(title="longest of width or height", ge=0)] = 0,
    w: Annotated[int, Query(title="width", ge=0)] = 0,
    h: Annotated[int, Query(title="height", ge=0)] = 0,
    square: Annotated[bool | None, Query()] = None,
):
    """
    Return an asset preview.

    - `filename`: `"getfile"` will change the Content-Disposition header to the original name.
    """

    asset = await fotoware.search.find(ARCHIVES, SE.eq(UUID_FIELD, identifier))
    is_public = fotoware.assets.is_public(asset)
    if not is_public and (not authed and not is_public):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)

    return await reprs.filepreview(
        asset,
        PreviewTrait(height=h, size=size, width=w, square=square),  # type: ignore
        filename=filename if not filename == DEFAULT_FILENAME else None,
    )


@router.get("/img/{identifier}/rendition/{filename}", tags=["rendition"])
async def render_rendition(
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
    identifier: Annotated[str, Path(regex=IDENTIFIER_RE)],
    filename: str,
    profile: Annotated[str | None, Query()] = None,
    original: Annotated[bool | None, Query()] = None,
    size: Annotated[int, Query(title="longest of width or height", ge=0)] = 0,
    w: Annotated[int, Query(title="width", ge=0)] = 0,
    h: Annotated[int, Query(title="height", ge=0)] = 0,
):
    """
    Return an asset rendition.

    - `filename`: `"getfile"` will change the Content-Disposition header to the original name.
    """
    if profile is None and original is None and size + w + h == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST)

    asset = await fotoware.search.find(ARCHIVES, SE.eq(UUID_FIELD, identifier))
    is_public = fotoware.assets.is_public(asset)

    if not is_public or (not authed and not is_public):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)

    return await reprs.filerendition(
        asset,
        RenditionTrait(
            profile=profile, original=original, size=size, width=w, height=h
        ),  # type: ignore
        filename=filename if not filename == DEFAULT_FILENAME else None,
    )
