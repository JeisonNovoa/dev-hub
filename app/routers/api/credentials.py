import logging

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Credential, User
from app.schemas.credential import CredentialCreate, CredentialResponse, CredentialUpdate
from app.schemas.pagination import Page
from app.services import credentials as cred_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "",
    response_model=Page[CredentialResponse],
    summary="Listar credenciales",
    description="Lista paginada de credenciales del usuario, con filtros por proyecto, categoría y búsqueda. No incluye contraseñas en claro salvo el campo cifrado.",
)
def list_credentials(
    project_id: int | None = None,
    category: str | None = None,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[CredentialResponse]:
    query = db.query(Credential).filter(
        Credential.user_id == current_user.id, Credential.deleted_at.is_(None)
    )
    if project_id is not None:
        query = query.filter(Credential.project_id == project_id)
    if category:
        query = query.filter(Credential.category == category)
    if search:
        like = f"%{search}%"
        query = query.filter(
            Credential.label.ilike(like) | Credential.username.ilike(like)
        )
    query = query.order_by(Credential.label)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "",
    response_model=CredentialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear credencial",
    description="Guarda una credencial. La contraseña se cifra en reposo (Fernet). Puede asociarse a un proyecto o servicio.",
)
def create_credential(
    data: CredentialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Credential:
    return cred_service.create(
        db,
        current_user,
        label=data.label,
        username=data.username,
        password=data.password,
        url=data.url,
        category=data.category,
        notes=data.notes,
        service_id=data.service_id,
        project_id=data.project_id,
    )


@router.get("/{cred_id}", response_model=CredentialResponse)
def get_credential(
    cred_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Credential:
    return cred_service.get_owned_or_404(db, cred_id, current_user.id)


@router.put("/{cred_id}", response_model=CredentialResponse)
def update_credential(
    cred_id: int,
    data: CredentialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Credential:
    cred = cred_service.get_owned_or_404(db, cred_id, current_user.id)
    return cred_service.update(db, cred, data.model_dump(exclude_unset=True))


@router.delete("/{cred_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credential(
    cred_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    cred = cred_service.get_owned_or_404(db, cred_id, current_user.id)
    cred_service.soft_delete(db, cred)
