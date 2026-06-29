"""Smoke test del servidor MCP contra una instancia real de Dev Hub.

Hace llamadas reales a la API con el DEVHUB_TOKEN configurado y confirma que
la conexión, el token y las tools funcionan. No modifica datos (solo lectura).

Uso:
    DEVHUB_TOKEN=dvh_... python smoke_test.py
    DEVHUB_TOKEN=dvh_... DEVHUB_BASE_URL=http://localhost:8000 python smoke_test.py
"""

import sys

from client import base_url, request

# Fuerza salida UTF-8 (la consola de Windows usa cp1252 y rompería con tildes).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    print(f"Base URL: {base_url()}")
    try:
        data = request("GET", "/api/projects")
        projects = data["items"] if isinstance(data, dict) else data
    except Exception as exc:  # noqa: BLE001 - smoke test, queremos el mensaje crudo
        print(f"FALLO al listar proyectos: {exc}")
        return 1

    print(f"OK list_projects -> {len(projects)} proyecto(s)")
    for p in projects[:5]:
        print(f"  - {p['name']} ({p['slug']}) [{p['status']}]")

    if projects:
        slug = projects[0]["slug"]
        try:
            ctx = request("GET", f"/api/context/{slug}")
            print(f"OK get_context('{slug}') -> {len(ctx)} chars de markdown")
        except Exception as exc:  # noqa: BLE001
            print(f"FALLO get_context: {exc}")
            return 1

    try:
        events = request("GET", "/api/context/recent")
        events = events["events"] if isinstance(events, dict) else events
        print(f"OK recent_activity -> {len(events)} evento(s)")
    except Exception as exc:  # noqa: BLE001
        print(f"FALLO recent_activity: {exc}")
        return 1

    print("\nSmoke test OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
