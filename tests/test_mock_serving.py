import base64

CSV_CONTENT = b"id,name\n1,Alice\n2,Bob\n"
XML_CONTENT = b"<orders><order><id>1</id></order></orders>"


def _create_endpoint(client, auth_headers, path, auth_type="none", filename="data.csv", content=CSV_CONTENT):
    resp = client.post(
        "/admin/endpoints",
        data={"path": path, "method": "GET", "auth_type": auth_type},
        files={"file": (filename, content, "application/octet-stream")},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_unregistered_path_returns_404(client):
    resp = client.get("/api/nope")
    assert resp.status_code == 404


def test_csv_endpoint_served_as_json(client, auth_headers):
    _create_endpoint(client, auth_headers, "/api/users")
    resp = client.get("/api/users")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]


def test_xml_endpoint_served_as_xml_unchanged(client, auth_headers):
    _create_endpoint(client, auth_headers, "/api/orders", filename="orders.xml", content=XML_CONTENT)
    resp = client.get("/api/orders")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")
    assert resp.content == XML_CONTENT


def test_wrong_method_returns_404(client, auth_headers):
    _create_endpoint(client, auth_headers, "/api/users")
    resp = client.post("/api/users")
    assert resp.status_code == 404


# ── api_key auth ───────────────────────────────────────────────────

def test_api_key_endpoint_rejects_missing_key(client, auth_headers):
    _create_endpoint(client, auth_headers, "/api/secure", auth_type="api_key")
    resp = client.get("/api/secure")
    assert resp.status_code == 401


def test_api_key_endpoint_rejects_invalid_key(client, auth_headers):
    _create_endpoint(client, auth_headers, "/api/secure", auth_type="api_key")
    resp = client.get("/api/secure", headers={"X-API-Key": "not-a-real-key"})
    assert resp.status_code == 403


def test_api_key_endpoint_accepts_header_and_query_param(client, auth_headers):
    _create_endpoint(client, auth_headers, "/api/secure", auth_type="api_key")
    key = client.post("/admin/auth/api-keys", json={"name": "svc"}, headers=auth_headers).json()["key"]

    via_header = client.get("/api/secure", headers={"X-API-Key": key})
    assert via_header.status_code == 200

    via_query = client.get("/api/secure", params={"api_key": key})
    assert via_query.status_code == 200


# ── basic auth ───────────────────────────────────────────────────

def _basic_header(username, password):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_basic_auth_endpoint_rejects_missing_credentials(client, auth_headers):
    _create_endpoint(client, auth_headers, "/api/internal", auth_type="basic")
    resp = client.get("/api/internal")
    assert resp.status_code == 401


def test_basic_auth_endpoint_rejects_wrong_password(client, auth_headers):
    _create_endpoint(client, auth_headers, "/api/internal", auth_type="basic")
    client.post("/admin/auth/users", json={"username": "alice", "password": "correct"}, headers=auth_headers)

    resp = client.get("/api/internal", headers=_basic_header("alice", "wrong"))
    assert resp.status_code == 403


def test_basic_auth_endpoint_accepts_correct_credentials(client, auth_headers):
    _create_endpoint(client, auth_headers, "/api/internal", auth_type="basic")
    client.post("/admin/auth/users", json={"username": "alice", "password": "correct"}, headers=auth_headers)

    resp = client.get("/api/internal", headers=_basic_header("alice", "correct"))
    assert resp.status_code == 200


# ── jwt auth ───────────────────────────────────────────────────

def test_jwt_endpoint_rejects_when_not_configured(client, auth_headers):
    _create_endpoint(client, auth_headers, "/api/jwt-guarded", auth_type="jwt")
    resp = client.get("/api/jwt-guarded", headers={"Authorization": "Bearer whatever"})
    assert resp.status_code == 500


def test_jwt_endpoint_accepts_valid_token(client, auth_headers):
    _create_endpoint(client, auth_headers, "/api/jwt-guarded", auth_type="jwt")
    client.post("/admin/auth/jwt/config", json={}, headers=auth_headers)
    token = client.post(
        "/admin/auth/jwt/token", json={"subject": "svc", "expires_in_seconds": 60}, headers=auth_headers
    ).json()["token"]

    resp = client.get("/api/jwt-guarded", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_jwt_endpoint_rejects_bad_token(client, auth_headers):
    _create_endpoint(client, auth_headers, "/api/jwt-guarded", auth_type="jwt")
    client.post("/admin/auth/jwt/config", json={}, headers=auth_headers)

    resp = client.get("/api/jwt-guarded", headers={"Authorization": "Bearer garbage.not.a.jwt"})
    assert resp.status_code == 403
