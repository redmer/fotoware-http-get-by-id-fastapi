from joserfc.errors import InvalidClaimError
from joserfc.jwt import JWTClaimsRegistry
from joserfc.rfc7519.registry import ClaimsOption

from .scopes import expand_scope


def values(option: ClaimsOption) -> list[str] | None:
    expected_values = option.get("values")
    if expected_values is None:
        option_value = option.get("value")
        if option_value:
            expected_values = [option_value]

    return expected_values  # type: ignore


class MyClaimsRegistry(JWTClaimsRegistry):
    """
    This JWTClaimsRegistry can validate aud, exp, iat, nbf and scope, rid claims.
    """

    def validate_scope(self, value: str) -> None:
        option = self.options["scope"]

        reqd_scopes = values(option)
        if reqd_scopes is None:
            return

        required_scopes = set()
        for reqscope in reqd_scopes:
            required_scopes.update(expand_scope(reqscope))

        claimed_scopes = expand_scope(value)

        if not any(claimscope in required_scopes for claimscope in claimed_scopes):
            raise InvalidClaimError("scope")

    def validate_rid(self, value: str | list[str]) -> None:
        option = self.options["rid"]

        reqd_rids = values(option)
        if reqd_rids is None:
            return

        if isinstance(value, str):
            claimed_rids = [value]
        else:
            claimed_rids = value

        if not any(claimrid in reqd_rids for claimrid in claimed_rids):
            raise InvalidClaimError("rid")
