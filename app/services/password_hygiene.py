"""Análisis de higiene de contraseñas de la bóveda.

Todo ocurre en el servidor: las contraseñas se descifran en memoria para
compararlas y NUNCA salen en el informe — solo los hallazgos (qué credenciales
comparten contraseña, cuáles son débiles, etc.).
"""

from dataclasses import dataclass, field

from app.models import Credential


@dataclass(frozen=True)
class HygieneReport:
    total: int
    # Grupos de credenciales que comparten la misma contraseña (cada grupo >= 2).
    reused: list[list[Credential]] = field(default_factory=list)
    # (credencial, motivo) de contraseñas débiles.
    weak: list[tuple[Credential, str]] = field(default_factory=list)
    # Credenciales sin URL: la extensión no puede ofrecerlas en ningún sitio.
    no_url: list[Credential] = field(default_factory=list)
    # Método email+contraseña pero sin contraseña guardada (incompletas).
    no_password: list[Credential] = field(default_factory=list)

    @property
    def issues(self) -> int:
        reused_count = sum(len(group) for group in self.reused)
        return reused_count + len(self.weak) + len(self.no_url) + len(self.no_password)


def weakness_reason(password: str) -> str | None:
    """Motivo por el que una contraseña es débil, o None si es aceptable."""
    if len(password) < 8:
        return f"muy corta ({len(password)} caracteres)"
    if password.isdigit():
        return "solo números"
    if password.isalpha():
        return "solo letras"
    classes = sum([
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ])
    if len(password) < 10 and classes < 3:
        return "corta y con poca variedad"
    if classes <= 1:
        return "sin variedad de caracteres"
    return None


def analyze(credentials: list[Credential]) -> HygieneReport:
    by_password: dict[str, list[Credential]] = {}
    weak: list[tuple[Credential, str]] = []
    no_url: list[Credential] = []
    no_password: list[Credential] = []

    for cred in credentials:
        if not cred.url:
            no_url.append(cred)

        if cred.password:
            by_password.setdefault(cred.password, []).append(cred)
            reason = weakness_reason(cred.password)
            if reason:
                weak.append((cred, reason))
        elif cred.login_via == "email":
            no_password.append(cred)

    reused = [group for group in by_password.values() if len(group) >= 2]
    reused.sort(key=len, reverse=True)

    return HygieneReport(
        total=len(credentials),
        reused=reused,
        weak=weak,
        no_url=no_url,
        no_password=no_password,
    )
