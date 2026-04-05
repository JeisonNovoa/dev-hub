import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.auth import (
    COOKIE_NAME,
    create_session_cookie,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.dependencies import get_current_user_optional
from app.jinja import templates
from app.models import User

router = APIRouter()
logger = logging.getLogger(__name__)

_COOKIE_MAX_AGE = 86400 * 30  # 30 días


def _set_session(response: Response, user_id: int, secure: bool) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_session_cookie(user_id),
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=secure,
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    current_user: User | None = Depends(get_current_user_optional),
) -> Response:
    if current_user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        "auth/login.html", {"request": request, "current_user": None, "error": None}
    )


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> Response:
    user = db.query(User).filter(User.email == email.lower().strip()).first()
    if not user or not user.is_active or not verify_password(password, user.hashed_password):
        logger.warning("Login fallido para email: %s", email)
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "current_user": None,
                "error": "Email o contraseña incorrectos",
            },
            status_code=401,
        )
    from app.config import settings
    redirect = RedirectResponse(url="/", status_code=303)
    _set_session(redirect, user.id, secure=not settings.debug)
    logger.info("Login exitoso: user_id=%s", user.id)
    return redirect


@router.get("/register", response_class=HTMLResponse)
def register_page(
    request: Request,
    current_user: User | None = Depends(get_current_user_optional),
) -> Response:
    if current_user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        "auth/register.html", {"request": request, "current_user": None, "error": None}
    )


@router.post("/register")
def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db),
) -> Response:
    email = email.lower().strip()

    if len(password) < 8:
        return templates.TemplateResponse(
            "auth/register.html",
            {
                "request": request,
                "current_user": None,
                "error": "La contraseña debe tener al menos 8 caracteres",
            },
            status_code=422,
        )
    if password != password_confirm:
        return templates.TemplateResponse(
            "auth/register.html",
            {
                "request": request,
                "current_user": None,
                "error": "Las contraseñas no coinciden",
            },
            status_code=422,
        )
    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse(
            "auth/register.html",
            {
                "request": request,
                "current_user": None,
                "error": "Ya existe una cuenta con ese email",
            },
            status_code=409,
        )

    user = User(email=email, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Nuevo usuario registrado: user_id=%s", user.id)

    from app.config import settings
    redirect = RedirectResponse(url="/", status_code=303)
    _set_session(redirect, user.id, secure=not settings.debug)
    return redirect


@router.post("/logout")
def logout(request: Request) -> Response:
    redirect = RedirectResponse(url="/login", status_code=303)
    redirect.delete_cookie(key=COOKIE_NAME)
    return redirect
