"""Servidor MCP para Dev Hub.

Expone la API REST de Dev Hub como herramientas MCP para que Claude Code (u otro
cliente MCP) pueda leer y escribir en el hub sin copy-paste manual.

Autenticación: token de extensión Bearer (dvh_...). Se genera desde la web
(Extensión → conectar Claude Code / MCP) y se pasa por la variable de entorno
DEVHUB_TOKEN.

Config (variables de entorno):
    DEVHUB_TOKEN     token Bearer de extensión (obligatorio)
    DEVHUB_BASE_URL  URL de la app (default: https://dev-hub-whry8q.fly.dev)

Las tools viven en tools.py (CRUD completo por entidad); el cliente HTTP
compartido en client.py. Uso y configuración: ver README.md de esta carpeta.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

import tools

mcp = FastMCP("dev-hub")
tools.register(mcp)


if __name__ == "__main__":
    mcp.run()
