from urllib.parse import urlparse

import markdown as md
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")


def _markdown_filter(text: str | None) -> str:
    return md.markdown(text or "", extensions=["fenced_code", "tables"])


def _domain_filter(url: str) -> str:
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return urlparse(url).netloc


templates.env.filters["markdown"] = _markdown_filter
templates.env.filters["domain"] = _domain_filter
