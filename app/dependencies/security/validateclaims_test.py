import joserfc
import joserfc.errors
import pytest

from .scopes import ScopeSpec, scope_for
from .validateclaims import MyClaimsRegistry


class TestMyClaimsRegistry:
    def test_validate_scope(self):
        allowed_scopes: list[ScopeSpec] = [("metadata", "r"), ("original", "r")]
        reg = MyClaimsRegistry(
            scope={
                "essential": True,
                "values": [scope_for(role, mode) for role, mode in allowed_scopes],
            }
        )

        assert reg.validate({"scope": "m:r O:r"}) is None

        with pytest.raises(joserfc.errors.InvalidClaimError):
            reg.validate({"scope": "J:r"})

        with pytest.raises(joserfc.errors.InvalidClaimError):
            reg.validate({"scope": "X:R"})

    def test_validate_rid(self):
        allowed_1 = "urn:res:123"
        allowed_2 = "urn:res:234"
        reg = MyClaimsRegistry(
            rid={
                "essential": True,
                "values": [allowed_1, allowed_2],
            }
        )

        assert reg.validate({"rid": allowed_1}) is None
        assert reg.validate({"rid": [allowed_1, allowed_2]}) is None
        assert reg.validate({"rid": [allowed_2, "urn:res:999"]}) is None

        with pytest.raises(joserfc.errors.InvalidClaimError):
            reg.validate({"rid": "urn:invalid"})
