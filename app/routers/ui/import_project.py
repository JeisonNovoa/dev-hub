"""Importación de proyectos desde la UI: prompt copiable + pegar/subir JSON."""

import json
import logging
from html import escape

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.jinja import templates
from app.models import User
from app.schemas.import_project import parse_project_import
from app.services.import_project import import_project

router = APIRouter()
logger = logging.getLogger(__name__)

# Más que suficiente para el JSON de un proyecto; evita payloads abusivos.
MAX_IMPORT_BYTES = 512 * 1024


def render_import_prompt() -> str:
    return templates.get_template("import/prompt.txt").render()


def _strip_code_fence(text: str) -> str:
    """Tolera que la IA envuelva el JSON en un bloque ```json ... ``` pese a las instrucciones."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _error_fragment(message: str) -> HTMLResponse:
    # 200 para que HTMX haga swap del mensaje dentro del modal.
    return HTMLResponse(f'<p class="text-red-400 text-sm font-mono">{escape(message)}</p>')


@router.get("/ui/import/prompt", response_class=PlainTextResponse)
def import_prompt(current_user: User = Depends(get_current_user)) -> PlainTextResponse:
    return PlainTextResponse(render_import_prompt())


@router.post("/ui/import", response_model=None)
async def import_submit(
    request: Request,
    json_text: str = Form(""),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse | RedirectResponse:
    if file is not None and file.filename:
        raw_bytes = await file.read()
        if len(raw_bytes) > MAX_IMPORT_BYTES:
            return _error_fragment("El archivo es demasiado grande (máximo 512 KB).")
        try:
            content = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            return _error_fragment("El archivo no es texto UTF-8 válido.")
    else:
        if len(json_text.encode("utf-8", errors="ignore")) > MAX_IMPORT_BYTES:
            return _error_fragment("El JSON es demasiado grande (máximo 512 KB).")
        content = json_text

    content = _strip_code_fence(content)
    if not content:
        return _error_fragment("Pega el JSON generado por la IA o sube el archivo .json.")

    try:
        raw = json.loads(content)
    except json.JSONDecodeError as exc:
        return _error_fragment(f"JSON inválido: {exc.msg} (línea {exc.lineno}).")

    try:
        data, skipped = parse_project_import(raw)
    except ValueError as exc:
        return _error_fragment(str(exc))

    project, counts = import_project(data, current_user.id, db)
    if skipped:
        logger.warning(
            "Importación de '%s' con %d item(s) descartado(s) (user=%d): %s",
            project.slug, len(skipped), current_user.id, "; ".join(skipped[:5]),
        )

    target = f"/projects/{project.slug}"
    if request.headers.get("HX-Request"):
        return HTMLResponse("", headers={"HX-Redirect": target})
    return RedirectResponse(url=target, status_code=303)
