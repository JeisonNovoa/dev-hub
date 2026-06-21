from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.crypto import EncryptedText
from app.models.common import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Última vez que se cambió la contraseña. Cualquier cookie de sesión con
    # iat anterior queda inválida al comparar. Servidor-side invalidation.
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    # 2FA (TOTP): el secreto se guarda cifrado y solo cuenta como activo cuando
    # el usuario lo confirmó con un código válido (totp_confirmed_at no nulo).
    totp_secret: Mapped[str | None] = mapped_column(EncryptedText, nullable=True, default=None)
    totp_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    @property
    def totp_enabled(self) -> bool:
        return bool(self.totp_secret and self.totp_confirmed_at)
