import urllib.parse
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import JSONResponse

from .. import fotoware
from ..apptoken import QueryHeaderAuth, TokenAud
from ..assign_metadata_tasks import Task, exec_update_tasks, task_info
from ..config import FOTOWARE_ARCHIVES as ARCHIVES
from ..config import FOTOWARE_FIELDNAME_UUID as UUID_FIELD
from ..config import TOKEN_MAX_DURATION_LONG
from ..fotoware.search_expression import SE, Predicate
from ..log import AppLog
from ..renderers.reprs import jsonldrender

router = APIRouter()


@router.get("/-/data/jsonld-manifest", tags=["tasks", "metadata"])
async def worker_jsonld_manifest(
    authed: Annotated[
        bool,
        Depends(
            QueryHeaderAuth(
                required=True,
                aud=TokenAud.RenderFullManifest,
                maxdur=TOKEN_MAX_DURATION_LONG,
            )
        ),
    ],
    archives: Annotated[list[str], Query()] = ARCHIVES,
    limit: Annotated[int, Query(ge=1)] = 100,
    since: Annotated[str | None, Query()] = None,
):
    """
    Return a JSON-LD manifest of all assets in archives

    - Returns asset representations on basis of their identifier.
    - Assets are sorted oldest to newest, so supply the parameter ?after= to paginate
      with the modified date of the last result.
    """
    query = -SE.empty(UUID_FIELD)  # where not empty
    if since is not None:
        # paginate this endpoint with date modified
        query = query & SE.eq(Predicate.FileModificationFrom, since)

    assets = [
        jsonldrender(a) async for a in fotoware.search.iter_n(archives, query, n=limit)
    ]
    until = assets[-1].get("dateModified")
    qp = urllib.parse.urlencode(
        {"limit": limit, "since": until, "archives": archives}, doseq=True
    )
    return JSONResponse(
        content=assets,
        headers={"Link": f'</-/data/jsonld-manifest?{qp}; rel="next"'},
    )


@router.get("/-/background-worker/assign-metadata", tags=["tasks", "metadata"])
async def worker_assign_metadata(
    authed: Annotated[
        bool,
        Depends(
            QueryHeaderAuth(
                required=True,
                aud=TokenAud.UpdateAssetMetadata,
                maxdur=TOKEN_MAX_DURATION_LONG,
            )
        ),
    ],
    background_tasks: BackgroundTasks,
    archives: Annotated[list[str], Query()] = ARCHIVES,
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
    return {"query": query, "message": "Background task started"}


async def update_assets(tasks: list[Task], archives: list[str], query: SE, max: int):
    # Find all assets that don't have a value for the ID-field.
    assets_wo_id = await fotoware.search.find_all(archives, query, n=max)

    await exec_update_tasks(assets=assets_wo_id, tasks=tasks)


@router.post("/-/webhooks/assign-metadata", tags=["webhook", "metadata"])
async def webhook_assign_metadata(
    authed: Annotated[
        bool,
        Depends(
            QueryHeaderAuth(
                required=True,
                aud=TokenAud.UpdateAssetMetadata,
                maxdur=TOKEN_MAX_DURATION_LONG,
            )
        ),
    ],
    background_tasks: BackgroundTasks,
    request: Request,
    tasks: Annotated[list[Task], Query()] = [Task.uuid],
):
    """
    Set unique ID and other task results on a single file.

    If the asset already has a value in a tasked field, ignore the request.
    """
    body = await request.json()
    asset = body.get("data")
    if asset is None:
        return

    background_tasks.add_task(exec_update_tasks, assets=[asset], tasks=tasks)
    return {"asset": asset, "message": "Background task(s) started"}
