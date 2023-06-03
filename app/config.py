"""
Environment variables configure behavior.

The keys with `os.getenv` have defaults and are optional.
"""

import os
import secrets
from datetime import timedelta

ENV = os.getenv("ENV", "production")
"""
- "development": logging level more verbose, enables /docs OpenAPI documentation,
                 enables /fotoweb remote proxy, enables /json/{id} open endpoint,
                 enables /token endpoint for local tokens.
"""

FOTOWARE_ARCHIVES = os.getenv("FOTOWARE_ARCHIVES", "5000").split()
"""
ID of the archive that will be searched. Provide a searchable (union) archive.
Multiple archives can be searched, but they MUST NOT have same assets represented.
Else, this service finds multiple results for a single ID and errors out.
"""

FOTOWARE_CLIENT_ID = os.environ["FOTOWARE_CLIENT_ID"]
"""From the Fotoware auth details, the Client ID. Required."""

FOTOWARE_CLIENT_SECRET = os.environ["FOTOWARE_CLIENT_SECRET"]
"""From the Fotoware auth details, the Client secret. Required."""

FOTOWARE_EXPORT_PRESET_ID = os.getenv("FOTOWARE_EXPORT_PRESET_ID")
"""
File exports (image only) require a preset, provide its GUID here.
Reference: <https://learn.fotoware.com/Integrations_and_APIs/001_The_FotoWare_API/FotoWare_API_Overview/Export_API#ProgrammaticExportusingtheAPI-GettingthePresetURL>
"""
FOTOWARE_HOST = os.environ["FOTOWARE_HOST"]
"""Fotoware host, e.g. <https://tenant.fotoware.cloud>. Required."""

FOTOWARE_FIELDNAME_UUID = os.getenv("FOTOWARE_FIELDNAME_UUID", "fn")
"""
ID of the field that contains a unique identifying value. If multiple matching values
are found, 404 is returned for that file.
Action required: Fotoware must index empty values for this field number.
"""

FOTOWARE_FIELDNAME_PHASH = os.getenv("FOTOWARE_FIELDNAME_PHASH")
"""ID of the field for a visual (perceptual) hash: similar values mean similar images."""

FOTOWARE_FIELDNAME_SHA256 = os.getenv("FOTOWARE_FIELDNAME_SHA256")
"""ID of the field for a file's sha256 hash: identical values mean identical files."""

FOTOWARE_FIELDNAME_IMGSUBJ = os.getenv("FOTOWARE_FIELDNAME_IMGSUBJ")
"""
ID of the field for recognized objects on an image. This field MUST be of Bag-type and
will be filled with keywords from the recognizer. The values are always in English.
"""

JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe())
"""
Supply a secret token to supply a signed expiration value. The default value invalidates
all tokens upon service reboot. If the value is set, other services may be configured to
have long-lasting tokens, e.g. for webhook configuration.
"""

TOKEN_MAX_DURATION_SHORT, TOKEN_MAX_DURATION_LONG = (
    timedelta(seconds=int(t))
    for t in os.getenv("TOKEN_MAX_DURATION", "900 31622400").split()
)
assert TOKEN_MAX_DURATION_SHORT < TOKEN_MAX_DURATION_LONG
"""
Limit allowed validity duration of a token. The supplied value are two whitespace
separated values in seconds. The first is for file access tokens, the latter for 
background workers and webhooks etc.
"""

HOST = os.getenv("HOST", "https://rdmr.eu/fotoware-http-get-by-id-fastapi")
"""
- For the export API, provides a reference to the endpoint that made the export. 
- For the JSON-LD manifest export, provides the base for file access
"""

CANONICAL_HOST_BASE = os.getenv("CANONICAL_HOST_BASE", "https://" + HOST + "/")
"""For the JSON-LD manifest export, a base URL for an asset canonical URL"""


PUBLIC_DOCTYPES = os.getenv("PUBLIC_DOCTYPES", "").split()
"""
A whitespace separated list of doctypes that do not require authenticated access.
Reference: <https://learn.fotoware.com/Integrations_and_APIs/001_The_FotoWare_API/FotoWare_API_Overview/Document_Types>
"""

PUBLIC_METADATA_KEY, PUBLIC_METADATA_VALUE = os.getenv(
    "PUBLIC_METADATA_KEY_VALUE", ":"
).split(":", maxsplit=1)
"""
A colon (`:`) separated key-value pair of a metadata field and value set on assets that
do not require authenticated access
"""

RATE_LIMIT = os.getenv("RATE_LIMIT", "25/minute; 50/hour; 75/day")
"""Rate-limit the API endpoints outside development mode"""

REDIS_HOST = os.getenv("REDIS_HOST", "redis:6379/")
"""String containing the path to a UNIX domain socket for the Redis-based file cache"""

STYLESHEETS = os.getenv("STYLESHEETS", "").split()
"""Whitespace separated URLs of CSS stylesheets for HTML renders"""

STYLESHEETS_DARK_MODE = os.getenv("STYLESHEETS_DARK_MODE", "").split()
"""Whitespace separated URLs of CSS stylesheets for HTML renders, in dark mode"""
