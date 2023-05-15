from mimetypes import guess_type
from typing import Any

from ..config import CANONICAL_HOST_BASE, FOTOWARE_FIELDNAME_UUID, FOTOWARE_HOST, HOST
from ..fotoware.apitypes import Asset
from ..slugify import slugify


def jsonldrender(asset: Asset) -> dict[str, Any]:
    def builtin_field(name: str):
        for field in asset["builtinFields"]:
            if field["field"] == name:
                return field["value"]
        return None

    def metadata_field(name: str):
        for k, v in asset["metadata"].items():
            if k == name:
                return v["value"]
        return None

    identifier = metadata_field(FOTOWARE_FIELDNAME_UUID)  # ID is single str
    if not isinstance(identifier, str):
        return {}  # only regular
    lname, ext = asset["filename"].split(".", maxsplit=1)
    filename = slugify(lname) + "." + ext
    subject = CANONICAL_HOST_BASE + identifier  # canonical
    local_render = f"https://{HOST}/doc/{identifier}/{filename}"
    fotoware_url = FOTOWARE_HOST + asset["href"]

    mime = guess_type(filename)[0]

    result = {
        "@id": subject,
        "@context": "https://schema.org/docs/jsonldcontext.json",
        "identifier": identifier,
        "dcterms:type": asset.get("doctype"),
        "mainEntityOfPage": fotoware_url,
        "url": local_render,
        "name": lname,
        "dcterms:title": builtin_field("title"),
        "description": builtin_field("description"),
        "keywords": builtin_field("tags"),
        "encodingFormat": mime or None,
        "fileSize": asset.get("filesize"),
        "dateCreated": asset.get("created"),  # already ISO format
        "dateModified": asset.get("modified"),  # already ISO format
    }

    # filter empty values
    return {k: v for k, v in result.items() if v}
