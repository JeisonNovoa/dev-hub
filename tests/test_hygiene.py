"""Tests del informe de higiene de contraseñas: análisis y página."""

from app.services.password_hygiene import analyze, weakness_reason


def _create_credential(client, label, password=None, url=None, login_via="email"):
    res = client.post("/api/credentials", json={
        "label": label,
        "username": "user@mail.com",
        "password": password,
        "url": url,
        "category": "personal",
        "login_via": login_via,
    })
    assert res.status_code == 201
    return res.json()["id"]


# ─── weakness_reason ─────────────────────────────────────────────────────────

def test_weakness_short():
    assert "muy corta" in weakness_reason("abc12")


def test_weakness_only_digits():
    assert weakness_reason("123456789012") == "solo números"


def test_weakness_only_letters():
    assert weakness_reason("abcdefghijkl") == "solo letras"


def test_weakness_short_low_variety():
    assert weakness_reason("abcd12345") == "corta y con poca variedad"


def test_strong_password_passes():
    assert weakness_reason("Tr3s-tristes_Tigres!") is None


def test_acceptable_two_classes_long():
    assert weakness_reason("abcdefgh12345") is None


# ─── analyze ─────────────────────────────────────────────────────────────────

class _FakeCred:
    def __init__(self, label, password=None, url=None, login_via="email"):
        self.label = label
        self.password = password
        self.url = url
        self.login_via = login_via


def test_analyze_groups_reused():
    creds = [
        _FakeCred("A", password="Compartida-123!", url="https://a.com"),
        _FakeCred("B", password="Compartida-123!", url="https://b.com"),
        _FakeCred("C", password="Otra-Unica-456!", url="https://c.com"),
    ]
    report = analyze(creds)
    assert len(report.reused) == 1
    assert {c.label for c in report.reused[0]} == {"A", "B"}


def test_analyze_no_url_and_no_password():
    creds = [
        _FakeCred("SinURL", password="Buena-Clave-789!"),
        _FakeCred("SinPass", url="https://x.com"),
        _FakeCred("OAuth sin pass", url="https://y.com", login_via="google"),
    ]
    report = analyze(creds)
    assert [c.label for c in report.no_url] == ["SinURL"]
    # OAuth sin contraseña es normal: solo cuenta la de método email.
    assert [c.label for c in report.no_password] == ["SinPass"]


def test_analyze_healthy_vault():
    creds = [_FakeCred("OK", password="Super-Clave-2026!", url="https://ok.com")]
    report = analyze(creds)
    assert report.issues == 0
    assert report.total == 1


# ─── Página /credentials/higiene ─────────────────────────────────────────────

def test_hygiene_page_renders_findings(client):
    _create_credential(client, "Sitio A", password="repetida99", url="https://a.com")
    _create_credential(client, "Sitio B", password="repetida99", url="https://b.com")
    _create_credential(client, "Debil", password="123456", url="https://c.com")
    _create_credential(client, "Sin URL", password="Clave-Fuerte-2026!")

    res = client.get("/credentials/higiene")
    assert res.status_code == 200
    body = res.text
    assert "reutilizadas" in body
    assert "Sitio A" in body and "Sitio B" in body
    assert "muy corta" in body
    assert "Sin URL" in body


def test_hygiene_page_never_leaks_passwords(client):
    _create_credential(client, "Secreta", password="repetida99", url="https://a.com")
    _create_credential(client, "Secreta2", password="repetida99", url="https://b.com")
    _create_credential(client, "Corta", password="123456", url="https://c.com")

    res = client.get("/credentials/higiene")
    assert "repetida99" not in res.text
    assert "123456" not in res.text


def test_hygiene_page_healthy(client):
    _create_credential(client, "Sana", password="Clave-Robusta-2026!", url="https://ok.com")
    res = client.get("/credentials/higiene")
    assert res.status_code == 200
    assert "excelente" in res.text
    assert "problemas detectables" in res.text


def test_hygiene_page_isolated_per_user(client, db):
    from app.auth import hash_password
    from app.models import Credential, User

    other = User(email="otro@test.local", hashed_password=hash_password("password123"), is_active=True)
    db.add(other)
    db.flush()
    db.add(Credential(label="Ajena Debil", user_id=other.id, password="123", url="https://x.com"))
    db.commit()

    res = client.get("/credentials/higiene")
    assert "Ajena Debil" not in res.text


def test_hygiene_requires_login(unauth_client):
    res = unauth_client.get("/credentials/higiene", follow_redirects=False)
    assert res.status_code == 302


# ─── Puntaje de salud global ─────────────────────────────────────────────────

def test_health_score_perfect_when_no_issues():
    creds = [_FakeCred("OK", password="Super-Clave-2026!", url="https://ok.com")]
    report = analyze(creds)
    assert report.health_score == 100
    assert report.health_label == "excelente"


def test_health_score_empty_vault():
    report = analyze([])
    assert report.health_score == 100


def test_health_score_drops_with_issues():
    creds = [
        _FakeCred("A", password="123456", url="https://a.com"),       # débil
        _FakeCred("B", password="123456", url="https://b.com"),       # débil + reutilizada con A
        _FakeCred("C", password="abcdefghij", url="https://c.com"),   # débil
        _FakeCred("D", password="Buena-Clave-2026!"),                 # sin url
    ]
    report = analyze(creds)
    assert 0 <= report.health_score < 100
    assert report.health_label in ("buena", "mejorable", "en riesgo")


def test_health_score_clamped_0_100():
    creds = [_FakeCred(f"x{i}", password="123", url="https://x.com") for i in range(50)]
    report = analyze(creds)
    assert 0 <= report.health_score <= 100


# ─── Have I Been Pwned (k-anonymity) ─────────────────────────────────────────

import hashlib

from app.services.pwned import check_passwords


class _FakeResponse:
    def __init__(self, text):
        self.text = text
    def raise_for_status(self):
        pass


class _FakeClient:
    """Cliente HTTP falso: responde como la API range de HIBP."""
    def __init__(self, breached_passwords):
        # password -> nº de veces visto
        self._db = {}
        for pwd, count in breached_passwords.items():
            self._db[hashlib.sha1(pwd.encode()).hexdigest().upper()] = count
        self.calls = []
    def get(self, url):
        prefix = url.rsplit("/", 1)[-1]
        self.calls.append(prefix)
        lines = [f"{h[5:]}:{c}" for h, c in self._db.items() if h.startswith(prefix)]
        # Ruido: sufijos que no son de nadie, para asegurar el match exacto
        lines.append("0000000000000000000000000000000000:9")
        return _FakeResponse("\r\n".join(lines))


def test_pwned_detects_breached():
    client = _FakeClient({"123456": 37359195})
    result = check_passwords([("Cuenta débil", "123456"), ("Cuenta fuerte", "Zx9$wq2-La!7")], client=client)
    assert result.checked
    assert result.breached == [("Cuenta débil", 37359195)]


def test_pwned_clean_when_none_breached():
    client = _FakeClient({"123456": 100})
    result = check_passwords([("Segura", "Zx9$wq2-La!7")], client=client)
    assert result.checked
    assert result.breached == []


def test_pwned_only_sends_hash_prefix():
    """Garantía de privacidad: a la API solo viaja el prefijo de 5 chars del SHA-1."""
    client = _FakeClient({})
    check_passwords([("X", "mi-contraseña-secreta")], client=client)
    full_hash = hashlib.sha1("mi-contraseña-secreta".encode()).hexdigest().upper()
    assert client.calls == [full_hash[:5]]
    assert all(len(c) == 5 for c in client.calls)


def test_pwned_groups_by_prefix():
    # Dos contraseñas distintas; cada una su prefijo → 2 llamadas como mucho
    client = _FakeClient({})
    check_passwords([("A", "alpha"), ("B", "beta")], client=client)
    assert len(client.calls) <= 2


def test_pwned_resilient_on_network_error():
    class _BoomClient:
        def get(self, url):
            raise RuntimeError("sin red")
    result = check_passwords([("X", "123456")], client=_BoomClient())
    assert result.checked is False
    assert result.breached == []
    assert result.error


def test_pwned_empty_list():
    result = check_passwords([])
    assert result.checked
    assert result.breached == []


# ─── Página: medidor y endpoint de filtraciones ──────────────────────────────

def test_hygiene_page_shows_health_score(client):
    _create_credential(client, "OK", password="Clave-Robusta-2026!", url="https://ok.com")
    res = client.get("/credentials/higiene")
    assert res.status_code == 200
    assert "Salud de la bóveda" in res.text
    assert "Comprobar filtraciones" in res.text
