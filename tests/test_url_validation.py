def test_link_url_invalid(client):
    client.post("/api/projects", json={"name": "Mi App"})
    res = client.post("/api/projects/mi-app/links", json={"label": "Bad", "url": "not-a-url"})
    assert res.status_code == 422


def test_link_url_valid(client):
    client.post("/api/projects", json={"name": "Mi App"})
    res = client.post("/api/projects/mi-app/links", json={"label": "Good", "url": "https://example.com"})
    assert res.status_code == 201


def test_service_url_invalid(client):
    res = client.post("/api/services", json={"name": "Bad Svc", "url": "ftp://nope.com"})
    assert res.status_code == 422


def test_service_url_valid(client):
    res = client.post("/api/services", json={"name": "Good Svc", "url": "https://example.com"})
    assert res.status_code == 201


def test_service_url_optional_null(client):
    res = client.post("/api/services", json={"name": "No URL Svc"})
    assert res.status_code == 201


def test_credential_url_invalid(client):
    res = client.post("/api/credentials", json={"label": "Bad", "url": "javascript:alert(1)"})
    assert res.status_code == 422


def test_credential_url_valid(client):
    res = client.post("/api/credentials", json={"label": "Good", "url": "https://login.example.com"})
    assert res.status_code == 201


def test_repo_github_url_invalid(client):
    client.post("/api/projects", json={"name": "Mi App"})
    res = client.post("/api/projects/mi-app/repos", json={"name": "MyRepo", "github_url": "git@github.com:user/repo.git"})
    assert res.status_code == 422


def test_repo_github_url_valid(client):
    client.post("/api/projects", json={"name": "Mi App"})
    res = client.post("/api/projects/mi-app/repos", json={"name": "MyRepo", "github_url": "https://github.com/user/repo"})
    assert res.status_code == 201
