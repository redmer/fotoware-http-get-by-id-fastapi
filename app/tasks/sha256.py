from hashlib import sha256

from ..fotoware.apitypes import Asset, RenditionTrait
from ..renderers.reprs import filerendition


async def calc_sha256(asset: Asset):
    """Calculate the SHA-256 checksum of an asset's original"""

    try:
        original = RenditionTrait(original=True)  # type: ignore
        rendition = await filerendition(asset, original)
        response_body: list[bytes] = [chunk async for chunk in rendition.body_iterator]  # type: ignore
        bytes_content = b"".join(response_body)
        return sha256(bytes_content).hexdigest()
    except Exception:
        return None
