import datetime
import mimetypes

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_ipaddr

from . import fotoware, persistence, previews
from .config import (
    CACHE_EXPIRATION_SECONDS,
    ENV,
    FOTOWARE_PREFERRED_ARCHIVE,
    RATE_LIMIT,
)

if ENV == "development":
    app = FastAPI(title="Fotoware asset proxy", debug=True)
    RATE_LIMIT = "1000/second"

# Only allow the /openapi.json and /docs paths if we're not in development mode
else:
    app = FastAPI(openapi_url=None)

limiter = Limiter(key_func=get_ipaddr)  # an ip-address based rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/id/{field}/{value}", response_class=RedirectResponse)
@limiter.limit(RATE_LIMIT)
async def redirect_asset_by_field_value(r: Request, field: int | str, value: str | int):
    """Redirects to first search result where field=value in configured archive"""

    asset = fotoware.find_single(FOTOWARE_PREFERRED_ARCHIVE, field, str(value))
    filename = asset["filename"]
    return f"/doc/{field}/{value}/{filename}"


@app.get("/doc/{field}/{value}/{filename}", response_class=Response)
@limiter.limit(RATE_LIMIT)
async def retrieve_cached_asset_by_field_value(
    r: Request,
    field: int | str,
    value: str | int,
    filename: str,
    nocache: bool = False,
):
    """Retrieves asset by first search result of field with value in configured ALL archive"""

    asset = fotoware.find_single(FOTOWARE_PREFERRED_ARCHIVE, field, str(value))
    mime_type = (
        mimetypes.guess_type(filename, strict=True)[0] or "application/octet-stream"
    )

    key = persistence.key(asset)
    cached = persistence.get(key)

    if cached is None or nocache:
        cached = previews.get_contents(asset)
        persistence.set(
            key, cached, expires_in=datetime.timedelta(seconds=CACHE_EXPIRATION_SECONDS)
        )

    return Response(content=cached, media_type=mime_type)


# Only show in development mode the fotoweb proxy and the JSON representations
if ENV == "development":
    import logging

    logging.basicConfig(level=logging.DEBUG)

    @app.get("/fotoweb/{rest:path}")
    def fotoweb_proxy(rest, request: Request):
        """Proxies (with auth) the entirety of the remote Fotoware endpoint"""
        return fotoware.GET(f"/fotoweb/{rest}?{request.query_params}")

    @app.get("/json/{field}/{value}")
    @app.get("/json/{field}/{value}/{filename}")
    def json_by_field_value(field: int | str, value: str):
        """Returns the JSON representation of a single asset"""
        return fotoware.find_single(FOTOWARE_PREFERRED_ARCHIVE, field, value)
