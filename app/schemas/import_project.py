"""Schema del JSON de importación de proyectos (generado por la IA del usuario).

El parseo es tolerante por-item: un comando/link/repo inválido se descarta y se
reporta en `skipped`, sin tumbar la importación completa. Solo `name` es obligatorio.
"""

from pydantic import BaseModel, Field, ValidationError, field_validator

VALID_COMMAND_TYPES = {"start", "migration", "build", "other"}
VALID_LINK_CATEGORIES = {"dashboard", "repo", "staging", "prod", "docs", "monitoring", "other"}
VALID_SERVICE_CATEGORIES = {"ai", "auth", "storage", "db", "deploy", "messaging", "monitoring", "other"}
VALID_STATUSES = {"active", "paused", "archived"}


def _clean_optional_url(v: str | None) -> str | None:
    """URL opcional: si no es http(s) válida se descarta el campo, no el item."""
    if not v or not isinstance(v, str):
        return None
    v = v.strip()
    return v if v.startswith(("http://", "https://")) else None


class ImportCommand(BaseModel):
    label: str = Field(min_length=1)
    command: str = Field(min_length=1)
    order: int = 0
    type: str = "other"

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: object) -> str:
        return v if v in VALID_COMMAND_TYPES else "other"


class ImportEnvVar(BaseModel):
    key: str = Field(min_length=1)
    value: str | None = None
    description: str | None = None


class ImportLink(BaseModel):
    label: str = Field(min_length=1)
    url: str
    category: str = "other"

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL inválida (debe empezar con http:// o https://)")
        return v

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v: object) -> str:
        return v if v in VALID_LINK_CATEGORIES else "other"


class ImportRepo(BaseModel):
    name: str = Field(min_length=1)
    local_path: str | None = None
    github_url: str | None = None
    description: str | None = None
    commands: list[ImportCommand] = []
    env_vars: list[ImportEnvVar] = []

    @field_validator("github_url", mode="before")
    @classmethod
    def clean_github_url(cls, v: str | None) -> str | None:
        return _clean_optional_url(v)


class ImportService(BaseModel):
    name: str = Field(min_length=1)
    url: str | None = None
    category: str = "other"
    notes: str | None = None

    @field_validator("url", mode="before")
    @classmethod
    def clean_url(cls, v: str | None) -> str | None:
        return _clean_optional_url(v)

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v: object) -> str:
        return v if v in VALID_SERVICE_CATEGORIES else "other"


class ProjectImport(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    tech_stack: list[str] = []
    status: str = "active"
    notes: str | None = None
    commands: list[ImportCommand] = []
    env_vars: list[ImportEnvVar] = []
    links: list[ImportLink] = []
    repos: list[ImportRepo] = []
    services: list[ImportService] = []

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v: object) -> str:
        return v if v in VALID_STATUSES else "active"

    @field_validator("tech_stack", mode="before")
    @classmethod
    def clean_tech_stack(cls, v: object) -> list[str]:
        if not isinstance(v, list):
            return []
        return [str(t).strip() for t in v if str(t).strip()]


def _first_error(exc: ValidationError) -> str:
    err = exc.errors()[0]
    field = ".".join(str(p) for p in err["loc"]) or "item"
    return f"{field}: {err['msg']}"


def _parse_items(
    raw_items: object, model: type[BaseModel], label: str, skipped: list[str]
) -> list[BaseModel]:
    if not isinstance(raw_items, list):
        if raw_items is not None:
            skipped.append(f"{label}: se esperaba una lista")
        return []
    parsed: list[BaseModel] = []
    for i, item in enumerate(raw_items):
        try:
            parsed.append(model.model_validate(item))
        except ValidationError as exc:
            skipped.append(f"{label}[{i}] descartado — {_first_error(exc)}")
    return parsed


def parse_project_import(raw: object) -> tuple[ProjectImport, list[str]]:
    """Parsea el JSON de importación descartando items inválidos individualmente.

    Devuelve el ProjectImport válido y la lista de items descartados (para mostrar
    al usuario). Levanta ValueError solo si el objeto raíz es inutilizable
    (no es un dict o no tiene `name`).
    """
    if not isinstance(raw, dict):
        raise ValueError("El JSON debe ser un objeto con los datos del proyecto")

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("El JSON debe incluir un campo 'name' con el nombre del proyecto")

    skipped: list[str] = []

    repos: list[ImportRepo] = []
    raw_repos = raw.get("repos")
    if isinstance(raw_repos, list):
        for i, raw_repo in enumerate(raw_repos):
            if not isinstance(raw_repo, dict):
                skipped.append(f"repos[{i}] descartado — no es un objeto")
                continue
            # Los hijos del repo también se filtran por-item antes de validar el repo.
            repo_data = {
                **raw_repo,
                "commands": _parse_items(raw_repo.get("commands"), ImportCommand, f"repos[{i}].commands", skipped),
                "env_vars": _parse_items(raw_repo.get("env_vars"), ImportEnvVar, f"repos[{i}].env_vars", skipped),
            }
            try:
                repos.append(ImportRepo.model_validate(repo_data))
            except ValidationError as exc:
                skipped.append(f"repos[{i}] descartado — {_first_error(exc)}")
    elif raw_repos is not None:
        skipped.append("repos: se esperaba una lista")

    data = ProjectImport(
        name=name.strip(),
        description=raw.get("description") if isinstance(raw.get("description"), str) else None,
        tech_stack=raw.get("tech_stack"),
        status=raw.get("status"),
        notes=raw.get("notes") if isinstance(raw.get("notes"), str) else None,
        commands=_parse_items(raw.get("commands"), ImportCommand, "commands", skipped),
        env_vars=_parse_items(raw.get("env_vars"), ImportEnvVar, "env_vars", skipped),
        links=_parse_items(raw.get("links"), ImportLink, "links", skipped),
        repos=repos,
        services=_parse_items(raw.get("services"), ImportService, "services", skipped),
    )
    return data, skipped
