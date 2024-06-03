"""
The unfettered ID-based access of assets with this service creates a problem if access
to the binary representation of a file should be time-limited. Therefore, this service
uses a KEY to SIGN an access TOKEN. The token is a 'JWT', with the following claims:

- `sub`: the identifier of the file
- `aud`: the allowed endpoint (token audience)
- `iat`: the timestamp of token issue, to calculate validity duration
- `exp`: the timestamp of token expiration, after which the token is no longer valid.

The `sub` claim prevents reuse of the token for the same endpoint across different files
and `aud` for across different endpoints. The `exp` claim prevents long-term
reuse of the token to access the file, e.g. by different end-users. The `iat` claim,
combined with `exp`, limits the maximum duration of a valid token.

The KEY can be assigned from environment variable `JWT_SECRET`. Unset it is randomized
and not saved acrosss restarts. Only the "HS256" algorithm is accepted.

Limit replay attacks by limiting the time the token is valid. For file access endpoints
maximum validity is set to `TOKEN_MAX_DURATION_SHORT` (default: 15 minutes), for others
`TOKEN_MAX_DURATION_LONG` is used (default: 1 year). The validator uses a 30sec leeway.

The `sub` key is the identifier of the file. The `aud` key indicates the allowed
interaction with a three-letter string from the below enum `TokenAud`.

If the JWT_SECRET is "sekret", then following token encodes access to the
original rendition of a file with ID '123456789' (linebreaks for readiblity):

    eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9
    .
    eyJzdWIiOiIxMjM0NTY3ODkwIiwiYXVkIjoib3JpIiwiaWF0IjoxNTE2MjM5MDIyLCJleHAiOjE1MTYyNTkwMjJ9
    .
    HNzcYtBpJJDUBZocVdLqtKDbD1EIejJfYZ3-63Zvgmo
"""

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import JWT_SECRET
from .resource_identifier import getidentifier


class TokenAud(str, Enum):
    """Known local audiences for the JWT token"""

    NONE = "zzz"
    PreviewAsset = "pre"
    RenderAsset = "rnd"
    RenderAssetOriginal = "ori"
    RenderFullManifest = "jld"
    UpdateAssetMetadata = "uid"


def sub_aud_dur_claims(token: str, /) -> tuple[str, TokenAud, timedelta, dict]:
    """Return token's subject identifier, subject audience, validity duration, claims."""
    try:
        claims = decode(token)
        if ":" in claims.get("sub", ":") and claims.get("aud") is None:
            # The old parsing code uses colon-sep `{aud}:{sub}` in `sub` claim.
            # These tokens were deprecated with v4.2.0
            audstr, sub = claims.get("sub", f"{TokenAud.NONE}:").split(":", maxsplit=1)
            aud = TokenAud(audstr)
        else:
            sub = claims.get("sub", "")
            aud = TokenAud(claims.get("aud", TokenAud.NONE))
        iat = datetime.fromtimestamp(claims["iat"])
        exp = datetime.fromtimestamp(claims["exp"])
        return sub, aud, exp - iat, claims
    except Exception:
        raise HTTPException(status.HTTP_403_FORBIDDEN)


def tokencontents(*, sub: str, aud: TokenAud, dur: timedelta, **claims) -> str:
    """
    Create a new token with an expiration and other claims

    Args:
        sub: File identifier
        aud: Audience, i.e. allowed action with this token
        dur: Duration after NOW when which this token expires
        claims: Other JWT claims

    Returns:
        The encoded JWT token with the above claims.
    """
    _iat = datetime.now(tz=timezone.utc)
    _exp = datetime.now(tz=timezone.utc) + dur

    return jwt.encode(
        {**claims, "sub": sub, "aud": aud, "iat": _iat, "exp": _exp},
        JWT_SECRET,
        algorithm="HS256",
    )


def decode(token: str) -> dict[str, Any]:
    """Get a token's payload. PyJWT can validate claims: iat, exp, nbf, (iss, aud, iat)"""
    try:
        return jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            leeway=timedelta(seconds=30),
            verify=True,
        )
    except jwt.PyJWTError:
        return dict()


class QueryHeaderAuth:
    """Checks presence of JWT token in Query (token=) or Header (Authorization:)"""

    def __init__(self, *, required=True, aud: TokenAud, maxdur: timedelta):
        self.auth_is_required = required
        self.aud = aud
        self.maxdur = maxdur

    def __call__(
        self,
        request: Request,
        token: Annotated[str | None, Query()] = None,
        httpcreds: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
    ) -> bool:
        try:
            tokencontents = httpcreds.credentials if httpcreds else token
            if not isinstance(tokencontents, str):
                raise HTTPException(status.HTTP_401_UNAUTHORIZED)  # goto except handler

            sub, aud, dur, _ = sub_aud_dur_claims(tokencontents)
            res = request.query_params.get("resource", "")
            identifier = getidentifier(fromresource=res)

            if not all([identifier == sub, self.aud == aud, self.maxdur >= dur]):
                raise HTTPException(status.HTTP_403_FORBIDDEN)

            return True
        except HTTPException as err:
            if self.auth_is_required:
                raise err  # re-raise error iff configured to raise_
            return False
