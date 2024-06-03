from enum import Enum


class ResponseMediaType(str, Enum):
    """Force a response type from /id or /doc"""

    AsHTML = "html"
    AsJSON = "json"
