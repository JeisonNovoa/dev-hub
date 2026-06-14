import bleach
import markdown as md
from fastapi.templating import Jinja2Templates

from app.utils.activity import EVENT_DOT
from app.utils.projects import relative_activity
from app.utils.url import extract_domain

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
    return extract_domain(url)


def _event_dot_filter(entity: str) -> str:
    return EVENT_DOT.get(entity, "bg-gray-500")


def _is_stale_filter(moment) -> bool:
    from app.routers.ui.credentials import is_stale
    return is_stale(moment)


templates.env.filters["markdown"] = _markdown_filter
templates.env.filters["domain"] = _domain_filter
templates.env.filters["relative_time"] = relative_activity
templates.env.filters["event_dot"] = _event_dot_filter
templates.env.filters["is_stale"] = _is_stale_filter
