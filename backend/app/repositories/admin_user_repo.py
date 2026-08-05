import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ValidationAppError
from app.core.security import hash_password
from app.models.admin_user import AdminUser
from app.models.admin_user_role import AdminUserRole
from app.models.role import Role
from app.schemas.admin_user import AdminUserCreateRequest, AdminUserUpdateRequest

INVITE_TOKEN_EXPIRE_DAYS = 7
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 60


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


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


def create(db: Session, organization_id: uuid.UUID, request: AdminUserCreateRequest) -> tuple[AdminUser, str]:
    """Creates the user with an unusable password (a random string only this
    call ever sees) plus an invite token — nobody can sign in until they
    follow the invite link and set their own password via accept_invite()
    below. Returns (admin_user, raw_invite_token); the raw token is never
    persisted, only its SHA-256 hash, so a database read alone can't be used
    to accept someone else's invite."""
    raw_invite_token = secrets.token_urlsafe(32)
    admin_user = AdminUser(
        organization_id=organization_id,
        email=request.email.lower(),
        password_hash=hash_password(secrets.token_urlsafe(32)),
        full_name=request.full_name,
        invite_token_hash=_hash_token(raw_invite_token),
        invite_expires_at=datetime.now(UTC) + timedelta(days=INVITE_TOKEN_EXPIRE_DAYS),
    )
    db.add(admin_user)
    db.flush()

    for role_id in _resolve_role_ids(db, request.roles):
        db.add(AdminUserRole(admin_user_id=admin_user.id, role_id=role_id))
    db.flush()
    return admin_user, raw_invite_token


def get_by_invite_token(db: Session, raw_token: str) -> AdminUser | None:
    token_hash = _hash_token(raw_token)
    stmt = select(AdminUser).where(AdminUser.invite_token_hash == token_hash)
    return db.execute(stmt).scalar_one_or_none()


def accept_invite(db: Session, admin_user: AdminUser, *, new_password_hash: str) -> None:
    admin_user.password_hash = new_password_hash
    admin_user.invite_token_hash = None
    admin_user.invite_expires_at = None
    admin_user.is_active = True
    db.flush()


def set_password_reset_token(db: Session, admin_user: AdminUser) -> str:
    """Generates a fresh single-use reset token, overwriting any previous
    unused one for this account (only the most recently requested link ever
    works). Returns the raw token — only its SHA-256 hash is persisted, same
    discipline as the invite token above."""
    raw_token = secrets.token_urlsafe(32)
    admin_user.password_reset_token_hash = _hash_token(raw_token)
    admin_user.password_reset_expires_at = datetime.now(UTC) + timedelta(
        minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
    )
    db.flush()
    return raw_token


def get_by_password_reset_token(db: Session, raw_token: str) -> AdminUser | None:
    token_hash = _hash_token(raw_token)
    stmt = select(AdminUser).where(AdminUser.password_reset_token_hash == token_hash)
    return db.execute(stmt).scalar_one_or_none()


def reset_password(db: Session, admin_user: AdminUser, *, new_password_hash: str) -> None:
    """Sets a new password and clears the reset token (single-use) — also
    clears any active account lockout, since successfully proving control of
    the registered email is itself a strong identity check, and there's no
    other self-service way to recover from a lockout today."""
    admin_user.password_hash = new_password_hash
    admin_user.password_reset_token_hash = None
    admin_user.password_reset_expires_at = None
    admin_user.failed_login_attempts = 0
    admin_user.locked_until = None
    db.flush()


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


def is_locked(admin_user: AdminUser) -> bool:
    return admin_user.locked_until is not None and admin_user.locked_until > datetime.now(UTC)


def register_failed_login(
    db: Session, admin_user: AdminUser, *, threshold: int, lockout_minutes: int
) -> bool:
    """Increments the failure counter and locks the account once `threshold`
    consecutive failures are reached. Returns True if this call is what
    triggered the lock (so the caller can audit-log it distinctly)."""
    admin_user.failed_login_attempts += 1
    just_locked = False
    if admin_user.failed_login_attempts >= threshold:
        admin_user.locked_until = datetime.now(UTC) + timedelta(minutes=lockout_minutes)
        admin_user.failed_login_attempts = 0
        just_locked = True
    db.flush()
    return just_locked


def reset_failed_login(db: Session, admin_user: AdminUser) -> None:
    admin_user.failed_login_attempts = 0
    admin_user.locked_until = None
    db.flush()
