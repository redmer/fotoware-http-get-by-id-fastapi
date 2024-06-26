import urllib.parse
from mimetypes import guess_type
from typing import Any

from ..config import FOTOWARE_FIELDNAME_UUID, FOTOWARE_HOST, HOST
from ..fotoware.apitypes import Asset
from ..fotoware.assets import builtin_field, metadata_field
from ..resource_identifier import getresourceurl


def jsonldrender(asset: Asset) -> dict[str, Any]:
    identifier = metadata_field(asset, FOTOWARE_FIELDNAME_UUID)  # ID is single str
    if not isinstance(identifier, str):
        return {}  # only regular
    filename = asset["filename"]

    subject = getresourceurl(fromidentifier=identifier)  # canonical
    local_render = f"https://{HOST}/-/about?resource={subject}"
    fotoware_url = FOTOWARE_HOST + urllib.parse.quote(asset["href"], safe="()%/")

    mime = guess_type(filename)[0]

    result = {
        "@id": subject,
        "@context": "https://schema.org/docs/jsonldcontext.json",
        "identifier": identifier,
        "dcterms:type": asset.get("doctype"),
        "mainEntityOfPage": fotoware_url,
        "url": local_render,
        "name": filename,
        "dcterms:title": builtin_field(asset, "title"),
        "description": builtin_field(asset, "description"),
        "keywords": builtin_field(asset, "tags"),
        "encodingFormat": mime or None,
        "fileSize": asset.get("filesize"),
        "dateCreated": asset.get("created"),  # already ISO format
        "dateModified": asset.get("modified"),  # already ISO format
    }

    # filter empty values
    return {k: v for k, v in result.items() if v}
