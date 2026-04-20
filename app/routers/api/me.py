import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.user import PasswordChange, UserResponse, UserUpdate

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.put("", response_model=UserResponse)
def update_me(
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    new_email = data.email.lower().strip()
    if new_email != current_user.email:
        conflict = db.query(User).filter(User.email == new_email).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese email")
    current_user.email = new_email
    db.commit()
    db.refresh(current_user)
    logger.info("Email actualizado: user_id=%s", current_user.id)
    return current_user


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
    current_user.hashed_password = hash_password(data.new_password)
    db.commit()
    logger.info("Contraseña cambiada: user_id=%s", current_user.id)
