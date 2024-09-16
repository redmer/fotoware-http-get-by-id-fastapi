from .scopes import (
    any_is_allowed,
    expand_scope,
    scope_for,
    scope_is_allowed,
)


class TestTokenScope:
    def test_scope_for(self):
        assert "R:r" == scope_for("render", "r")
        assert "J:rw" == scope_for("manifest", "rw")
        assert "m:w" == scope_for("metadata", "w")

    def test_is_allowed(self):
        assert scope_is_allowed("R:r", role="render", mode="r")
        assert scope_is_allowed("m:w", role="metadata", mode="w")
        assert scope_is_allowed("p:rw", role="preview", mode="w")
        assert not scope_is_allowed("R:r", role="render", mode="w")
        assert not scope_is_allowed("M:r", role="original", mode="rw")
        assert not scope_is_allowed("J:r", role="manifest", mode="rw")

    def test_is_allowed_multi(self):
        scopes = "R:r m:w p:rw"
        assert any_is_allowed(scopes, role="render", mode="r")
        assert not any_is_allowed(scopes, role="original", mode="w")

    def test_role_mode_for(self):
        assert expand_scope("O:rw") == set([("original", "rw")])
        assert expand_scope("R:r m:w p:rw") == set(
            [("render", "r"), ("metadata", "w"), ("preview", "rw")]
        )
        assert expand_scope("R:a") == set(), "Unknown mode should not be returned"
        assert expand_scope("X:r") == set(), "Unknown role should not be returned"
