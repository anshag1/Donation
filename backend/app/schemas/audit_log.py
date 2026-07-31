import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: uuid.UUID
    actor_admin_user_id: uuid.UUID | None
    actor_email: str | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    before: dict | None
    after: dict | None
    ip_address: str | None
    created_at: datetime
