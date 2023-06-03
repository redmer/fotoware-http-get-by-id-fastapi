import itertools
from datetime import datetime, timedelta

from fastapi import APIRouter

from ..apptoken import TokenAud, tokencontents

router = APIRouter()


@router.get("/-/token/new", tags=["development mode"])
async def new_token(subject: str = ""):
    """Returns a new and valid token"""

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
