from urllib.parse import urlparse

import bleach
import markdown as md
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")

_ALLOWED_TAGS = [
    "p", "br", "strong", "b", "em", "i", "code", "pre", "blockquote",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
    "hr", "del", "s",
]
_ALLOWED_ATTRS: dict[str, list[str]] = {
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title"],
    "code": ["class"],
    "td": ["align"],
    "th": ["align"],
}


def _markdown_filter(text: str | None) -> str:
    raw_html = md.markdown(text or "", extensions=["fenced_code", "tables"])
    return bleach.clean(raw_html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)


def _domain_filter(url: str) -> str:
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return urlparse(url).netloc


templates.env.filters["markdown"] = _markdown_filter
templates.env.filters["domain"] = _domain_filter
