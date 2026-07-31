import uuid

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentAdminOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    full_name: str
    roles: list[str]
