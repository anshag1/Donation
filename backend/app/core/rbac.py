from collections.abc import Callable

from fastapi import Depends

from app.core.exceptions import ForbiddenError
from app.deps import CurrentAdmin, get_current_admin


def require_role(*allowed_roles: str) -> Callable[..., CurrentAdmin]:
    """FastAPI dependency: 403s unless the caller has at least one of the
    given roles. Enforced server-side — see docs/01-prd.md §1.9 for the
    role/permission matrix this must always match.
    """

    def _check(admin: CurrentAdmin = Depends(get_current_admin)) -> CurrentAdmin:
        if not set(admin.roles) & set(allowed_roles):
            raise ForbiddenError(
                f"Requires one of roles: {', '.join(allowed_roles)}"
            )
        return admin

    return _check
