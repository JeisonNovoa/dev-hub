# Dev Hub

Hub personal de desarrollo — centraliza proyectos, credenciales y servicios en una sola app web propia, con cuentas privadas por usuario.

## El problema que resuelve

Cuando trabajas en múltiples proyectos con IA (Vibe Coding), es fácil perder contexto: ¿cómo se inicia este proyecto? ¿qué variables de entorno usa? ¿con qué cuenta me registré en Cartesia? ¿cuál era el link al dashboard? Este hub centraliza todo eso en un solo lugar accesible desde cualquier dispositivo.

## Qué tiene

### Autenticación
- Registro y login por email/contraseña
- Sesiones firmadas con cookie HttpOnly (itsdangerous)
- Contraseñas hasheadas con bcrypt
- Datos completamente aislados por usuario

### Proyectos
- Dashboard con cards, búsqueda en tiempo real y filtro por status (activo / pausado / archivado)
- Vista de detalle con todas las secciones en una sola página
- Comandos (inicio, build, test…) con orden numérico, tipo y copy-to-clipboard
- Variables de entorno con toggle show/hide y copy-to-clipboard
- Links rápidos categorizados (dashboard, repo, docs, staging, prod)
- Notas en markdown renderizado
- Repos vinculados, cada uno con sus propios comandos y env vars
- Servicios externos asociados al proyecto
- Credenciales inline por proyecto
- Todo editable inline (HTMX — sin recargar página)

### Credenciales
- Tabla global con búsqueda y filtro por categoría (personal / trabajo / proyecto)
- Contraseñas cifradas en reposo (Fernet AES-128)
- Toggle show/hide y copy-to-clipboard por fila
- URL de acceso directo

### API REST
Todos los endpoints en `/api/...` — diseñados para que Claude Code los llame directamente.

```
POST   /api/projects
PATCH  /api/projects/{slug}
POST   /api/projects/{slug}/env-vars
POST   /api/projects/{slug}/commands
POST   /api/projects/{slug}/links
POST   /api/projects/{slug}/repos
POST   /api/credentials
POST   /api/services
GET    /api/export
```

Documentación interactiva en `/docs` (Swagger UI).

## Stack técnico

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.12 + FastAPI |
| ORM + migraciones | SQLAlchemy 2.x + Alembic |
| Base de datos | SQLite local → PostgreSQL en producción (Supabase) |
| Frontend | Jinja2 + HTMX 2.x + Alpine.js 3.x |
| Estilos | Tailwind CSS compilado (dark mode) |
| Cifrado | Fernet (cryptography) para contraseñas + itsdangerous para sesiones |
| Tests | pytest — 125 tests |
| Deploy | Render + Supabase (ambos free tier) |

## Cómo correrlo localmente

```bash
# 1. Clonar e instalar dependencias
git clone https://github.com/tu-usuario/dev-hub.git
cd dev-hub
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt      # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # Mac/Linux

# 2. Compilar CSS
npm ci && npm run build:css

# 3. Configurar variables de entorno
cp .env.example .env   # editar con tus valores

# 4. Crear la base de datos
.venv\Scripts\python -m alembic upgrade head

# 5. Arrancar
.venv\Scripts\python -m uvicorn app.main:app --reload
# App en http://localhost:8000
```

## Variables de entorno

```bash
# Base de datos
DATABASE_URL=sqlite:///./dev_hub.db

# Nombre de la app
APP_NAME=Dev Hub

# Modo debug
DEBUG=true

# Clave para cifrar contraseñas (obligatoria)
# Genera con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=

# Clave para firmar sesiones (obligatoria, mínimo 32 chars)
# Genera con: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=
```

## Correr tests

```bash
.venv\Scripts\python -m pytest tests/ -v
```

## Migraciones

```bash
# Aplicar migraciones pendientes
.venv\Scripts\python -m alembic upgrade head

# Crear nueva migración tras cambiar modelos
.venv\Scripts\python -m alembic revision --autogenerate -m "descripcion"
```

## Deploy en Render + Supabase

1. Crear proyecto en [Supabase](https://supabase.com) y copiar la URL del **Session Pooler** (puerto 5432)
2. Subir el repo a GitHub y conectar en [render.com](https://render.com) como Web Service
3. En Render → Environment, configurar:
   - `DATABASE_URL` → URL de Supabase Session Pooler con `+psycopg2`
   - `ENCRYPTION_KEY` → genera una nueva con el comando de arriba
   - `SECRET_KEY` → genera una nueva con el comando de arriba
4. El `render.yaml` ya tiene el build command (`alembic upgrade head` incluido) y el start command

La primera migración crea un usuario admin seed:
- Email: `admin@devhub.local`
- Contraseña: `changeme`

Regístrate con tu cuenta real desde `/register` después del primer deploy.

## Estructura del proyecto

```
dev-hub/
├── app/
│   ├── main.py              # App factory + registro de routers
│   ├── auth.py              # Hash bcrypt + cookies firmadas (itsdangerous)
│   ├── config.py            # Settings (DATABASE_URL, ENCRYPTION_KEY, SECRET_KEY)
│   ├── crypto.py            # TypeDecorator Fernet para cifrar contraseñas en BD
│   ├── database.py          # Engine SQLAlchemy + get_db
│   ├── dependencies.py      # get_current_user, get_project_or_404
│   ├── models/
│   │   ├── user.py          # User (email, hashed_password, is_active)
│   │   ├── project.py       # Project, EnvVariable, Command, QuickLink
│   │   ├── repo.py          # Repo (con sus propios commands y env vars)
│   │   ├── service.py       # Service
│   │   └── credential.py    # Credential (password cifrada)
│   ├── schemas/             # Pydantic schemas (Create / Update / Response)
│   ├── routers/
│   │   ├── api/             # Endpoints JSON
│   │   └── ui/              # Endpoints HTML (Jinja2 + HTMX)
│   │       └── auth.py      # /login, /register, /logout
│   └── templates/
│       ├── auth/            # login.html, register.html
│       └── ...              # dashboard, project, credentials
├── alembic/                 # Migraciones
├── tests/                   # 125 tests (pytest)
├── scripts/
│   └── migrate_to_prod.py   # Migrar datos de SQLite local a producción
├── render.yaml
└── requirements.txt
```

## Integración con Claude Code

La API acepta peticiones directas sin autenticación adicional desde localhost. Claude puede registrar proyectos, env vars y comandos automáticamente mientras trabaja:

```bash
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "Mi App", "tech_stack": ["FastAPI"], "description": "..."}'

curl -X POST http://localhost:8000/api/projects/mi-app/env-vars \
  -H "Content-Type: application/json" \
  -d '{"key": "DATABASE_URL", "value": "sqlite:///./dev.db"}'
```
