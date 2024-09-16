"""
The unfettered ID-based access of assets with this service creates a problem if access
to the binary representation of a file should be time-limited. Therefore, this service
uses ACCESS TOKENS that temporally limit access and can restrict access in other ways.

The token is an asymmetrically signed JWT, using the `EdDSA` algorithm (Ed25519 curve).
If OKP-keys are unvailable, use `ES256K` or `ES256` instead). The JWT has the following
REQUIRED claims:

- `scope`: space separated list of scopes this token is valid for

Some endpoints MAY require the following claims:

- `exp`: the timestamp of token expiration, after which the token is no longer valid
- `rid`: the resource identifier that is accessed, e.g., for original renders

The following claims are recommended, but OPTIONAL:

- `aud`: audience, i.e., the host of fotoware-http-get-by-id-fastapi
- `iat`: issued at, timestamp at which the token was issued by the `iss`
- `iss`: issuer, i.e., the app that sent the request
- `nbf`: not before, timestamp before which the token is not valid

The administrator registers a public key for a trusted client application. That public
key is then explicitely trusted for all operations. Each transaction with a token is
saved in the application access log.

The `scope` claim prevents reuse of the token for other actions.
The `rid` claim prevents reuse of the token for other resources.
The `exp` claim prevents long-term reuse of the token.

It is recommended to always put all the above claims in the JWT token.
"""

from datetime import timedelta

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from joserfc import jwt
from joserfc.errors import InvalidClaimError, InvalidTokenError, MissingClaimError
from joserfc.jws import JWSRegistry
from joserfc.rfc7519.claims import Claims

from app.config import HOST
from app.model.clients_public_keys import public_keys

from .scopes import ScopeSpec, scope_for
from .validateclaims import MyClaimsRegistry

ALLOWED_JWS_ALGORITHMS = ["EdDSA", "ES256K", "ES256"]
JWS_REGISTRY = JWSRegistry(algorithms=ALLOWED_JWS_ALGORITHMS)


def validate_token(
    token: str,
    *,
    allowed_scopes: list[ScopeSpec],
    allowed_resources: list[str],
    limit_age=False,
    max_age=timedelta(minutes=20),
    now: int | None = None,
) -> Claims:
    """
    Checks a token, validate its signature and claims, and returns its claims.

    Args:
        token: The complete JWT token as a string.
        allowed_scopes: The token MUST have one of these scopes in its `scope` claim.
        allowed_resources: The resource ID's one of which this token MUST have in its
            `rid` claim. If there are no allowed resources, this claim is OPTIONAL.
        limit_validity: Require an iat claim for this endpoint.
        expire_after: The maximum time a token may be valid after issuance.

    Raises:
        InvalidClaimError: If the claims are not valid.
        JoseError: The token is invalid, e.g. because of its signature, payload, etc.
    """

    claims_reg = MyClaimsRegistry(
        now=now,
        scope={
            "essential": True,
            "values": [scope_for(role, mode) for role, mode in allowed_scopes],
        },
        aud={"essential": False, "value": HOST},
        iat={"essential": True},
        exp={"essential": limit_age},
        nbf={"essential": False},
        rid={"essential": bool(allowed_resources), "values": allowed_resources},
    )

    token_decoded = jwt.decode(
        token,
        public_keys(),
        algorithms=ALLOWED_JWS_ALGORITHMS,
    )
    claims_reg.validate(token_decoded.claims)

    if limit_age:
        iat = token_decoded.claims.get("iat", None)  # type: int | None
        exp = token_decoded.claims.get("exp", claims_reg.now)
        if iat is None or (exp - iat) > max_age.total_seconds():
            # the time difference between expiration and issuance time is bigger than
            # the total expiration timedelta allowed.
            raise InvalidClaimError("exp")

    return token_decoded.claims


class AsymmetricalToken:
    """Checks presence of JWT token in Query (token=) or Header (Authorization:)"""

    def __init__(
        self,
        *,
        scopes: list[ScopeSpec],
        required: bool,
        any_resource: bool = False,
        limit_age: bool = True,
        max_age: timedelta = timedelta(minutes=20),
    ):
        """
        Access control using an asymmetrical JWT token.

        The token is supplied as Query parameter (token=) or as Header (Authorization:).
        The token has the following JWT claims:

            `"scope"`: Space separated list of scope specifiers.
            `"iat"`: Timestamp of issuance, required.
            `"exp"`: Expiration timestamp, required if the endpoint limits token age.
            `"rid"`: Resource ID, required if endpoint requires tokens not to be for any
                resource. Fill with resource URI.

        Args:
            scopes: List of scopes that this endpoint requires
            required: Raise 401 if the token is invalid
            any_resource: Requires a rid (resource id) claim if set to False (default).
            limit_age: Limit the maximum age a token can have (default). Requires the
                exp claim on a JWT token.
            max_age: The maximum age a token can become (max diff between iat and exp).
                exp is not a
        """
        self.auth_is_required = required
        self.allowed_scopes = scopes
        self.any_resource = any_resource
        self.limit_age = limit_age
        self.max_age = max_age

    def __call__(
        self,
        request: Request,
        q_token: str | None = Depends(Query(None, alias="token")),
        h_creds: HTTPAuthorizationCredentials | None = Depends(
            HTTPBearer(auto_error=False)
        ),
    ) -> bool:
        try:
            serialized = q_token if h_creds is None else h_creds.credentials

            if serialized is None:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED)  # goto except handler

            # Get the resource that should be in the rid claim
            resource_id = request.query_params.get("resource", None)
            allowed_resources = list(filter(None, [resource_id]))
            if not self.any_resource and len(allowed_resources) == 0:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED)

            validate_token(
                serialized,
                allowed_scopes=self.allowed_scopes,
                allowed_resources=allowed_resources,
                limit_age=self.limit_age,
                max_age=self.max_age,
            )

            return True

        except HTTPException:
            # If the exception is already a HTTPException, don't recreate it...
            if self.auth_is_required:
                raise
            return False

        except (InvalidTokenError, InvalidClaimError, MissingClaimError):
            # Raise other exceptions as a 401
            if self.auth_is_required:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED)
            return False
