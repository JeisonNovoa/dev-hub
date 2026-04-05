from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_project_or_404
from app.models import EnvVariable
from app.schemas.project import EnvVariableCreate, EnvVariableResponse, EnvVariableUpdate

router = APIRouter()


def _get_env_var_or_404(env_id: int, project_id: int, db: Session) -> EnvVariable:
    env_var = db.query(EnvVariable).filter(
        EnvVariable.id == env_id, EnvVariable.project_id == project_id
    ).first()
    if not env_var:
        raise HTTPException(status_code=404, detail="Variable de entorno no encontrada")
    return env_var


@router.get("", response_model=list[EnvVariableResponse])
def list_env_vars(slug: str, db: Session = Depends(get_db)) -> list[EnvVariable]:
    project = get_project_or_404(slug, db)
    return project.env_vars


@router.post("", response_model=EnvVariableResponse, status_code=status.HTTP_201_CREATED)
def create_env_var(slug: str, data: EnvVariableCreate, db: Session = Depends(get_db)) -> EnvVariable:
    project = get_project_or_404(slug, db)
    env_var = EnvVariable(project_id=project.id, key=data.key, value=data.value, description=data.description)
    db.add(env_var)
    db.commit()
    db.refresh(env_var)
    return env_var


@router.put("/{env_id}", response_model=EnvVariableResponse)
def update_env_var(slug: str, env_id: int, data: EnvVariableUpdate, db: Session = Depends(get_db)) -> EnvVariable:
    project = get_project_or_404(slug, db)
    env_var = _get_env_var_or_404(env_id, project.id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(env_var, field, value)
    db.commit()
    db.refresh(env_var)
    return env_var


@router.delete("/{env_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_env_var(slug: str, env_id: int, db: Session = Depends(get_db)) -> None:
    project = get_project_or_404(slug, db)
    env_var = _get_env_var_or_404(env_id, project.id, db)
    db.delete(env_var)
    db.commit()
