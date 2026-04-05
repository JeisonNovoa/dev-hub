from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.jinja import templates
from app.models import Credential

router = APIRouter()


@router.get("/credentials", response_class=HTMLResponse)
def credentials_page(
    request: Request,
    q: str = "",
    category: str = "",
    db: Session = Depends(get_db),
) -> HTMLResponse:
    credentials = _query_credentials(q, category, db)
    # Si es HTMX, devolver solo las filas
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "credentials/partials/credential_rows.html",
            {"request": request, "credentials": credentials},
        )
    return templates.TemplateResponse(
        "credentials/index.html",
        {"request": request, "credentials": credentials, "q": q, "category_filter": category},
    )


@router.post("/ui/credentials/new", response_class=RedirectResponse, status_code=303)
def create_credential_form(
    label: str = Form(...),
    username: str = Form(""),
    password: str = Form(""),
    url: str = Form(""),
    category: str = Form("work"),
    login_via: str = Form("email"),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    cred = Credential(
        label=label,
        username=username or None,
        password=password or None,
        url=url or None,
        category=category,
        login_via=login_via,
    )
    db.add(cred)
    db.commit()
    return RedirectResponse(url="/credentials", status_code=303)


@router.get("/ui/credentials/{cred_id}/edit", response_class=HTMLResponse)
def credential_edit_form(cred_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    cred = db.query(Credential).filter(Credential.id == cred_id).first()
    if not cred:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "credentials/partials/credential_edit_row.html",
        {"request": request, "cred": cred},
    )


@router.get("/ui/credentials/{cred_id}/view", response_class=HTMLResponse)
def credential_view(cred_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    cred = db.query(Credential).filter(Credential.id == cred_id).first()
    if not cred:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "credentials/partials/credential_row.html",
        {"request": request, "cred": cred},
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
) -> HTMLResponse:
    cred = db.query(Credential).filter(Credential.id == cred_id).first()
    if not cred:
        raise HTTPException(status_code=404)
    cred.label = label
    cred.username = username or None
    cred.password = password or None
    cred.url = url or None
    cred.category = category
    cred.login_via = login_via
    cred.notes = notes or None
    cred.project_id = int(project_id) if project_id.strip() else None
    db.commit()
    db.refresh(cred)
    return templates.TemplateResponse(
        "credentials/partials/credential_row.html",
        {"request": request, "cred": cred},
    )


def _query_credentials(q: str, category: str, db: Session) -> list[Credential]:
    query = db.query(Credential)
    if category:
        query = query.filter(Credential.category == category)
    if q:
        like = f"%{q}%"
        query = query.filter(Credential.label.ilike(like) | Credential.username.ilike(like))
    return query.order_by(Credential.label).all()
