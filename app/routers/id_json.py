from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query, Request, Response
from fastapi.responses import RedirectResponse

from ..resource_identifier import getresourceurl
from ..tasks.uuid import IDENTIFIER_RE

router = APIRouter()


@router.get("/id/{identifier}", response_class=Response, tags=["find and redirect"])
async def identify_file(
    identifier: Annotated[str, Path(regex=IDENTIFIER_RE)],
    request: Request,
    as_: Annotated[
        Literal["original", "json", "html"] | None,
        Query(title="Force response type", alias="as", deprecated=True),
    ] = None,
):
    """
    Construct a file URL identifier and redirect to its About page.
    """

    res = getresourceurl(fromidentifier=identifier)

    if as_ is not None:
        # The deprecated ?as query parameter
        if as_ == "original":
            render_asset = str(request.url_for("render_asset"))
            return RedirectResponse(render_asset + f"?original=1&resource={res}")

        about = str(request.url_for("present_resource"))
        return RedirectResponse(about + f"?resource={res}&format={as_}")

    # This endpoint only redirects to the about renderer
    about = str(request.url_for("present_resource"))
    return RedirectResponse(about + f"?resource={res}")
