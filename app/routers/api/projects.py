import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slugify import slugify
from sqlalchemy import Text, cast
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404
from app.models import Project, User
from app.schemas.pagination import Page
from app.schemas.project import ProjectCreate, ProjectDetailResponse, ProjectResponse, ProjectUpdate

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=Page[ProjectResponse])
def list_projects(
    status: str | None = None,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[ProjectResponse]:
    query = db.query(Project).filter(Project.user_id == current_user.id, Project.deleted_at.is_(None))
    if status:
        query = query.filter(Project.status == status)
    if search:
        like = f"%{search}%"
        query = query.filter(
            Project.name.ilike(like)
            | Project.description.ilike(like)
            | Project.notes.ilike(like)
            | cast(Project.tech_stack, Text).ilike(like)
        )
    query = query.order_by(Project.name)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Project:
    slug = data.slug or slugify(data.name)
    existing = db.query(Project).filter(
        Project.slug == slug, Project.user_id == current_user.id
    ).first()
    if existing:
        logger.warning("Intento de crear proyecto con slug duplicado: '%s' (user=%d)", slug, current_user.id)
        raise HTTPException(status_code=409, detail=f"Ya existe un proyecto con slug '{slug}'")
    project = Project(
        name=data.name,
        slug=slug,
        description=data.description,
        tech_stack=data.tech_stack,
        status=data.status,
        notes=data.notes,
        user_id=current_user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info("Proyecto creado: '%s' (id=%d)", project.slug, project.id)
    return project


@router.get("/{slug}", response_model=ProjectDetailResponse)
def get_project(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Project:
    return get_project_or_404(slug, db, current_user)


@router.put("/{slug}", response_model=ProjectResponse)
def update_project(
    slug: str,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Project:
    project = get_project_or_404(slug, db, current_user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.patch("/{slug}", response_model=ProjectResponse)
def patch_project(
    slug: str,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Project:
    return update_project(slug, data, db, current_user)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    from datetime import datetime, timezone
    project = get_project_or_404(slug, db, current_user)
    project.deleted_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Proyecto movido a papelera: '%s'", slug)
