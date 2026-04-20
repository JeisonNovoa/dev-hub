from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Service, User
from app.schemas.pagination import Page
from app.schemas.service import ServiceCreate, ServiceResponse, ServiceUpdate

router = APIRouter()


def _get_service_or_404(service_id: int, user_id: int, db: Session) -> Service:
    service = db.query(Service).filter(Service.id == service_id, Service.user_id == user_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    return service


@router.get("", response_model=Page[ServiceResponse])
def list_services(
    project_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[ServiceResponse]:
    query = db.query(Service).filter(Service.user_id == current_user.id)
    if project_id is not None:
        query = query.filter(Service.project_id == project_id)
    query = query.order_by(Service.name)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
def create_service(
    data: ServiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Service:
    service = Service(
        name=data.name,
        url=data.url,
        category=data.category,
        notes=data.notes,
        project_id=data.project_id,
        user_id=current_user.id,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@router.get("/{service_id}", response_model=ServiceResponse)
def get_service(
    service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Service:
    return _get_service_or_404(service_id, current_user.id, db)


@router.put("/{service_id}", response_model=ServiceResponse)
def update_service(
    service_id: int,
    data: ServiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Service:
    service = _get_service_or_404(service_id, current_user.id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(service, field, value)
    db.commit()
    db.refresh(service)
    return service


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(
    service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    service = _get_service_or_404(service_id, current_user.id, db)
    db.delete(service)
    db.commit()
