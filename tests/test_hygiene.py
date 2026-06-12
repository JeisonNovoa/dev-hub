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
    assert "Bóveda sana" in res.text


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
