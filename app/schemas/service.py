from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ServiceBase(BaseModel):
    name: str
    url: str | None = None
    category: str = "other"
    notes: str | None = None
    project_id: int | None = None


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    category: str | None = None
    notes: str | None = None
    project_id: int | None = None


class ServiceResponse(ServiceBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
