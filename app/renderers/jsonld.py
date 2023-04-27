from datetime import datetime

from ..config import CANONICAL_HOST_BASE, FOTOWARE_FIELDNAME_UUID, FOTOWARE_HOST, HOST
from ..fotoware.apitypes import Asset
from ..slugify import slugify


def jsonldrender(asset: Asset) -> dict:
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
    localurl = f"https://{HOST}/doc/{identifier}/{filename}"
    remoteurl = FOTOWARE_HOST + asset["href"]

    return {
        "@id": subject,
        "@context": "https://schema.org/docs/jsonldcontext.json",
        "identifier": identifier,
        "type": asset["doctype"].capitalize(),
        "about": remoteurl,
        "url": localurl,
        "name": builtin_field("title"),
        "description": builtin_field("description"),
        "keywords": builtin_field("tags"),
        "fileSize": asset["filesize"],
        "dateCreated": asset["created"],  # already ISO format
        "dateModified": asset["modified"],  # already ISO format
    }
