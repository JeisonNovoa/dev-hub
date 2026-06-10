from pathlib import Path

from slowapi import Limiter
from slowapi.util import get_remote_address

# slowapi lee .env con cp1252 en Windows; pydantic-settings ya carga .env en UTF-8.
_SLOWAPI_ENV = Path(__file__).resolve().parent.parent / ".slowapi.env"
limiter = Limiter(key_func=get_remote_address, config_filename=str(_SLOWAPI_ENV))
