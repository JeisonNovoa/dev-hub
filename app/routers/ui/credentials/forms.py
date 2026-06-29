"""Acciones de tabla de credenciales: crear, editar, ver, guardar."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.jinja import templates
from app.models import Credential, User
from app.routers.ui.credentials._shared import (
    apply_credential_form,
    get_active_credential_or_404,
)

router = APIRouter()


@router.post("/ui/credentials/new", response_class=RedirectResponse, status_code=303)
def create_credential_form(
    label: str = Form(...),
    username: str = Form(""),
    password: str = Form(""),
    url: str = Form(""),
    category: str = Form("work"),
    login_via: str = Form("email"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RedirectResponse:
    cred = Credential(
        label=label,
        username=username or None,
        password=password or None,
        url=url or None,
        category=category,
        login_via=login_via,
        user_id=current_user.id,
    )
    db.add(cred)
    db.commit()
    return RedirectResponse(url="/credentials", status_code=303)


@router.get("/ui/credentials/{cred_id}/edit", response_class=HTMLResponse)
def credential_edit_form(
    cred_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    cred = get_active_credential_or_404(cred_id, current_user.id, db)
    return templates.TemplateResponse(
        "credentials/partials/credential_edit_row.html",
        {"request": request, "cred": cred, "current_user": current_user},
    )


@router.get("/ui/credentials/{cred_id}/view", response_class=HTMLResponse)
def credential_view(
    cred_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    cred = get_active_credential_or_404(cred_id, current_user.id, db)
    return templates.TemplateResponse(
        "credentials/partials/credential_row.html",
        {"request": request, "cred": cred, "current_user": current_user},
    )


@router.post("/ui/credentials/{cred_id}/save", response_class=HTMLResponse)
def credential_save(
    cred_id: int,
    request: Request,
    label: str = Form(...),
    username: str = Form(""),
    password: str = Form(""),
    url: str = Form(""),
    category: str = Form("work"),
    login_via: str = Form("email"),
    notes: str = Form(""),
    project_id: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    cred = get_active_credential_or_404(cred_id, current_user.id, db)
    apply_credential_form(cred, label, username, password, url, category, login_via, notes, project_id)
    db.commit()
    db.refresh(cred)
    return templates.TemplateResponse(
        "credentials/partials/credential_row.html",
        {"request": request, "cred": cred, "current_user": current_user},
    )
