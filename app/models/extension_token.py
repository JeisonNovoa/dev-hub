from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.common import Base, TimestampMixin

# Vigencia por defecto de un token de extensión. Un token robado solo sirve
# durante esta ventana; pasado ese tiempo hay que volver a hacer login.
DEFAULT_TOKEN_TTL_DAYS = 90
# Máximo de tokens activos (no revocados, no expirados) por usuario. Evita que
# un atacante con la contraseña genere tokens infinitos.
MAX_ACTIVE_TOKENS = 5


class ExtensionToken(Base, TimestampMixin):
    """Token de acceso para la extensión del navegador.

    Se guarda solo el hash SHA-256 del token; el token en claro se entrega una
    única vez al hacer login desde la extensión. Revocable desde la web.
    Expira a los DEFAULT_TOKEN_TTL_DAYS días.
    """

    __tablename__ = "extension_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="Extensión")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
