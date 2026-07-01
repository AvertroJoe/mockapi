import jwt as pyjwt

from app import storage


# ── API keys ─────────────────────────────────────────────────────

def test_api_key_plaintext_never_persisted_to_disk(client, auth_headers):
    created = client.post("/admin/auth/api-keys", json={"name": "svc"}, headers=auth_headers).json()
    full_key = created["key"]

    raw = storage.CONFIG_FILE.read_text(encoding="utf-8")
    assert full_key not in raw


def test_create_and_list_api_keys(client, auth_headers):
    created = client.post("/admin/auth/api-keys", json={"name": "my-service"}, headers=auth_headers)
    assert created.status_code == 200
    body = created.json()
    assert body["name"] == "my-service"
    full_key = body["key"]
    assert len(full_key) > 16

    listed = client.get("/admin/auth/api-keys", headers=auth_headers).json()
    assert len(listed) == 1
    # The full key is never shown again — only a masked form.
    assert listed[0]["key"] != full_key
    assert listed[0]["key"].startswith(full_key[:8])


def test_delete_api_key(client, auth_headers):
    created = client.post("/admin/auth/api-keys", json={"name": "svc"}, headers=auth_headers).json()
    resp = client.delete(f"/admin/auth/api-keys/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert client.get("/admin/auth/api-keys", headers=auth_headers).json() == []


def test_delete_unknown_api_key_returns_404(client, auth_headers):
    resp = client.delete("/admin/auth/api-keys/nope", headers=auth_headers)
    assert resp.status_code == 404


# ── Basic-auth users ─────────────────────────────────────────────

def test_create_and_list_basic_user(client, auth_headers):
    resp = client.post(
        "/admin/auth/users", json={"username": "alice", "password": "hunter2"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"

    listed = client.get("/admin/auth/users", headers=auth_headers).json()
    assert [u["username"] for u in listed] == ["alice"]


def test_create_duplicate_username_rejected(client, auth_headers):
    client.post("/admin/auth/users", json={"username": "alice", "password": "hunter2"}, headers=auth_headers)
    resp = client.post("/admin/auth/users", json={"username": "alice", "password": "other"}, headers=auth_headers)
    assert resp.status_code == 409


def test_delete_basic_user(client, auth_headers):
    client.post("/admin/auth/users", json={"username": "alice", "password": "hunter2"}, headers=auth_headers)
    resp = client.delete("/admin/auth/users/alice", headers=auth_headers)
    assert resp.status_code == 200
    assert client.get("/admin/auth/users", headers=auth_headers).json() == []


# ── JWT ──────────────────────────────────────────────────────────

def test_jwt_status_defaults_to_unconfigured(client, auth_headers):
    resp = client.get("/admin/auth/jwt", headers=auth_headers)
    assert resp.json() == {"configured": False}


def test_jwt_config_and_token_roundtrip(client, auth_headers):
    configured = client.post("/admin/auth/jwt/config", json={}, headers=auth_headers)
    assert configured.status_code == 200
    secret = configured.json()["secret"]
    algorithm = configured.json()["algorithm"]

    status = client.get("/admin/auth/jwt", headers=auth_headers).json()
    assert status == {"configured": True, "algorithm": algorithm}

    token_resp = client.post(
        "/admin/auth/jwt/token",
        json={"subject": "my-service", "expires_in_seconds": 60},
        headers=auth_headers,
    )
    assert token_resp.status_code == 200
    token = token_resp.json()["token"]

    decoded = pyjwt.decode(token, secret, algorithms=[algorithm])
    assert decoded["sub"] == "my-service"


def test_generate_token_before_config_fails(client, auth_headers):
    resp = client.post("/admin/auth/jwt/token", json={"subject": "x"}, headers=auth_headers)
    assert resp.status_code == 400
