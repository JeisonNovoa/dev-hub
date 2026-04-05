"""
Migra todos los datos del SQLite local a producción (Supabase via API REST).

Las contraseñas se leen descifradas desde el SQLite local y se envían en
texto plano a la API de producción, que las cifra con la clave de producción.

Uso:
    python scripts/migrate_to_prod.py https://tu-app.onrender.com

Requisitos:
    - El .env local debe tener DATABASE_URL apuntando al SQLite local
    - La app de producción debe estar corriendo
"""

import sys
from pathlib import Path

import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.models import Credential, Project, Service


def post(prod_url: str, path: str, data: dict) -> dict:
    r = requests.post(f"{prod_url}{path}", json=data, timeout=30)
    if r.status_code not in (200, 201):
        print(f"  ! ERROR {r.status_code} en {path}: {r.text[:200]}")
        return {}
    return r.json()


def migrate(prod_url: str) -> None:
    prod_url = prod_url.rstrip("/")
    print(f"\nConectando a DB local: {settings.database_url}")
    print(f"Destino: {prod_url}\n")

    engine = create_engine(settings.database_url)
    db = sessionmaker(bind=engine)()

    project_id_map: dict[int, int] = {}   # local_id → prod_id
    service_id_map: dict[int, int] = {}   # local_id → prod_id

    # ─── 1. Proyectos ────────────────────────────────────────────────────────
    projects = db.query(Project).order_by(Project.id).all()
    print(f"-- Proyectos ({len(projects)}) --------------------------")

    for p in projects:
        print(f"  > {p.name} ({p.slug})")

        result = post(prod_url, "/api/projects", {
            "name": p.name,
            "slug": p.slug,
            "description": p.description,
            "tech_stack": p.tech_stack or [],
            "status": p.status,
            "notes": p.notes,
        })
        if not result:
            continue

        prod_id = result["id"]
        project_id_map[p.id] = prod_id

        # Env vars
        for ev in p.env_vars:
            post(prod_url, f"/api/projects/{p.slug}/env-vars", {
                "key": ev.key,
                "value": ev.value,
                "description": ev.description,
            })

        # Commands (solo globales — los de repo se crean con el repo)
        for cmd in p.commands:
            if cmd.repo_id is None:
                post(prod_url, f"/api/projects/{p.slug}/commands", {
                    "label": cmd.label,
                    "command": cmd.command,
                    "order": cmd.order,
                    "type": cmd.type,
                })

        # Links
        for link in p.links:
            post(prod_url, f"/api/projects/{p.slug}/links", {
                "label": link.label,
                "url": link.url,
                "category": link.category,
            })

        # Repos (con sus propios commands y env vars)
        for repo in p.repos:
            repo_result = post(prod_url, f"/api/projects/{p.slug}/repos", {
                "name": repo.name,
                "slug": repo.slug,
                "local_path": repo.local_path,
                "github_url": repo.github_url,
                "description": repo.description,
            })
            if not repo_result:
                continue

            repo_slug = repo_result["slug"]

            for cmd in repo.commands:
                post(prod_url, f"/api/projects/{p.slug}/repos/{repo_slug}/commands", {
                    "label": cmd.label,
                    "command": cmd.command,
                    "order": cmd.order,
                    "type": cmd.type,
                })

            for ev in repo.env_vars:
                post(prod_url, f"/api/projects/{p.slug}/repos/{repo_slug}/env-vars", {
                    "key": ev.key,
                    "value": ev.value,
                    "description": ev.description,
                })

    # ─── 2. Servicios ────────────────────────────────────────────────────────
    services = db.query(Service).order_by(Service.id).all()
    print(f"\n-- Servicios ({len(services)}) --------------------------")

    for s in services:
        print(f"  > {s.name}")
        result = post(prod_url, "/api/services", {
            "name": s.name,
            "url": s.url,
            "category": s.category,
            "notes": s.notes,
            "project_id": project_id_map.get(s.project_id) if s.project_id else None,
        })
        if result:
            service_id_map[s.id] = result["id"]

    # ─── 3. Credenciales ─────────────────────────────────────────────────────
    credentials = db.query(Credential).order_by(Credential.id).all()
    print(f"\n-- Credenciales ({len(credentials)}) --------------------")

    for c in credentials:
        print(f"  > {c.label}")
        post(prod_url, "/api/credentials", {
            "label": c.label,
            "username": c.username,
            "password": c.password,   # TypeDecorator ya lo descifró
            "url": c.url,
            "category": c.category,
            "login_via": c.login_via,
            "notes": c.notes,
            "project_id": project_id_map.get(c.project_id) if c.project_id else None,
            "service_id": service_id_map.get(c.service_id) if c.service_id else None,
        })

    db.close()
    print(f"\nMigracion completa.")
    print(f"  Proyectos migrados : {len(project_id_map)}")
    print(f"  Servicios migrados : {len(service_id_map)}")
    print(f"  Credenciales       : {len(credentials)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/migrate_to_prod.py https://tu-app.onrender.com")
        sys.exit(1)

    migrate(sys.argv[1])
