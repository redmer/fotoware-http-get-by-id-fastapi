from fastapi import HTTPException, status

from .config import CANONICAL_HOST_BASE


def getidentifier(*, fromresource: str):
    """Returns FotoWare identifier for a resource URL"""
    if not fromresource.startswith(CANONICAL_HOST_BASE):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)
    return fromresource.removeprefix(CANONICAL_HOST_BASE)


def getresourceurl(*, fromidentifier: str):
    """Returns resource URL for a FotoWare identifier"""
    return CANONICAL_HOST_BASE + fromidentifier
