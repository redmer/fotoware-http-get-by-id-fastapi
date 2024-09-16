import typing as t

type Role = t.Literal["metadata", "original", "render", "preview", "manifest"]
type Mode = t.Literal["r", "w", "rw"]
type ScopeSpec = tuple[Role, Mode]
type ScopeStr = str

_Role2RoleCode: dict[Role, str] = {
    "manifest": "J",
    "metadata": "m",
    "original": "O",
    "render": "R",
    "preview": "p",
}


def scope_for(role: Role, mode: Mode, /) -> ScopeStr:
    """Abbreviates the role and mode to a scope string for use in a token."""
    return f"{_Role2RoleCode[role]}:{mode}"


def expand_scope(scope: ScopeStr) -> set[ScopeSpec]:
    result = set()
    for s in scope.split():
        role, mode = s.split(":")

        if not any(mode == v for v in ["r", "w", "rw"]):
            continue

        for key, value in _Role2RoleCode.items():
            if value == role:
                result.add((key, mode))

    return result


def scope_is_allowed(
    scope: ScopeStr, /, role: Role | None = None, mode: Mode | None = None
) -> bool:
    """
    Returns if the scope string matches the role and mode passed.

    Args:
        scope: Untrusted scope string, coming from a token.
        role: Required role for a scope to have. Set to None to allow any role.
        mode: Required mode for a scope to have. Set to None to allow any mode.

    Returns:
        True if the required role and modes are included in this scope string.
    """
    r, m = scope.split(":")

    role_is_allowed = role is None or r == _Role2RoleCode[role]
    # mode is hierarchical: rw implies both r and w -> `x in y`
    mode_is_allowed = mode is None or mode in m

    return role_is_allowed and mode_is_allowed


def any_is_allowed(
    scopes: ScopeStr, *, role: Role | None = None, mode: Mode | None = None
) -> bool:
    """
    Returns if the scope string matches the role and mode passed.

    Args:
        scope: Untrusted scope string, potentially space separated, from a token.
        role: Required role for a scope to have. Set to None to allow any role.
        mode: Required mode for a scope to have. Set to None to allow any mode.

    Returns:
        True if the required role and modes are included in this scope string.
    """
    return any(scope_is_allowed(s, role=role, mode=mode) for s in scopes.split())
