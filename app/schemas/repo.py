from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.project import CommandResponse, EnvVariableResponse


class RepoBase(BaseModel):
    name: str
    local_path: str | None = None
    github_url: str | None = None
    description: str | None = None


class RepoCreate(RepoBase):
    slug: str | None = None


class RepoUpdate(BaseModel):
    name: str | None = None
    local_path: str | None = None
    github_url: str | None = None
    description: str | None = None


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
