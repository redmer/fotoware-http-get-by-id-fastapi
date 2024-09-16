"""
Endpoints concerning listing clients' public keys and reloading them from disk.
"""

import math
import time
import typing as t

from fastapi import APIRouter, HTTPException, status
from joserfc import jwt
from joserfc.jwk import JWKRegistry
from pydantic import BaseModel, ConfigDict

from app.model.clients_public_keys import public_keys, reload_public_key_file

router = APIRouter(tags=["API keys"])


class JWKPublicKey(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        frozen=True,
    )
    kty: t.Literal["EC", "OKP"]
    crv: str
    x: str
    y: str | None = None
    kid: str | None


class JWKPrivateKey(JWKPublicKey):
    d: str


class JWKSet(BaseModel):
    keys: list[JWKPublicKey]


@router.get("/-/client-keys", response_model=JWKSet)
async def list_client_keys():
    """List public keys of client applications."""
    return public_keys().as_dict(private=False)


@router.get("/-/client-keys/{kid}", response_model=JWKPublicKey)
async def get_key(kid: str):
    """Describe a public key of a client application."""
    try:
        return public_keys().get_by_kid(kid).as_dict(private=False)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND)


@router.post("/-/client-keys/reload", include_in_schema=False)
async def reload_keys():
    """Reload public keys from the local keystore."""
    reload_public_key_file()
    return {"status": "reloaded"}


@router.post("/-/client-keys/new", response_model=JWKPrivateKey)
async def create_new_key(kty: t.Literal["OKP", "EC"]):
    crv = {"OKP": "Ed25519", "EC": "P-256"}[kty]
    key = JWKRegistry.generate_key(kty, crv, auto_kid=True)
    return key.as_dict(private=True)


@router.post("/-/client-keys/tokens/new")
async def create_new_token(private_key: JWKPrivateKey, claims: dict[str, t.Any]) -> str:
    algs = {"OKP": "EdDSA", "EC": "ES256"}
    alg = algs[private_key.kty]
    header = {"alg": alg}
    key = JWKRegistry.import_key(private_key.model_dump())
    return jwt.encode(
        header,
        {"iat": math.floor(time.time()), **claims},
        key,
        algorithms=list(algs.values()),
    )
