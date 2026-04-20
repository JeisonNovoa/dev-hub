from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.project import CommandResponse, EnvVariableResponse


def _validate_http_url(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip()
    if not v.startswith(("http://", "https://")):
        raise ValueError("La URL debe comenzar con http:// o https://")
    return v


class RepoBase(BaseModel):
    name: str
    local_path: str | None = None
    github_url: str | None = None
    description: str | None = None

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, v: str | None) -> str | None:
        return _validate_http_url(v)


class RepoCreate(RepoBase):
    slug: str | None = None


class RepoUpdate(BaseModel):
    name: str | None = None
    local_path: str | None = None
    github_url: str | None = None
    description: str | None = None

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, v: str | None) -> str | None:
        return _validate_http_url(v)


class RepoResponse(RepoBase):
    id: int
    slug: str
    project_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RepoDetailResponse(RepoResponse):
    commands: list[CommandResponse] = []
    env_vars: list[EnvVariableResponse] = []
