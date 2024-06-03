from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_ipaddr

from .config import ENV, RATE_LIMIT
from .fotoware import api
from .routers import doc_img, id_json, robots_txt, tasks

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
    lifespan=api.api_lifespan,
)
app.include_router(id_json.router)
app.include_router(doc_img.router)
app.include_router(tasks.router)
app.include_router(robots_txt.router)

# IP-based rate limiter.
limiter = Limiter(
    key_func=get_ipaddr, default_limits=[RATE_LIMIT]
)  # an ip-address based rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Enable the fotoweb proxy and the JSON representations only in development mode. These
# endpoints do not use authentication and must not be used in production.
if ENV == "development":
    import logging

    from .routers import token

    logging.basicConfig(level=logging.DEBUG)
    app.debug = True

    @app.get("/fotoweb/{rest:path}", tags=["development mode"])
    async def fotoweb_proxy(rest, request: Request):
        """
        Proxies the remote Fotoware endpoint.
        This uses the configured authorization details, but does not retain HTTP methods
        or other headers than Accept: application/json.
        """
        return await api.GET(f"/fotoweb/{rest}?{request.query_params}")

    app.include_router(token.router)
