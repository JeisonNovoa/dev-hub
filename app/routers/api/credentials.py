import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Credential, User
from app.schemas.credential import CredentialCreate, CredentialResponse, CredentialUpdate
from app.schemas.pagination import Page

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_credential_or_404(cred_id: int, user_id: int, db: Session) -> Credential:
    cred = (
        db.query(Credential)
        .filter(Credential.id == cred_id, Credential.user_id == user_id, Credential.deleted_at.is_(None))
        .first()
    )
    if not cred:
        logger.warning("Credencial no encontrada: id=%d", cred_id)
        raise HTTPException(status_code=404, detail="Credencial no encontrada")
    return cred


@router.get("", response_model=Page[CredentialResponse])
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


@router.post("", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
def create_credential(
    data: CredentialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Credential:
    cred = Credential(
        label=data.label,
        username=data.username,
        password=data.password,
        url=data.url,
        category=data.category,
        notes=data.notes,
        service_id=data.service_id,
        project_id=data.project_id,
        user_id=current_user.id,
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    logger.info("Credencial creada: '%s' (id=%d)", cred.label, cred.id)
    return cred


@router.get("/{cred_id}", response_model=CredentialResponse)
def get_credential(
    cred_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Credential:
    return _get_credential_or_404(cred_id, current_user.id, db)


@router.put("/{cred_id}", response_model=CredentialResponse)
def update_credential(
    cred_id: int,
    data: CredentialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Credential:
    cred = _get_credential_or_404(cred_id, current_user.id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(cred, field, value)
    db.commit()
    db.refresh(cred)
    return cred


@router.delete("/{cred_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credential(
    cred_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    from datetime import datetime, timezone
    cred = _get_credential_or_404(cred_id, current_user.id, db)
    cred.deleted_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Credencial movida a papelera: '%s' (id=%d)", cred.label, cred_id)
