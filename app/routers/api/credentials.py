import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Credential
from app.schemas.credential import CredentialCreate, CredentialResponse, CredentialUpdate

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_credential_or_404(cred_id: int, db: Session) -> Credential:
    cred = db.query(Credential).filter(Credential.id == cred_id).first()
    if not cred:
        logger.warning("Credencial no encontrada: id=%d", cred_id)
        raise HTTPException(status_code=404, detail="Credencial no encontrada")
    return cred


@router.get("", response_model=list[CredentialResponse])
def list_credentials(
    project_id: int | None = None,
    category: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
) -> list[Credential]:
    query = db.query(Credential)
    if project_id is not None:
        query = query.filter(Credential.project_id == project_id)
    if category:
        query = query.filter(Credential.category == category)
    if search:
        like = f"%{search}%"
        query = query.filter(
            Credential.label.ilike(like) | Credential.username.ilike(like)
        )
    return query.order_by(Credential.label).all()


@router.post("", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
def create_credential(data: CredentialCreate, db: Session = Depends(get_db)) -> Credential:
    cred = Credential(
        label=data.label,
        username=data.username,
        password=data.password,
        url=data.url,
        category=data.category,
        notes=data.notes,
        service_id=data.service_id,
        project_id=data.project_id,
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    logger.info("Credencial creada: '%s' (id=%d)", cred.label, cred.id)
    return cred


@router.get("/{cred_id}", response_model=CredentialResponse)
def get_credential(cred_id: int, db: Session = Depends(get_db)) -> Credential:
    return _get_credential_or_404(cred_id, db)


@router.put("/{cred_id}", response_model=CredentialResponse)
def update_credential(cred_id: int, data: CredentialUpdate, db: Session = Depends(get_db)) -> Credential:
    cred = _get_credential_or_404(cred_id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(cred, field, value)
    db.commit()
    db.refresh(cred)
    return cred


@router.delete("/{cred_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credential(cred_id: int, db: Session = Depends(get_db)) -> None:
    cred = _get_credential_or_404(cred_id, db)
    label = cred.label
    db.delete(cred)
    db.commit()
    logger.info("Credencial eliminada: '%s' (id=%d)", label, cred_id)
