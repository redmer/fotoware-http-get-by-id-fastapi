from enum import Enum


class ResponseMediaType(str, Enum):
    """Force a response type from /id or /doc"""

    Original = "original"
    AsHTML = "html"
    AsJSON = "json"
