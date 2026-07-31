import uuid

from pydantic import BaseModel, EmailStr, Field


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    logo_url: str | None
    signature_image_url: str | None
    contact_email: str | None
    pan_number: str | None
    address: str | None
    receipt_prefix: str
    status: str


class OrganizationUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    logo_url: str | None = Field(default=None, max_length=500)
    signature_image_url: str | None = Field(default=None, max_length=500)
    contact_email: EmailStr | None = None
    pan_number: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=500)
    receipt_prefix: str | None = Field(default=None, min_length=1, max_length=20)
