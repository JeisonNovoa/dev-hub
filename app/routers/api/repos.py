from fastapi import APIRouter, Depends, HTTPException, status
from slugify import slugify
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404
from app.models import Command, EnvVariable, Repo, User
from app.schemas.project import CommandCreate, CommandResponse, CommandUpdate, EnvVariableCreate, EnvVariableResponse, EnvVariableUpdate
from app.schemas.repo import RepoCreate, RepoDetailResponse, RepoResponse, RepoUpdate

router = APIRouter()


def _get_repo_or_404(project_id: int, repo_slug: str, db: Session) -> Repo:
    repo = db.query(Repo).filter(Repo.project_id == project_id, Repo.slug == repo_slug).first()
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repo '{repo_slug}' no encontrado")
    return repo


@router.get("", response_model=list[RepoResponse])
def list_repos(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Repo]:
    project = get_project_or_404(slug, db, current_user)
    return db.query(Repo).filter(Repo.project_id == project.id).order_by(Repo.name).all()


@router.post("", response_model=RepoResponse, status_code=status.HTTP_201_CREATED)
def create_repo(
    slug: str,
    data: RepoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Repo:
    project = get_project_or_404(slug, db, current_user)
    repo_slug = data.slug or slugify(data.name)
    existing = db.query(Repo).filter(Repo.project_id == project.id, Repo.slug == repo_slug).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Ya existe un repo con slug '{repo_slug}'")
    repo = Repo(
        project_id=project.id,
        name=data.name,
        slug=repo_slug,
        local_path=data.local_path,
        github_url=data.github_url,
        description=data.description,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


@router.get("/{repo_slug}", response_model=RepoDetailResponse)
def get_repo(
    slug: str,
    repo_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Repo:
    project = get_project_or_404(slug, db, current_user)
    return _get_repo_or_404(project.id, repo_slug, db)


@router.put("/{repo_slug}", response_model=RepoResponse)
def update_repo(
    slug: str,
    repo_slug: str,
    data: RepoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Repo:
    project = get_project_or_404(slug, db, current_user)
    repo = _get_repo_or_404(project.id, repo_slug, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(repo, field, value)
    db.commit()
    db.refresh(repo)
    return repo


@router.delete("/{repo_slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_repo(
    slug: str,
    repo_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    project = get_project_or_404(slug, db, current_user)
    repo = _get_repo_or_404(project.id, repo_slug, db)
    db.delete(repo)
    db.commit()


# ---- Comandos del repo ----

@router.post("/{repo_slug}/commands", response_model=CommandResponse, status_code=status.HTTP_201_CREATED)
def create_repo_command(
    slug: str,
    repo_slug: str,
    data: CommandCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Command:
    project = get_project_or_404(slug, db, current_user)
    repo = _get_repo_or_404(project.id, repo_slug, db)
    cmd = Command(
        project_id=project.id,
        repo_id=repo.id,
        label=data.label,
        command=data.command,
        order=data.order,
        type=data.type,
    )
    db.add(cmd)
    db.commit()
    db.refresh(cmd)
    return cmd


@router.put("/{repo_slug}/commands/{cmd_id}", response_model=CommandResponse)
def update_repo_command(
    slug: str,
    repo_slug: str,
    cmd_id: int,
    data: CommandUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Command:
    project = get_project_or_404(slug, db, current_user)
    repo = _get_repo_or_404(project.id, repo_slug, db)
    cmd = db.query(Command).filter(Command.id == cmd_id, Command.repo_id == repo.id).first()
    if not cmd:
        raise HTTPException(status_code=404, detail="Comando no encontrado")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(cmd, field, value)
    db.commit()
    db.refresh(cmd)
    return cmd


@router.delete("/{repo_slug}/commands/{cmd_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_repo_command(
    slug: str,
    repo_slug: str,
    cmd_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    project = get_project_or_404(slug, db, current_user)
    repo = _get_repo_or_404(project.id, repo_slug, db)
    cmd = db.query(Command).filter(Command.id == cmd_id, Command.repo_id == repo.id).first()
    if not cmd:
        raise HTTPException(status_code=404, detail="Comando no encontrado")
    db.delete(cmd)
    db.commit()


# ---- Env vars del repo ----

@router.post("/{repo_slug}/env-vars", response_model=EnvVariableResponse, status_code=status.HTTP_201_CREATED)
def create_repo_env_var(
    slug: str,
    repo_slug: str,
    data: EnvVariableCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EnvVariable:
    project = get_project_or_404(slug, db, current_user)
    repo = _get_repo_or_404(project.id, repo_slug, db)
    env_var = EnvVariable(
        project_id=project.id,
        repo_id=repo.id,
        key=data.key,
        value=data.value,
        description=data.description,
    )
    db.add(env_var)
    db.commit()
    db.refresh(env_var)
    return env_var


@router.put("/{repo_slug}/env-vars/{env_id}", response_model=EnvVariableResponse)
def update_repo_env_var(
    slug: str,
    repo_slug: str,
    env_id: int,
    data: EnvVariableUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EnvVariable:
    project = get_project_or_404(slug, db, current_user)
    repo = _get_repo_or_404(project.id, repo_slug, db)
    env_var = db.query(EnvVariable).filter(EnvVariable.id == env_id, EnvVariable.repo_id == repo.id).first()
    if not env_var:
        raise HTTPException(status_code=404, detail="Variable no encontrada")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(env_var, field, value)
    db.commit()
    db.refresh(env_var)
    return env_var


@router.delete("/{repo_slug}/env-vars/{env_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_repo_env_var(
    slug: str,
    repo_slug: str,
    env_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    project = get_project_or_404(slug, db, current_user)
    repo = _get_repo_or_404(project.id, repo_slug, db)
    env_var = db.query(EnvVariable).filter(EnvVariable.id == env_id, EnvVariable.repo_id == repo.id).first()
    if not env_var:
        raise HTTPException(status_code=404, detail="Variable no encontrada")
    db.delete(env_var)
    db.commit()
