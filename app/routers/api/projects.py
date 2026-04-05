import logging

from fastapi import APIRouter, Depends, HTTPException, status
from slugify import slugify
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_project_or_404
from app.models import Project
from app.schemas.project import ProjectCreate, ProjectDetailResponse, ProjectResponse, ProjectUpdate

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=list[ProjectResponse])
def list_projects(status: str | None = None, db: Session = Depends(get_db)) -> list[Project]:
    query = db.query(Project)
    if status:
        query = query.filter(Project.status == status)
    return query.order_by(Project.name).all()


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    slug = data.slug or slugify(data.name)
    existing = db.query(Project).filter(Project.slug == slug).first()
    if existing:
        logger.warning("Intento de crear proyecto con slug duplicado: '%s'", slug)
        raise HTTPException(status_code=409, detail=f"Ya existe un proyecto con slug '{slug}'")
    project = Project(
        name=data.name,
        slug=slug,
        description=data.description,
        tech_stack=data.tech_stack,
        status=data.status,
        notes=data.notes,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info("Proyecto creado: '%s' (id=%d)", project.slug, project.id)
    return project


@router.get("/{slug}", response_model=ProjectDetailResponse)
def get_project(slug: str, db: Session = Depends(get_db)) -> Project:
    return get_project_or_404(slug, db)


@router.put("/{slug}", response_model=ProjectResponse)
def update_project(slug: str, data: ProjectUpdate, db: Session = Depends(get_db)) -> Project:
    project = get_project_or_404(slug, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.patch("/{slug}", response_model=ProjectResponse)
def patch_project(slug: str, data: ProjectUpdate, db: Session = Depends(get_db)) -> Project:
    return update_project(slug, data, db)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(slug: str, db: Session = Depends(get_db)) -> None:
    project = get_project_or_404(slug, db)
    db.delete(project)
    db.commit()
    logger.info("Proyecto eliminado: '%s'", slug)
