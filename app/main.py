import itertools
from datetime import datetime
from mimetypes import guess_type
from typing import Annotated
import urllib.parse

from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    HTTPException,
    Path,
    Query,
    Request,
    status,
)
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
from .fotoware.search_expression import Predicate
from .log import AppLog
from .renderers import htmlrender, jsonldrender
from .slugify import slugify

app_desc = """Regular, unauthenticated GET requests to retrieve a Fotoware asset.
    
Source and details over at GitHub
[redmer/fotoware-http-get-by-id-fastapi](https://github.com/redmer/fotoware-http-get-by-id-fastapi).
"""

app = FastAPI(
    title="Fotoware asset proxy",
    description=app_desc,
    openapi_url="/-/openapi.json",
    docs_url="/-/docs/swagger",
    redoc_url="/-/docs/redoc",
)


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
    Find an file by identifier and 307 redirect to /doc/{identifier}/{filename}.

    This endpoint is unauthenticated and only passes on `?token` query parameters.
    """

    asset = fotoware.find(FOTOWARE_ARCHIVES, SE.eq(FOTOWARE_FIELDNAME_UUID, identifier))
    basename, ext = asset["filename"].rsplit(".", maxsplit=1)
    slug = slugify(basename) + "." + ext

    if (qToken := request.query_params.get("token")) is not None:
        return f"/doc/{identifier}/{slug}?token={qToken}"  # Re-send token query parameter along

    return f"/doc/{identifier}/{slug}"


@app.get(
    "/doc/{identifier}/{filename}",
    response_class=Response,
    tags=["rendition", "json-ld"],
)
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
    if not is_public or (not authed and not is_public):  # then, render metadata
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


@app.get("/doc/{identifier}/preview/{filename}", tags=["rendition"])
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
    if not is_public or (not authed and not is_public):
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


@app.get("/doc/{identifier}/rendition/{filename}", tags=["rendition"])
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

    if not is_public or (not authed and not is_public):
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


@app.get(
    "/-/background-worker/jsonld-manifest",
    tags=["background worker", "json-ld"],
    response_class=JSONResponse,
)
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
    limit: Annotated[int, Query(ge=1)] = 100,
    since: Annotated[str | None, Query()] = None,
):
    """
    Return a JSON-LD manifest of all assets in archives

    - Returns asset representations on basis of their identifier.
    - Assets are sorted oldest to newest, so supply the parameter ?after= to paginate
      with the modified date of the last result.
    """
    query = -SE.empty(FOTOWARE_FIELDNAME_UUID)  # where not empty
    if since is not None:
        # paginate this endpoint with date modified
        query = query & SE.eq(Predicate.FileModificationFrom, since)

    assets = [jsonldrender(a) for a in fotoware.iter_n(archives, query, n=limit)]
    until = assets[-1].get("dateModified")
    qp = urllib.parse.urlencode(
        {"limit": limit, "since": until, "archives": archives}, doseq=True
    )
    return JSONResponse(
        content=assets,
        headers={"Link": f'</-/background-worker/jsonld-manifest?{qp}; rel="next"'},
    )


@app.get("/-/background-worker/assign-metadata", tags=["background worker", "tasks"])
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
    background_tasks: BackgroundTasks,
    archives: Annotated[list[str], Query()] = FOTOWARE_ARCHIVES,
    limit: Annotated[int, Query(ge=1)] = 100,
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

    background_tasks.add_task(update_assets, tasks, archives, SE(query), limit)
    return {"query": query, "message": f"Background task started"}


async def update_assets(tasks: list[Task], archives: list[str], query: SE, max: int):
    # Find all assets that don't have a value for the ID-field.
    assets_wo_id = fotoware.find_all(archives, query, n=max)

    exec_update_tasks(assets=assets_wo_id, tasks=tasks)


@app.post("/-/webhooks/assign-metadata", tags=["webhook", "tasks"])
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
    app.debug = True
    RATE_LIMIT = "1000/second"

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
                    "valid_through": (datetime.utcnow() + dur).isoformat(),
                    "role": role,
                }
            )

        return tokens
