# Servidor MCP de Dev Hub

Expone Dev Hub como herramientas MCP para que Claude Code lea y escriba en tu
hub directamente, sin copiar JSON a mano.

## Qué puede hacer Claude con esto

| Tool | Qué hace |
|------|----------|
| `list_projects` | Lista tus proyectos (filtra por status o texto) |
| `get_context` | Trae el contexto completo de un proyecto en markdown |
| `search` | Busca across proyectos, credenciales y servicios |
| `recent_activity` | Muestra en qué estuviste trabajando últimamente |
| `register_project` | Registra un proyecto nuevo |
| `add_env_var` | Agrega una variable de entorno a un proyecto |
| `add_command` | Agrega un comando a un proyecto |

## Instalación

```bash
cd mcp
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # Mac/Linux
```

## Conseguir un token

El servidor se autentica con un **token de extensión** de Dev Hub:

1. Entra a la web → **Seguridad → Tokens de extensión → generar**, o
2. Pídelo por API:
   ```bash
   curl -X POST https://dev-hub-whry8q.fly.dev/api/extension/login \
     -H "Content-Type: application/json" \
     -d '{"email":"TU_EMAIL","password":"TU_PASSWORD","name":"claude-code-mcp"}'
   # → {"token":"dvh_...","email":"..."}
   ```

Guarda el `dvh_...`. Expira a los 90 días y es revocable desde la web.

## Configurar en Claude Code

Agrega esto a tu config de MCP (`~/.claude.json` o el `.mcp.json` del proyecto):

```json
{
  "mcpServers": {
    "dev-hub": {
      "command": "C:/ruta/al/repo/mcp/.venv/Scripts/python",
      "args": ["C:/ruta/al/repo/mcp/server.py"],
      "env": {
        "DEVHUB_TOKEN": "dvh_tu_token_aqui",
        "DEVHUB_BASE_URL": "https://dev-hub-whry8q.fly.dev"
      }
    }
  }
}
```

> En Mac/Linux usa `mcp/.venv/bin/python`. `DEVHUB_BASE_URL` es opcional
> (default: producción); apúntalo a `http://localhost:8000` para desarrollo.

Reinicia Claude Code. Deberías poder pedir cosas como:

- *"dame el contexto del proyecto dev-hub"*
- *"¿con qué cuenta me registré en Cartesia?"*
- *"registra este repo en mi dev-hub"*

## Probar el servidor manualmente

```bash
DEVHUB_TOKEN=dvh_... .venv/Scripts/python smoke_test.py
```

Hace una llamada real a la API y confirma que el token y la conexión funcionan.
```
