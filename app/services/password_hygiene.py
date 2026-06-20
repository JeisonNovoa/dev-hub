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

    @property
    def health_score(self) -> int:
        """Salud global de la bóveda, 0–100.

        Parte de 100 y descuenta según la gravedad relativa de cada problema
        (reutilizadas y débiles pesan más que sin-url/sin-contraseña). Se pondera
        por el total de credenciales para que en bóvedas grandes unos pocos
        problemas no hundan el puntaje.
        """
        if self.total == 0:
            return 100
        reused_count = sum(len(group) for group in self.reused)
        # Peso de cada credencial problemática (0..1 aprox por item).
        penalty = (
            reused_count * 1.0
            + len(self.weak) * 0.8
            + len(self.no_url) * 0.3
            + len(self.no_password) * 0.3
        )
        score = 100 - round(penalty / self.total * 100)
        return max(0, min(100, score))

    @property
    def health_label(self) -> str:
        s = self.health_score
        if s >= 90:
            return "excelente"
        if s >= 70:
            return "buena"
        if s >= 40:
            return "mejorable"
        return "en riesgo"


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


@dataclass(frozen=True)
class CredentialSecurity:
    """Análisis de seguridad de UNA credencial, para su página de detalle."""

    has_password: bool
    strong: bool                  # contraseña aceptable (sin motivo de debilidad)
    weakness: str | None          # motivo si es débil
    strength_score: int           # 0..4 segmentos llenos para la barra
    length: int
    char_classes: int             # variedad (minús/mayús/dígitos/símbolos)
    reused: bool                  # comparte contraseña con otra credencial
    reused_with: list[str]        # etiquetas de las otras que la comparten


def _char_classes(password: str) -> int:
    return sum([
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ])


def analyze_credential(cred: Credential, all_credentials: list[Credential]) -> CredentialSecurity:
    """Seguridad de una credencial frente al resto de la bóveda. Las contraseñas
    se comparan en memoria; nada de esto se persiste ni sale más allá del informe."""
    password = cred.password
    if not password:
        return CredentialSecurity(
            has_password=False, strong=False, weakness=None, strength_score=0,
            length=0, char_classes=0, reused=False, reused_with=[],
        )

    reason = weakness_reason(password)
    classes = _char_classes(password)
    # Barra de 0..4: penaliza longitud corta y poca variedad.
    score = classes
    if len(password) < 8:
        score = min(score, 1)
    elif len(password) < 12:
        score = min(score, 3)
    if reason is None:
        score = max(score, 3)
    score = max(0, min(4, score))

    reused_with = [
        c.label for c in all_credentials
        if c.id != cred.id and c.password and c.password == password
    ]

    return CredentialSecurity(
        has_password=True,
        strong=reason is None,
        weakness=reason,
        strength_score=score,
        length=len(password),
        char_classes=classes,
        reused=bool(reused_with),
        reused_with=reused_with,
    )


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
