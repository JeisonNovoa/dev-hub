from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CredentialBase(BaseModel):
    label: str
    username: str | None = None
    password: str | None = None
    url: str | None = None
    category: str = "project"
    login_via: str = "email"
    notes: str | None = None
    service_id: int | None = None
    project_id: int | None = None


class CredentialCreate(CredentialBase):
    pass


class CredentialUpdate(BaseModel):
    label: str | None = None
    username: str | None = None
    password: str | None = None
    url: str | None = None
    category: str | None = None
    login_via: str = "email"
    notes: str | None = None
    service_id: int | None = None
    project_id: int | None = None


class CredentialResponse(CredentialBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
