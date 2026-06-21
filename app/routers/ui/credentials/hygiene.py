"""Informe de higiene de contraseñas + chequeo HIBP."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.jinja import templates
from app.models import Credential, User

router = APIRouter()


@router.get("/credentials/higiene", response_class=HTMLResponse)
def hygiene_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Informe de higiene: reutilizadas, débiles, sin URL y sin contraseña."""
    from app.services.password_hygiene import analyze

    credentials = (
        db.query(Credential)
        .filter(Credential.user_id == current_user.id, Credential.deleted_at.is_(None))
        .order_by(Credential.label)
        .all()
    )
    report = analyze(credentials)
    return templates.TemplateResponse(
        "credentials/hygiene.html",
        {"request": request, "report": report, "current_user": current_user},
    )


@router.post("/ui/credentials/higiene/filtraciones", response_class=HTMLResponse)
def hygiene_breach_check(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Comprueba contra Have I Been Pwned (k-anonymity). Opt-in: solo al pulsar."""
    from app.services.pwned import check_passwords

    creds = (
        db.query(Credential)
        .filter(
            Credential.user_id == current_user.id,
            Credential.deleted_at.is_(None),
            Credential.password.isnot(None),
        )
        .order_by(Credential.label)
        .all()
    )
    result = check_passwords([(c.label, c.password) for c in creds])
    return templates.TemplateResponse(
        "credentials/partials/breach_result.html",
        {"request": request, "result": result, "current_user": current_user},
    )
