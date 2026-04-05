from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Service
from app.schemas.service import ServiceCreate, ServiceResponse, ServiceUpdate

router = APIRouter()


def _get_service_or_404(service_id: int, db: Session) -> Service:
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    return service


@router.get("", response_model=list[ServiceResponse])
def list_services(project_id: int | None = None, db: Session = Depends(get_db)) -> list[Service]:
    query = db.query(Service)
    if project_id is not None:
        query = query.filter(Service.project_id == project_id)
    return query.order_by(Service.name).all()


@router.post("", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
def create_service(data: ServiceCreate, db: Session = Depends(get_db)) -> Service:
    service = Service(
        name=data.name,
        url=data.url,
        category=data.category,
        notes=data.notes,
        project_id=data.project_id,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@router.get("/{service_id}", response_model=ServiceResponse)
def get_service(service_id: int, db: Session = Depends(get_db)) -> Service:
    return _get_service_or_404(service_id, db)


@router.put("/{service_id}", response_model=ServiceResponse)
def update_service(service_id: int, data: ServiceUpdate, db: Session = Depends(get_db)) -> Service:
    service = _get_service_or_404(service_id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(service, field, value)
    db.commit()
    db.refresh(service)
    return service


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(service_id: int, db: Session = Depends(get_db)) -> None:
    service = _get_service_or_404(service_id, db)
    db.delete(service)
    db.commit()
