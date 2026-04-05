from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404
from app.models import QuickLink, User
from app.schemas.project import QuickLinkCreate, QuickLinkResponse, QuickLinkUpdate

router = APIRouter()


def _get_link_or_404(link_id: int, project_id: int, db: Session) -> QuickLink:
    link = db.query(QuickLink).filter(
        QuickLink.id == link_id, QuickLink.project_id == project_id
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link no encontrado")
    return link


@router.get("", response_model=list[QuickLinkResponse])
def list_links(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[QuickLink]:
    project = get_project_or_404(slug, db, current_user)
    return project.links


@router.post("", response_model=QuickLinkResponse, status_code=status.HTTP_201_CREATED)
def create_link(
    slug: str,
    data: QuickLinkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuickLink:
    project = get_project_or_404(slug, db, current_user)
    link = QuickLink(project_id=project.id, label=data.label, url=data.url, category=data.category)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.put("/{link_id}", response_model=QuickLinkResponse)
def update_link(
    slug: str,
    link_id: int,
    data: QuickLinkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuickLink:
    project = get_project_or_404(slug, db, current_user)
    link = _get_link_or_404(link_id, project.id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(link, field, value)
    db.commit()
    db.refresh(link)
    return link


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(
    slug: str,
    link_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    project = get_project_or_404(slug, db, current_user)
    link = _get_link_or_404(link_id, project.id, db)
    db.delete(link)
    db.commit()
