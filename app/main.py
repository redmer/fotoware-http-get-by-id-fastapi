import itertools
from mimetypes import guess_type
from typing import Annotated

from fastapi import Body, Depends, FastAPI, HTTPException, Path, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_ipaddr

from . import fotoware, persistence
from .apptoken import QueryHeaderAuth, TokenAud, tokencontents
from .assign_metadata_tasks import IDENTIFIER_RE, Task, exec_update_tasks, task_info
from .config import (
    ENV,
    FOTOWARE_ARCHIVES,
    FOTOWARE_FIELDNAME_UUID,
    RATE_LIMIT,
    TOKEN_MAX_DURATION_LONG,
    TOKEN_MAX_DURATION_SHORT,
)
from .fotoware import SE, Asset, api
from .log import AppLog
from .renderers import htmlrender, jsonldrender
from .slugify import slugify

if ENV == "development":
    # Only allow the /openapi.json and /docs paths if we're not in development mode
    app = FastAPI(title="Fotoware asset proxy", debug=True)
    RATE_LIMIT = "1000/second"

else:
    app = FastAPI(openapi_url=None)

# IP-based rate limiter.
limiter = Limiter(key_func=get_ipaddr)  # an ip-address based rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/id/{identifier}", response_class=RedirectResponse)
@limiter.limit(RATE_LIMIT)
async def identify_file(
    request: Request, identifier: Annotated[str, Path(regex=IDENTIFIER_RE)]
):
    """
    Find an file by identifier and 307 redirect to file_representation().

    This endpoint is unauthenticated and only passes on ?token-query parameters.
    """

    asset = fotoware.find(FOTOWARE_ARCHIVES, SE.eq(FOTOWARE_FIELDNAME_UUID, identifier))
    pfx = "img" if asset["doctype"] in ["graphic", "image"] else "doc"
    lname, ext = asset["filename"].split(".", maxsplit=1)
    filename = slugify(lname) + "." + ext

    if (qToken := request.query_params.get("token")) is not None:
        return f"/{pfx}/{identifier}/{filename}?token={qToken}"  # Re-send token query parameter along

    return f"/{pfx}/{identifier}/{filename}"


@app.get("/doc/{identifier}/{filename}", response_class=Response)
@limiter.limit(RATE_LIMIT)
async def file_representation(
    authed: Annotated[
        bool,
        Depends(
            QueryHeaderAuth(
                raise_=False,
                aud=TokenAud.RenderAssetOriginal,
                maxdur=TOKEN_MAX_DURATION_SHORT,
            )
        ),
    ],
    request: Request,
    identifier: Annotated[str, Path(regex=IDENTIFIER_RE)],
    filename: str,
):
    """Retrieves the file metadata or, if public, the original rendition of the file"""

    asset = fotoware.find(FOTOWARE_ARCHIVES, SE.eq(FOTOWARE_FIELDNAME_UUID, identifier))

    wants_json = any(
        [
            type in request.headers.getlist("Accept")
            for type in ["application/json", "application/ld+json"]
        ]
    )
    if wants_json:  # then, render JSON. Even without auth.
        return JSONResponse(jsonldrender(asset), media_type="application/ld+json")

    is_public = fotoware.assets.is_public(asset)
    if not is_public or not authed:  # then, render metadata
        return HTMLResponse(content=htmlrender(asset))

    # Render binary, check if it is already in cache
    cachekey = persistence.calc_asset_key(asset, "original", "")
    contents = persistence.get(cachekey)  # if nocache is False else None

    if contents is None:
        url = fotoware.original_rendition(asset["renditions"])
        location = fotoware.rendition_location(url)
        contents = fotoware.unstream(fotoware.retrying_get_binary(location))
        persistence.set(cachekey, contents)

    media_type = guess_type(filename, strict=True)[0] or "application/octet-stream"

    return Response(
        content=contents,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@app.get("/doc/{identifier}/preview/{filename}")
async def render_preview(
    authed: Annotated[
        bool,
        Depends(
            QueryHeaderAuth(
                raise_=False,
                aud=TokenAud.PreviewAsset,
                maxdur=TOKEN_MAX_DURATION_SHORT,
            )
        ),
    ],
    identifier: Annotated[str, Path(regex=IDENTIFIER_RE)],
    filename: str,
    size: Annotated[int, Query()] = 0,
    w: Annotated[int, Query()] = 0,
    h: Annotated[int, Query()] = 0,
    square: Annotated[bool | None, Query()] = None,
):
    """Return an asset preview"""

    asset = fotoware.find(FOTOWARE_ARCHIVES, SE.eq(FOTOWARE_FIELDNAME_UUID, identifier))
    is_public = fotoware.assets.is_public(asset)
    if not is_public or not authed:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)

    # Check if preview-able
    preview_url = fotoware.find_preview(
        asset["previews"], size=size, width=w, height=h, square=square
    )
    if preview_url is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST)

    # Render binary, check if it is already in cache
    cachekey = persistence.calc_asset_key(asset, "preview", preview_url["href"])
    contents = persistence.get(cachekey)  # if nocache is False else None

    if contents is None:
        contents = fotoware.unstream(
            fotoware.stream_preview(preview_url, asset["previewToken"])
        )
        persistence.set(cachekey, contents)

    media_type = guess_type(filename, strict=True)[0] or "application/octet-stream"

    return Response(
        content=contents,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@app.get("/doc/{identifier}/rendition/{filename}")
async def render_rendition(
    authed: Annotated[
        bool,
        Depends(
            QueryHeaderAuth(
                raise_=False,
                aud=TokenAud.RenderAsset,
                maxdur=TOKEN_MAX_DURATION_SHORT,
            )
        ),
    ],
    identifier: Annotated[str, Path(regex=IDENTIFIER_RE)],
    filename: str,
    profile: str | None = None,
    size: int = 0,
    w: int = 0,
    h: int = 0,
):
    """Return an asset rendition"""

    asset = fotoware.find(FOTOWARE_ARCHIVES, SE.eq(FOTOWARE_FIELDNAME_UUID, identifier))
    is_public = fotoware.assets.is_public(asset)

    if not is_public or not authed:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)

    rendition_url = fotoware.find_rendition(
        asset["renditions"], profile=profile, size=size, width=w, height=h
    )
    if rendition_url is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST)

    cachekey = persistence.calc_asset_key(asset, "rendition", rendition_url["profile"])
    contents = persistence.get(cachekey)  # if nocache is False else None

    if contents is None:
        url = fotoware.rendition_location(rendition_url)
        contents = fotoware.unstream(fotoware.retrying_get_binary(url))
        persistence.set(cachekey, contents)

    media_type = guess_type(filename, strict=True)[0] or "application/octet-stream"

    return Response(
        content=contents,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@app.get("/-/background-worker/jsonld-manifest")
async def worker_jsonld_manifest(
    authed: Annotated[
        bool,
        Depends(
            QueryHeaderAuth(
                raise_=True,
                aud=TokenAud.RenderFullManifest,
                maxdur=TOKEN_MAX_DURATION_LONG,
            )
        ),
    ],
    archives: Annotated[list[str], Query()] = FOTOWARE_ARCHIVES,
    num: Annotated[int, Query(ge=1, le=1000)] = 100,
    after: Annotated[str | None, Query(regex=r"\d{4}-\d{2}-\d{2}")] = None,
):
    """
    Return a JSON-LD manifest of all assets in archives

    - Returns asset representations on basis of their identifier.
    - Assets are sorted oldest to newest, so supply the parameter ?after= to paginate
      with the modified date of the last result.
    """
    query = -SE.empty(FOTOWARE_FIELDNAME_UUID)  # where not empty
    if after is not None:
        query = query & SE.eq("mtf", after)  # paginate this endpoint with dateModified

    return [jsonldrender(a) for a in fotoware.find_all(archives, query, n=num)]


@app.get("/-/background-worker/assign-metadata")
async def worker_assign_metadata(
    authed: Annotated[
        bool,
        Depends(
            QueryHeaderAuth(
                raise_=True,
                aud=TokenAud.UpdateAssetMetadata,
                maxdur=TOKEN_MAX_DURATION_LONG,
            )
        ),
    ],
    archives: Annotated[list[str], Query()] = FOTOWARE_ARCHIVES,
    num: Annotated[int, Query(ge=1, le=1000)] = 100,
    tasks: Annotated[list[Task], Query()] = [Task.uuid],
):
    """
    Set unique IDs to any number of files that don't have them yet.

    Configure it as a webhook (e.g. on ingestion) or run with a cronjob to stay updated.
    """

    # Query all assets that have a zero-value for any of the requested tasks' fields
    query = " OR ".join(
        str(SE.empty(fn)) for fn, _ in [task_info(t) for t in tasks] if fn is not None
    )
    AppLog.info(f"Query for worker: {query}")

    # Find all assets that don't have a value for the ID-field.
    assets_wo_id = fotoware.find_all(archives, SE(query), n=num)

    return exec_update_tasks(assets=assets_wo_id, tasks=tasks)


@app.post("/-/webhooks/assign-metadata")
async def webhook_assign_metadata(
    authed: Annotated[
        bool,
        Depends(
            QueryHeaderAuth(
                raise_=True,
                aud=TokenAud.UpdateAssetMetadata,
                maxdur=TOKEN_MAX_DURATION_LONG,
            )
        ),
    ],
    body: Annotated[Asset, Body()],
    tasks: Annotated[list[Task], Query()] = [Task.uuid],
):
    """
    Set unique ID and other task results on a single file.

    If the asset already has a value in a tasked field, ignore the request.
    """

    asset = body.get("data")
    if asset is None:
        return

    return exec_update_tasks(assets=[asset], tasks=tasks)


# Enable the fotoweb proxy and the JSON representations only in development mode. These
# endpoints do not use authentication and must not be used in production.
if ENV == "development":
    import logging

    logging.basicConfig(level=logging.DEBUG)

    @app.get("/fotoweb/{rest:path}", tags=["development mode"])
    def fotoweb_proxy(rest, request: Request):
        """
        Proxies the remote Fotoware endpoint.
        This uses the configured authorization details, but does not retain HTTP methods
        or other headers than Accept: application/json.
        """
        return api.GET(f"/fotoweb/{rest}?{request.query_params}")

    @app.get("/-/token/new", tags=["development mode"])
    async def new_token(subject: str = ""):
        """Returns a new and valid token"""

        from datetime import timedelta

        roles = [
            TokenAud.NONE,
            TokenAud.PreviewAsset,
            TokenAud.RenderAsset,
            TokenAud.RenderAssetOriginal,
            TokenAud.RenderFullManifest,
            TokenAud.UpdateAssetMetadata,
        ]
        durations = [timedelta(minutes=15), timedelta(days=7), timedelta(days=365)]
        tokens = []

        for dur, role in itertools.product(durations, roles):
            tokens.append(
                {
                    "token": tokencontents(aud=role, sub=subject, dur=dur),
                    "duration": dur,
                    "role": role,
                }
            )

        return tokens
