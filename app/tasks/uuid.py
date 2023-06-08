from base64 import b32encode
from random import choice
from uuid import uuid4

from ..fotoware.apitypes import Asset

IDENTIFIER_RE = "^[rjkmtvyz][a-z2-7]+$"


async def calc_uuid(asset: Asset) -> tuple[str, str]:
    """
    Generate a globally unique ID. The ID is case-insensitive and always starts with a
    letter, for systems that expect a C-style identifier.
    """

    prefix = choice("rjkmtvyz")  # some LD serializations may expect a C-style localname
    guid = b32encode(uuid4().bytes).decode().replace("=", "").lower()

    return prefix + guid
