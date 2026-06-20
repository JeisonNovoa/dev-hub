"""Comprobación de contraseñas filtradas vía Have I Been Pwned (k-anonymity).

Privacidad: NUNCA se envía la contraseña ni su hash completo. Se calcula el
SHA-1, se manda solo el prefijo de 5 caracteres a la API, y el rango de posibles
coincidencias se compara localmente. Es el mismo modelo que usa Bitwarden.

Resiliencia: si no hay red o la API falla, se devuelve un resultado "no
concluyente" en vez de romper la página de higiene.
"""

import hashlib
import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

HIBP_RANGE_URL = "https://api.pwnedpasswords.com/range/"


@dataclass(frozen=True)
class PwnedResult:
    checked: bool                      # ¿se pudo consultar la API?
    breached: list[tuple[str, int]] = field(default_factory=list)  # (label, nº de veces visto)
    error: str | None = None


def _sha1_upper(password: str) -> str:
    return hashlib.sha1(password.encode("utf-8")).hexdigest().upper()


def _count_in_range(suffix: str, body: str) -> int:
    """Busca el sufijo del hash en la respuesta de HIBP (líneas 'SUFIJO:cuenta')."""
    for line in body.splitlines():
        parts = line.split(":")
        if len(parts) == 2 and parts[0].strip() == suffix:
            try:
                return int(parts[1].strip())
            except ValueError:
                return 0
    return 0


def check_passwords(
    items: list[tuple[str, str]],
    client: httpx.Client | None = None,
) -> PwnedResult:
    """Comprueba una lista de (label, password) contra HIBP.

    Agrupa por prefijo para minimizar llamadas (varias contraseñas con el mismo
    prefijo = una sola petición). Devuelve las filtradas con su recuento.
    """
    if not items:
        return PwnedResult(checked=True)

    # prefijo -> lista de (label, sufijo)
    by_prefix: dict[str, list[tuple[str, str]]] = {}
    for label, password in items:
        if not password:
            continue
        digest = _sha1_upper(password)
        by_prefix.setdefault(digest[:5], []).append((label, digest[5:]))

    breached: list[tuple[str, int]] = []
    owns_client = client is None
    client = client or httpx.Client(timeout=8.0, headers={"User-Agent": "dev-hub-hygiene"})
    try:
        for prefix, entries in by_prefix.items():
            resp = client.get(f"{HIBP_RANGE_URL}{prefix}")
            resp.raise_for_status()
            for label, suffix in entries:
                count = _count_in_range(suffix, resp.text)
                if count > 0:
                    breached.append((label, count))
    except Exception as exc:  # noqa: BLE001 — cualquier fallo externo es no-concluyente
        logger.warning("Comprobación HIBP no concluyente: %s", exc)
        return PwnedResult(checked=False, error="No se pudo consultar el servicio de filtraciones.")
    finally:
        if owns_client:
            client.close()

    breached.sort(key=lambda x: x[1], reverse=True)
    return PwnedResult(checked=True, breached=breached)
