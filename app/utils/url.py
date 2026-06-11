"""Utilidades de URL compartidas entre la UI (filtro Jinja) y la API de la extensión."""

from urllib.parse import urlparse


def extract_domain(url: str | None) -> str:
    """Extrae el dominio (netloc, sin puerto ni www.) de una URL. '' si no aplica."""
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    netloc = urlparse(url).netloc.lower()
    if ":" in netloc:
        netloc = netloc.split(":", 1)[0]
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def domains_match(credential_url: str | None, page_domain: str) -> bool:
    """Match exacto de dominio (anti-phishing): el dominio de la credencial debe ser
    idéntico al de la página, o la página un subdominio directo del de la credencial
    (login.cartesia.ai cuenta para cartesia.ai). Nunca al revés ni parecidos."""
    cred_domain = extract_domain(credential_url)
    page_domain = extract_domain(page_domain)
    if not cred_domain or not page_domain:
        return False
    return page_domain == cred_domain or page_domain.endswith("." + cred_domain)
