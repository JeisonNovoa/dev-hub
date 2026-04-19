from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Credential, Project, Service, User
from app.schemas.credential import CredentialResponse
from app.schemas.project import (
    CommandResponse,
    EnvVariableResponse,
    ProjectResponse,
    QuickLinkResponse,
)
from app.schemas.repo import RepoDetailResponse
from app.schemas.service import ServiceResponse

router = APIRouter()


@router.get("")
def export_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    projects = (
        db.query(Project)
        .filter(Project.user_id == current_user.id, Project.deleted_at.is_(None))
        .order_by(Project.name)
        .all()
    )
    credentials = (
        db.query(Credential)
        .filter(Credential.user_id == current_user.id, Credential.deleted_at.is_(None))
        .order_by(Credential.label)
        .all()
    )
    services = db.query(Service).filter(Service.user_id == current_user.id).order_by(Service.name).all()

    projects_data = []
    for p in projects:
        project_dict = ProjectResponse.model_validate(p).model_dump()
        project_dict["env_vars"] = [EnvVariableResponse.model_validate(ev).model_dump() for ev in p.env_vars]
        project_dict["commands"] = [CommandResponse.model_validate(c).model_dump() for c in p.commands]
        project_dict["links"] = [QuickLinkResponse.model_validate(l).model_dump() for l in p.links]
        project_dict["repos"] = [RepoDetailResponse.model_validate(r).model_dump() for r in p.repos]
        projects_data.append(project_dict)

    return {
        "projects": projects_data,
        "credentials": [CredentialResponse.model_validate(c).model_dump() for c in credentials],
        "services": [ServiceResponse.model_validate(s).model_dump() for s in services],
    }
