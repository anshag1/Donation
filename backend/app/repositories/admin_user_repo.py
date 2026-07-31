import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ValidationAppError
from app.core.security import hash_password
from app.models.admin_user import AdminUser
from app.models.admin_user_role import AdminUserRole
from app.models.role import Role
from app.schemas.admin_user import AdminUserCreateRequest, AdminUserUpdateRequest


def get_by_email(db: Session, email: str) -> AdminUser | None:
    stmt = (
        select(AdminUser)
        .where(AdminUser.email == email.lower())
        .options(joinedload(AdminUser.role_links))
    )
    return db.execute(stmt).unique().scalar_one_or_none()


def get_by_id(db: Session, admin_user_id: uuid.UUID) -> AdminUser | None:
    stmt = (
        select(AdminUser)
        .where(AdminUser.id == admin_user_id)
        .options(joinedload(AdminUser.role_links))
    )
    return db.execute(stmt).unique().scalar_one_or_none()


def get_by_id_in_org(db: Session, organization_id: uuid.UUID, admin_user_id: uuid.UUID) -> AdminUser | None:
    """Org-scoped lookup for admin-facing user-management routes — `get_by_id`
    above is intentionally NOT org-scoped (used only during auth, where the
    id comes from a JWT this server itself issued for that org)."""
    stmt = (
        select(AdminUser)
        .where(AdminUser.id == admin_user_id, AdminUser.organization_id == organization_id)
        .options(joinedload(AdminUser.role_links))
    )
    return db.execute(stmt).unique().scalar_one_or_none()


def list_all(
    db: Session, organization_id: uuid.UUID, *, page: int, page_size: int
) -> tuple[list[AdminUser], int]:
    base = select(AdminUser).where(AdminUser.organization_id == organization_id)
    total = db.execute(select(func.count()).select_from(base.with_only_columns(AdminUser.id).subquery())).scalar_one()
    items = (
        db.execute(
            base.options(joinedload(AdminUser.role_links))
            .order_by(AdminUser.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .unique()
        .scalars()
        .all()
    )
    return list(items), total


def _resolve_role_ids(db: Session, role_names: list[str]) -> list[uuid.UUID]:
    stmt = select(Role).where(Role.name.in_(role_names))
    roles = db.execute(stmt).scalars().all()
    if len(roles) != len(set(role_names)):
        found = {r.name for r in roles}
        missing = set(role_names) - found
        raise ValidationAppError(f"Unknown role(s): {', '.join(sorted(missing))}")
    return [r.id for r in roles]


def create(db: Session, organization_id: uuid.UUID, request: AdminUserCreateRequest) -> AdminUser:
    admin_user = AdminUser(
        organization_id=organization_id,
        email=request.email.lower(),
        password_hash=hash_password(request.password),
        full_name=request.full_name,
    )
    db.add(admin_user)
    db.flush()

    for role_id in _resolve_role_ids(db, request.roles):
        db.add(AdminUserRole(admin_user_id=admin_user.id, role_id=role_id))
    db.flush()
    return admin_user


def update(db: Session, admin_user: AdminUser, request: AdminUserUpdateRequest) -> AdminUser:
    if request.full_name is not None:
        admin_user.full_name = request.full_name
    if request.is_active is not None:
        admin_user.is_active = request.is_active
    if request.roles is not None:
        role_ids = _resolve_role_ids(db, request.roles)
        for link in list(admin_user.role_links):
            db.delete(link)
        db.flush()
        for role_id in role_ids:
            db.add(AdminUserRole(admin_user_id=admin_user.id, role_id=role_id))
    db.flush()
    return admin_user


def touch_last_login(db: Session, admin_user: AdminUser) -> None:
    admin_user.last_login_at = func.now()
    db.flush()
