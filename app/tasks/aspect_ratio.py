from operator import itemgetter

from ..config import FOTOWARE_ASPECTRATIO_LABELS
from ..fotoware.apitypes import Asset


def aspect_ratio(asset: Asset) -> float:
    """Calculate aspect ratio"""
    w, h = itemgetter("pixelwidth", "pixelheight")(
        asset["attributes"]["imageattributes"]  # type: ignore
    )
    return round(w / h, 4)


async def calc_aspect_ratio_label(asset: Asset) -> str | None:
    """Calculate the asset's aspect ratio and assign a label to that"""
    try:
        ratio = aspect_ratio(asset)
        if ratio < 1:  # portrait
            return FOTOWARE_ASPECTRATIO_LABELS[0]
        if ratio == 1:  # square
            return FOTOWARE_ASPECTRATIO_LABELS[1]
        if ratio > 1:  # landscape
            return FOTOWARE_ASPECTRATIO_LABELS[2]
    except Exception:
        return None
