from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


def _validate_http_url(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip()
    if not v.startswith(("http://", "https://")):
        raise ValueError("La URL debe comenzar con http:// o https://")
    return v


class ServiceBase(BaseModel):
    name: str
    url: str | None = None
    category: str = "other"
    notes: str | None = None
    project_id: int | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        return _validate_http_url(v)


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    category: str | None = None
    notes: str | None = None
    project_id: int | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        return _validate_http_url(v)


class ServiceResponse(ServiceBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
