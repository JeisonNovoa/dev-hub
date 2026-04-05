# Dev Hub

Hub personal de desarrollo — reemplaza Notion + Bitwarden con una sola app web propia, sin fricción, sin pago, sin auth.

## El problema que resuelve

Cuando trabajas en múltiples proyectos con IA (Vibe Coding), es fácil perder contexto: ¿cómo se inicia este proyecto? ¿qué variables de entorno usa? ¿con qué cuenta me registré en Cartesia? ¿cuál era el link al dashboard? Este hub centraliza todo eso en un solo lugar accesible en segundos.

## Qué tiene implementado

### Proyectos
- Dashboard con cards, búsqueda en tiempo real y filtro por status (activo / pausado / archivado)
- Vista de detalle por proyecto con todas sus secciones en una sola página
- Comandos de inicio, migración, build — con orden numérico y tipo, copy-to-clipboard
- Variables de entorno — con toggle show/hide y copy-to-clipboard
- Links rápidos categorizados (dashboard, repo, docs, staging, prod)
- Notas en markdown renderizado
- Todo editable inline (HTMX — sin recargar página)

### Credenciales
- Tabla de credenciales con búsqueda y filtro por categoría (personal / trabajo / proyecto)
- Toggle show/hide contraseña por fila
- Copy-to-clipboard en usuario y contraseña
- URL de acceso directo por credencial

### Búsqueda global
- Busca simultáneamente en proyectos, credenciales, servicios y links

### API REST
Todos los endpoints en `/api/...` — diseñados para que Claude Code los llame directamente y agregue/actualice info de proyectos sin que el usuario tenga que hacerlo manualmente.

```
POST   /api/projects
PATCH  /api/projects/{slug}
POST   /api/projects/{slug}/env-vars
POST   /api/projects/{slug}/commands
POST   /api/projects/{slug}/links
POST   /api/credentials
POST   /api/services
```

Documentación interactiva disponible en `/docs` (Swagger UI).

## Stack técnico

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.12 + FastAPI |
| ORM + migraciones | SQLAlchemy 2.x + Alembic |
| Base de datos | SQLite local → PostgreSQL en producción (solo cambiar `DATABASE_URL`) |
| Frontend | Jinja2 + HTMX 2.x + Alpine.js 3.x |
| Estilos | Tailwind CSS (CDN, siempre dark mode) |
| Tests | pytest + httpx (15 tests, cobertura de API completa) |
| Deploy | Render (free tier + persistent disk 1GB para SQLite) |

## Cómo correrlo localmente

```bash
# 1. Instalar dependencias (solo la primera vez)
cd dev-hub
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # Mac/Linux

# 2. Crear la base de datos
.venv/Scripts/alembic upgrade head

# 3. Arrancar
.venv/Scripts/python -m uvicorn app.main:app --reload

# App disponible en http://localhost:8000
# API docs en      http://localhost:8000/docs
```

## Variables de entorno

Copia `.env.example` a `.env`:

```bash
# Local (default)
DATABASE_URL=sqlite:///./dev_hub.db

# Producción (Neon o Supabase — gratis)
# DATABASE_URL=postgresql+psycopg2://user:pass@host/dbname

APP_NAME=Dev Hub
DEBUG=true
```

## Correr tests

```bash
.venv/Scripts/pytest tests/ -v
```

## Migraciones

```bash
# Crear nueva migración después de cambiar modelos
.venv/Scripts/alembic revision --autogenerate -m "descripcion del cambio"

# Aplicar migraciones pendientes
.venv/Scripts/alembic upgrade head
```

## Deploy en Render

1. Subir el repo a GitHub
2. Conectar en [render.com](https://render.com) como Web Service
3. En el dashboard de Render, setear la variable de entorno:
   - `DATABASE_URL=sqlite:////data/dev_hub.db` (usa el persistent disk incluido en `render.yaml`)
   - O conectar una DB PostgreSQL gratuita de [Neon](https://neon.tech) o [Supabase](https://supabase.com) y poner su URL
4. El `render.yaml` ya tiene todo configurado (build command, start command, persistent disk de 1GB)

## Estructura del proyecto

```
dev-hub/
├── app/
│   ├── main.py              # App factory + registro de routers
│   ├── config.py            # Settings (DATABASE_URL, etc.)
│   ├── database.py          # Engine SQLAlchemy + get_db dependency
│   ├── models/              # SQLAlchemy models
│   │   ├── project.py       # Project, EnvVariable, Command, QuickLink
│   │   ├── service.py       # Service (herramientas externas por proyecto)
│   │   └── credential.py    # Credential (contraseñas y accesos)
│   ├── schemas/             # Pydantic schemas (Create / Update / Response)
│   ├── routers/
│   │   ├── api/             # Endpoints JSON — para Claude Code y uso externo
│   │   └── ui/              # Endpoints HTML — Jinja2 templates
│   └── templates/           # HTML con HTMX y Alpine.js
├── alembic/                 # Migraciones de base de datos
├── tests/                   # pytest — 15 tests
├── .env.example
├── render.yaml              # Configuración de deploy en Render
└── requirements.txt
```

## Integración con Claude Code

Cuando Claude Code está trabajando en un proyecto tuyo, puede registrar/actualizar la info en el hub directamente:

```bash
# Ejemplo: agregar un proyecto nuevo
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "Mi App", "tech_stack": ["FastAPI", "React"], "description": "..."}'

# Agregar una variable de entorno
curl -X POST http://localhost:8000/api/projects/mi-app/env-vars \
  -H "Content-Type: application/json" \
  -d '{"key": "DATABASE_URL", "value": "sqlite:///./dev.db"}'
```

No requiere MCP ni nada especial — es HTTP puro que Claude puede llamar directamente.

## Pendiente / ideas futuras

- [ ] Edición inline del nombre y descripción del proyecto (actualmente solo via API)
- [ ] Sección de servicios con UI (actualmente solo via API)
- [ ] Vinculación visual entre credenciales y proyectos
- [ ] Exportar / importar desde Bitwarden (CSV)
- [ ] Modo de edición de notas con preview markdown en vivo
