"""Credenciales inline del proyecto: alta y edición desde el detalle."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404
from app.jinja import templates
from app.models import Credential, User
from app.utils.activity import log_event

router = APIRouter()


@router.get("/ui/projects/{slug}/credentials/new", response_class=HTMLResponse)
def credential_new_form(slug: str, request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "project/partials/credential_new.html",
        {"request": request, "slug": slug},
    )


@router.post("/ui/projects/{slug}/credentials/new", response_class=HTMLResponse)
def credential_new_submit(
    slug: str,
    request: Request,
    label: str = Form(...),
    username: str = Form(""),
    password: str = Form(""),
    url: str = Form(""),
    login_via: str = Form("email"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    cred = Credential(
        project_id=project.id,
        user_id=current_user.id,
        label=label,
        username=username or None,
        password=password or None,
        url=url or None,
        login_via=login_via,
        category="project",
    )
    db.add(cred)
    log_event(db, project.id, "created", "credential", label)
    db.commit()
    db.refresh(cred)
    return templates.TemplateResponse(
        "project/partials/credential_item.html",
        {"request": request, "cred": cred, "project": project},
    )


@router.get("/ui/projects/{slug}/credentials/{cred_id}/edit", response_class=HTMLResponse)
def credential_edit_form(
    slug: str, cred_id: int, request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    cred = db.query(Credential).filter(Credential.id == cred_id, Credential.project_id == project.id).first()
    if not cred:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/credential_item_edit.html",
        {"request": request, "cred": cred, "project": project},
    )


@router.post("/ui/projects/{slug}/credentials/{cred_id}/save", response_class=HTMLResponse)
def credential_save(
    slug: str,
    cred_id: int,
    request: Request,
    label: str = Form(...),
    username: str = Form(""),
    password: str = Form(""),
    url: str = Form(""),
    login_via: str = Form("email"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    cred = db.query(Credential).filter(Credential.id == cred_id, Credential.project_id == project.id).first()
    if not cred:
        raise HTTPException(status_code=404)
    cred.label = label
    cred.username = username or None
    cred.password = password or None
    cred.url = url or None
    cred.login_via = login_via
    cred.notes = notes or None
    log_event(db, project.id, "updated", "credential", label)
    db.commit()
    db.refresh(cred)
    return templates.TemplateResponse(
        "project/partials/credential_item.html",
        {"request": request, "cred": cred, "project": project},
    )


@router.get("/ui/projects/{slug}/credentials/{cred_id}/view", response_class=HTMLResponse)
def credential_view(
    slug: str, cred_id: int, request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    project = get_project_or_404(slug, db, current_user)
    cred = db.query(Credential).filter(Credential.id == cred_id, Credential.project_id == project.id).first()
    if not cred:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/credential_item.html",
        {"request": request, "cred": cred, "project": project},
    )
