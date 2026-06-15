"""Página de seguridad de la cuenta: activar/desactivar 2FA (TOTP)."""

import logging
from datetime import datetime, timezone

import pyotp
import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password, verify_totp
from app.database import get_db
from app.dependencies import get_current_user
from app.jinja import templates
from app.models import User

MIN_PASSWORD_LEN = 8

router = APIRouter()
logger = logging.getLogger(__name__)


def _qr_svg(uri: str) -> str:
    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage)
    return img.to_string(encoding="unicode")


def _render(request: Request, user: User, error: str | None = None, success: str | None = None) -> HTMLResponse:
    """Renderiza la página según el estado: sin 2FA / configurando (QR) / activo."""
    context: dict = {
        "request": request,
        "current_user": user,
        "error": error,
        "success": success,
        "qr_svg": None,
        "manual_secret": None,
    }
    if user.totp_secret and not user.totp_confirmed_at:
        uri = pyotp.TOTP(user.totp_secret).provisioning_uri(name=user.email, issuer_name="Dev Hub")
        context["qr_svg"] = _qr_svg(uri)
        context["manual_secret"] = user.totp_secret
    return templates.TemplateResponse("security/settings.html", context)


@router.get("/seguridad", response_class=HTMLResponse)
def security_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    return _render(request, current_user)


@router.post("/ui/seguridad/2fa/iniciar", response_class=HTMLResponse)
def totp_start(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    if current_user.totp_enabled:
        return _render(request, current_user, error="El 2FA ya está activo.")
    current_user.totp_secret = pyotp.random_base32()
    current_user.totp_confirmed_at = None
    db.commit()
    logger.info("Configuración de 2FA iniciada: user_id=%s", current_user.id)
    return _render(request, current_user)


@router.post("/ui/seguridad/2fa/confirmar", response_class=HTMLResponse)
def totp_confirm(
    request: Request,
    code: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    if not current_user.totp_secret or current_user.totp_confirmed_at:
        return _render(request, current_user, error="No hay una configuración de 2FA pendiente.")
    if not verify_totp(current_user.totp_secret, code):
        return _render(request, current_user, error="Código incorrecto. Escanea el QR y vuelve a intentar.")
    current_user.totp_confirmed_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("2FA activado: user_id=%s", current_user.id)
    return _render(request, current_user, success="2FA activado. Desde ahora el login pedirá tu código.")


@router.post("/ui/seguridad/2fa/cancelar", response_class=HTMLResponse)
def totp_cancel(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Cancela una configuración pendiente (QR generado pero nunca confirmado)."""
    if current_user.totp_secret and not current_user.totp_confirmed_at:
        current_user.totp_secret = None
        db.commit()
    return _render(request, current_user)


@router.post("/ui/seguridad/2fa/desactivar", response_class=HTMLResponse)
def totp_disable(
    request: Request,
    code: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    if not current_user.totp_enabled:
        return _render(request, current_user, error="El 2FA no está activo.")
    if not verify_totp(current_user.totp_secret, code):
        return _render(request, current_user, error="Código incorrecto: no se desactivó el 2FA.")
    current_user.totp_secret = None
    current_user.totp_confirmed_at = None
    db.commit()
    logger.info("2FA desactivado: user_id=%s", current_user.id)
    return _render(request, current_user, success="2FA desactivado.")


# --- Cambio de contraseña de la cuenta ---

@router.get("/ui/seguridad/password/form", response_class=HTMLResponse)
def password_form(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    return templates.TemplateResponse(
        "security/partials/password_form.html",
        {"request": request, "current_user": current_user},
    )


@router.get("/ui/seguridad/password/cancel", response_class=HTMLResponse)
def password_cancel(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Vuelve a mostrar la fila de contraseña en reposo (botón 'Cambiar')."""
    return templates.TemplateResponse(
        "security/partials/password_row.html",
        {"request": request, "current_user": current_user},
    )


@router.post("/ui/seguridad/password/save", response_class=HTMLResponse)
def password_save(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    def fail(message: str) -> HTMLResponse:
        return templates.TemplateResponse(
            "security/partials/password_form.html",
            {"request": request, "current_user": current_user, "error": message},
        )

    if not verify_password(current_password, current_user.hashed_password):
        return fail("La contraseña actual no es correcta.")
    if len(new_password) < MIN_PASSWORD_LEN:
        return fail(f"La nueva contraseña debe tener al menos {MIN_PASSWORD_LEN} caracteres.")
    if new_password != confirm_password:
        return fail("La nueva contraseña y su confirmación no coinciden.")
    if new_password == current_password:
        return fail("La nueva contraseña debe ser distinta de la actual.")

    current_user.hashed_password = hash_password(new_password)
    db.commit()
    logger.info("Contraseña de cuenta cambiada: user_id=%s", current_user.id)
    return templates.TemplateResponse(
        "security/partials/password_row.html",
        {"request": request, "current_user": current_user, "success": "Contraseña actualizada."},
    )
