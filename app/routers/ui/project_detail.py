from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from slugify import slugify
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_project_or_404
from app.jinja import templates
from app.models import Command, Credential, EnvVariable, QuickLink, Repo, Service

router = APIRouter()


@router.get("/projects/{slug}", response_class=HTMLResponse)
def project_detail(slug: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    # Solo comandos globales (sin repo) agrupados por tipo
    commands_by_type: dict[str, list[Command]] = {}
    for cmd in project.commands:
        if cmd.repo_id is None:
            commands_by_type.setdefault(cmd.type, []).append(cmd)
    return templates.TemplateResponse(
        "project/detail.html",
        {"request": request, "project": project, "commands_by_type": commands_by_type},
    )


# ---- Formularios de creación (new) ----

@router.get("/ui/projects/{slug}/env-vars/new", response_class=HTMLResponse)
def env_var_new_form(slug: str, request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "project/partials/env_var_new.html",
        {"request": request, "slug": slug},
    )


@router.post("/ui/projects/{slug}/env-vars/new", response_class=HTMLResponse)
def env_var_new_submit(
    slug: str,
    request: Request,
    key: str = Form(...),
    value: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    env_var = EnvVariable(
        project_id=project.id,
        key=key,
        value=value or None,
        description=description or None,
    )
    db.add(env_var)
    db.commit()
    db.refresh(env_var)
    return templates.TemplateResponse(
        "project/partials/env_var_row.html",
        {"request": request, "env_var": env_var, "project": project},
    )


@router.get("/ui/projects/{slug}/env-vars/cancel-new", response_class=HTMLResponse)
def env_var_cancel_new(slug: str) -> HTMLResponse:
    return HTMLResponse("")


@router.get("/ui/projects/{slug}/commands/new", response_class=HTMLResponse)
def command_new_form(slug: str, request: Request, type: str = "start") -> HTMLResponse:
    return templates.TemplateResponse(
        "project/partials/command_new.html",
        {"request": request, "slug": slug, "type": type},
    )


@router.post("/ui/projects/{slug}/commands/new", response_class=HTMLResponse)
def command_new_submit(
    slug: str,
    request: Request,
    label: str = Form(...),
    command: str = Form(...),
    order: int = Form(0),
    type: str = Form("start"),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    cmd = Command(project_id=project.id, label=label, command=command, order=order, type=type)
    db.add(cmd)
    db.commit()
    db.refresh(cmd)
    return templates.TemplateResponse(
        "project/partials/command_row.html",
        {"request": request, "cmd": cmd, "project": project},
    )


@router.get("/ui/projects/{slug}/links/new", response_class=HTMLResponse)
def link_new_form(slug: str, request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "project/partials/link_new.html",
        {"request": request, "slug": slug},
    )


@router.post("/ui/projects/{slug}/links/new", response_class=HTMLResponse)
def link_new_submit(
    slug: str,
    request: Request,
    label: str = Form(...),
    url: str = Form(...),
    category: str = Form("other"),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    link = QuickLink(project_id=project.id, label=label, url=url, category=category)
    db.add(link)
    db.commit()
    db.refresh(link)
    return templates.TemplateResponse(
        "project/partials/link_row.html",
        {"request": request, "link": link, "project": project},
    )


# ---- Formularios de edición (edit) ----

@router.get("/ui/projects/{slug}/env-vars/{env_id}/edit", response_class=HTMLResponse)
def env_var_edit_form(slug: str, env_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    env_var = db.query(EnvVariable).filter(EnvVariable.id == env_id, EnvVariable.project_id == project.id).first()
    if not env_var:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/env_var_edit.html",
        {"request": request, "env_var": env_var, "project": project},
    )


@router.get("/ui/projects/{slug}/env-vars/{env_id}/view", response_class=HTMLResponse)
def env_var_view(slug: str, env_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    env_var = db.query(EnvVariable).filter(EnvVariable.id == env_id, EnvVariable.project_id == project.id).first()
    if not env_var:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/env_var_row.html",
        {"request": request, "env_var": env_var, "project": project},
    )


@router.get("/ui/projects/{slug}/commands/{cmd_id}/edit", response_class=HTMLResponse)
def command_edit_form(slug: str, cmd_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    cmd = db.query(Command).filter(Command.id == cmd_id, Command.project_id == project.id).first()
    if not cmd:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/command_edit.html",
        {"request": request, "cmd": cmd, "project": project},
    )


@router.get("/ui/projects/{slug}/commands/{cmd_id}/view", response_class=HTMLResponse)
def command_view(slug: str, cmd_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    cmd = db.query(Command).filter(Command.id == cmd_id, Command.project_id == project.id).first()
    if not cmd:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/command_row.html",
        {"request": request, "cmd": cmd, "project": project},
    )


@router.get("/ui/projects/{slug}/links/{link_id}/edit", response_class=HTMLResponse)
def link_edit_form(slug: str, link_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    link = db.query(QuickLink).filter(QuickLink.id == link_id, QuickLink.project_id == project.id).first()
    if not link:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/link_edit.html",
        {"request": request, "link": link, "project": project},
    )


@router.get("/ui/projects/{slug}/links/{link_id}/view", response_class=HTMLResponse)
def link_view(slug: str, link_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    link = db.query(QuickLink).filter(QuickLink.id == link_id, QuickLink.project_id == project.id).first()
    if not link:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/link_row.html",
        {"request": request, "link": link, "project": project},
    )


# ---- Servicios ----

@router.get("/ui/projects/{slug}/services/cancel-new", response_class=HTMLResponse)
def service_cancel_new(slug: str) -> HTMLResponse:
    return HTMLResponse("")


@router.get("/ui/projects/{slug}/services/new", response_class=HTMLResponse)
def service_new_form(slug: str, request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "project/partials/service_new.html",
        {"request": request, "slug": slug},
    )


@router.post("/ui/projects/{slug}/services/new", response_class=HTMLResponse)
def service_new_submit(
    slug: str,
    request: Request,
    name: str = Form(...),
    category: str = Form("other"),
    url: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    service = Service(
        project_id=project.id,
        name=name,
        category=category,
        url=url or None,
        notes=notes or None,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return templates.TemplateResponse(
        "project/partials/service_row.html",
        {"request": request, "service": service, "project": project},
    )


@router.get("/ui/projects/{slug}/services/{service_id}/edit", response_class=HTMLResponse)
def service_edit_form(slug: str, service_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    service = db.query(Service).filter(Service.id == service_id, Service.project_id == project.id).first()
    if not service:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/service_edit.html",
        {"request": request, "service": service, "project": project},
    )


@router.get("/ui/projects/{slug}/services/{service_id}/view", response_class=HTMLResponse)
def service_view(slug: str, service_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    service = db.query(Service).filter(Service.id == service_id, Service.project_id == project.id).first()
    if not service:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/service_row.html",
        {"request": request, "service": service, "project": project},
    )


# ---- Header del proyecto ----

@router.get("/ui/projects/{slug}/header/view", response_class=HTMLResponse)
def project_header_view(slug: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    return templates.TemplateResponse(
        "project/partials/project_header.html",
        {"request": request, "project": project},
    )


@router.get("/ui/projects/{slug}/header/edit", response_class=HTMLResponse)
def project_header_edit(slug: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    return templates.TemplateResponse(
        "project/partials/project_header_edit.html",
        {"request": request, "project": project},
    )


@router.post("/ui/projects/{slug}/header/save", response_class=HTMLResponse)
def project_header_save(
    slug: str,
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    tech_stack_raw: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    project.name = name
    project.description = description or None
    project.tech_stack = [t.strip() for t in tech_stack_raw.split(",") if t.strip()]
    db.commit()
    db.refresh(project)
    return templates.TemplateResponse(
        "project/partials/project_header.html",
        {"request": request, "project": project},
    )


# ---- Notas ----

@router.get("/ui/projects/{slug}/notes/view", response_class=HTMLResponse)
def notes_view(slug: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    return templates.TemplateResponse(
        "project/partials/notes_view.html",
        {"request": request, "project": project},
    )


@router.get("/ui/projects/{slug}/notes/edit", response_class=HTMLResponse)
def notes_edit(slug: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    return templates.TemplateResponse(
        "project/partials/notes_edit.html",
        {"request": request, "project": project},
    )


@router.post("/ui/projects/{slug}/notes/save", response_class=HTMLResponse)
def notes_save(
    slug: str,
    request: Request,
    notes: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    project.notes = notes or None
    db.commit()
    db.refresh(project)
    return templates.TemplateResponse(
        "project/partials/notes_view.html",
        {"request": request, "project": project},
    )


# ---- Repos ----

@router.get("/ui/projects/{slug}/repos/new", response_class=HTMLResponse)
def repo_new_form(slug: str, request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "project/partials/repo_new.html",
        {"request": request, "slug": slug},
    )


@router.post("/ui/projects/{slug}/repos/new", response_class=HTMLResponse)
def repo_new_submit(
    slug: str,
    request: Request,
    name: str = Form(...),
    local_path: str = Form(""),
    github_url: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    repo_slug = slugify(name)
    repo = Repo(
        project_id=project.id,
        name=name,
        slug=repo_slug,
        local_path=local_path or None,
        github_url=github_url or None,
        description=description or None,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return templates.TemplateResponse(
        "project/partials/repo_card.html",
        {"request": request, "repo": repo, "project": project},
    )


@router.get("/ui/projects/{slug}/repos/{repo_id}/edit", response_class=HTMLResponse)
def repo_edit_form(slug: str, repo_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    repo = db.query(Repo).filter(Repo.id == repo_id, Repo.project_id == project.id).first()
    if not repo:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/repo_edit.html",
        {"request": request, "repo": repo, "project": project},
    )


@router.get("/ui/projects/{slug}/repos/{repo_id}/view", response_class=HTMLResponse)
def repo_view(slug: str, repo_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    repo = db.query(Repo).filter(Repo.id == repo_id, Repo.project_id == project.id).first()
    if not repo:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/repo_card.html",
        {"request": request, "repo": repo, "project": project},
    )


# ---- Comandos de repo (UI) ----

@router.get("/ui/projects/{slug}/repos/{repo_id}/commands/new", response_class=HTMLResponse)
def repo_command_new_form(slug: str, repo_id: int, request: Request, type: str = "start") -> HTMLResponse:
    return templates.TemplateResponse(
        "project/partials/repo_command_new.html",
        {"request": request, "slug": slug, "repo_id": repo_id, "type": type},
    )


@router.post("/ui/projects/{slug}/repos/{repo_id}/commands/new", response_class=HTMLResponse)
def repo_command_new_submit(
    slug: str,
    repo_id: int,
    request: Request,
    label: str = Form(...),
    command: str = Form(...),
    order: int = Form(0),
    type: str = Form("start"),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    repo = db.query(Repo).filter(Repo.id == repo_id, Repo.project_id == project.id).first()
    if not repo:
        raise HTTPException(status_code=404)
    cmd = Command(project_id=project.id, repo_id=repo.id, label=label, command=command, order=order, type=type)
    db.add(cmd)
    db.commit()
    db.refresh(cmd)
    return templates.TemplateResponse(
        "project/partials/command_row.html",
        {"request": request, "cmd": cmd, "project": project},
    )


# ---- Credenciales del proyecto ----

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
) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    cred = Credential(
        project_id=project.id,
        label=label,
        username=username or None,
        password=password or None,
        url=url or None,
        login_via=login_via,
        category="project",
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return templates.TemplateResponse(
        "project/partials/credential_item.html",
        {"request": request, "cred": cred, "project": project},
    )


@router.get("/ui/projects/{slug}/credentials/{cred_id}/edit", response_class=HTMLResponse)
def credential_edit_form(slug: str, cred_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = get_project_or_404(slug, db)
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
) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    cred = db.query(Credential).filter(Credential.id == cred_id, Credential.project_id == project.id).first()
    if not cred:
        raise HTTPException(status_code=404)
    cred.label = label
    cred.username = username or None
    cred.password = password or None
    cred.url = url or None
    cred.login_via = login_via
    cred.notes = notes or None
    db.commit()
    db.refresh(cred)
    return templates.TemplateResponse(
        "project/partials/credential_item.html",
        {"request": request, "cred": cred, "project": project},
    )


@router.get("/ui/projects/{slug}/credentials/{cred_id}/view", response_class=HTMLResponse)
def credential_view(slug: str, cred_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    cred = db.query(Credential).filter(Credential.id == cred_id, Credential.project_id == project.id).first()
    if not cred:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "project/partials/credential_item.html",
        {"request": request, "cred": cred, "project": project},
    )


# ---- Env vars de repo (UI) ----

@router.get("/ui/projects/{slug}/repos/{repo_id}/env-vars/new", response_class=HTMLResponse)
def repo_env_var_new_form(slug: str, repo_id: int, request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "project/partials/repo_env_var_new.html",
        {"request": request, "slug": slug, "repo_id": repo_id},
    )


@router.post("/ui/projects/{slug}/repos/{repo_id}/env-vars/new", response_class=HTMLResponse)
def repo_env_var_new_submit(
    slug: str,
    repo_id: int,
    request: Request,
    key: str = Form(...),
    value: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    project = get_project_or_404(slug, db)
    repo = db.query(Repo).filter(Repo.id == repo_id, Repo.project_id == project.id).first()
    if not repo:
        raise HTTPException(status_code=404)
    env_var = EnvVariable(
        project_id=project.id,
        repo_id=repo.id,
        key=key,
        value=value or None,
        description=description or None,
    )
    db.add(env_var)
    db.commit()
    db.refresh(env_var)
    return templates.TemplateResponse(
        "project/partials/env_var_row.html",
        {"request": request, "env_var": env_var, "project": project},
    )
