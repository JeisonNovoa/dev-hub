from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


def _validate_http_url(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip()
    if not v.startswith(("http://", "https://")):
        raise ValueError("La URL debe comenzar con http:// o https://")
    return v


# --- EnvVariable ---

class EnvVariableBase(BaseModel):
    key: str
    value: str | None = None
    description: str | None = None


class EnvVariableCreate(EnvVariableBase):
    pass


class EnvVariableUpdate(BaseModel):
    key: str | None = None
    value: str | None = None
    description: str | None = None


class EnvVariableResponse(EnvVariableBase):
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Command ---

class CommandBase(BaseModel):
    label: str
    command: str
    order: int = 0
    type: str = "other"


class CommandCreate(CommandBase):
    pass


class CommandUpdate(BaseModel):
    label: str | None = None
    command: str | None = None
    order: int | None = None
    type: str | None = None


class CommandResponse(CommandBase):
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- QuickLink ---

class QuickLinkBase(BaseModel):
    label: str
    url: str
    category: str = "other"

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("La URL debe comenzar con http:// o https://")
        return v


class QuickLinkCreate(QuickLinkBase):
    pass


class QuickLinkUpdate(BaseModel):
    label: str | None = None
    url: str | None = None
    category: str | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        return _validate_http_url(v)


class QuickLinkResponse(QuickLinkBase):
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Project ---

class ProjectBase(BaseModel):
    name: str
    description: str | None = None
    tech_stack: list[str] = []
    status: str = "active"
    notes: str | None = None


class ProjectCreate(ProjectBase):
    slug: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tech_stack: list[str] | None = None
    status: str | None = None
    notes: str | None = None


class ProjectResponse(ProjectBase):
    id: int
    slug: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProjectDetailResponse(ProjectResponse):
    env_vars: list[EnvVariableResponse] = []
    commands: list[CommandResponse] = []
    links: list[QuickLinkResponse] = []
