"""Códigos de recuperación de un solo uso para 2FA.

Cuando el usuario activa 2FA, se generan 10 códigos de un solo uso. Se
muestran UNA sola vez y se guardan hasheados (bcrypt). Si el usuario pierde
el autenticador, puede usar uno de estos códigos en lugar del TOTP en el
login. Cada código se marca como usado tras emplearse.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.common import Base, TimestampMixin


class RecoveryCode(Base, TimestampMixin):
    __tablename__ = "recovery_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Hash bcrypt del código en claro. El código claro nunca se persiste.
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
