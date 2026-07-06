CSV_CONTENT = b"id,name\n1,Alice\n2,Bob\n"
JSON_CONTENT = b'[{"id": 1}, {"id": 2}, {"id": 3}]'


def _create(client, auth_headers, path="/api/users", content=CSV_CONTENT, filename="users.csv", **fields):
    data = {"path": path, "method": "GET", "auth_type": "none", **fields}
    files = {"file": (filename, content, "application/octet-stream")}
    resp = client.post("/admin/endpoints", data=data, files=files, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_update_requires_admin_token(client, auth_headers):
    created = _create(client, auth_headers)
    resp = client.patch(f"/admin/endpoints/{created['endpoint']['id']}", data={"description": "x"})
    assert resp.status_code in (401, 403)


def test_update_unknown_endpoint_returns_404(client, auth_headers):
    resp = client.patch("/admin/endpoints/does-not-exist", data={"description": "x"}, headers=auth_headers)
    assert resp.status_code == 404


def test_update_description_only_leaves_everything_else_unchanged(client, auth_headers):
    created = _create(client, auth_headers, description="old")
    endpoint_id = created["endpoint"]["id"]

    resp = client.patch(
        f"/admin/endpoints/{endpoint_id}", data={"description": "new"}, headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["endpoint"]["description"] == "new"
    assert body["endpoint"]["path"] == "/api/users"
    assert body["endpoint"]["method"] == "GET"
    assert body["artifact"]["name"] == "users.csv"

    # The mock still serves correctly at the unchanged path.
    served = client.get("/api/users")
    assert served.status_code == 200


def test_update_path(client, auth_headers):
    created = _create(client, auth_headers, path="/api/old")
    endpoint_id = created["endpoint"]["id"]

    resp = client.patch(f"/admin/endpoints/{endpoint_id}", data={"path": "/api/new"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["endpoint"]["path"] == "/api/new"

    assert client.get("/api/old").status_code == 404
    assert client.get("/api/new").status_code == 200


def test_update_method(client, auth_headers):
    created = _create(client, auth_headers)
    endpoint_id = created["endpoint"]["id"]

    resp = client.patch(f"/admin/endpoints/{endpoint_id}", data={"method": "POST"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["endpoint"]["method"] == "POST"

    assert client.get("/api/users").status_code == 404
    assert client.post("/api/users").status_code == 200


def test_update_rejects_invalid_method(client, auth_headers):
    created = _create(client, auth_headers)
    resp = client.patch(
        f"/admin/endpoints/{created['endpoint']['id']}", data={"method": "FETCH"}, headers=auth_headers
    )
    assert resp.status_code == 422


def test_update_rejects_path_conflicting_with_another_endpoint(client, auth_headers):
    _create(client, auth_headers, path="/api/first")
    second = _create(client, auth_headers, path="/api/second")

    resp = client.patch(
        f"/admin/endpoints/{second['endpoint']['id']}", data={"path": "/api/first"}, headers=auth_headers
    )
    assert resp.status_code == 409


def test_update_to_its_own_current_path_is_not_a_conflict(client, auth_headers):
    created = _create(client, auth_headers, path="/api/users")
    endpoint_id = created["endpoint"]["id"]

    resp = client.patch(
        f"/admin/endpoints/{endpoint_id}",
        data={"path": "/api/users", "description": "still fine"},
        headers=auth_headers,
    )
    assert resp.status_code == 200


def test_update_rejects_reserved_path(client, auth_headers):
    created = _create(client, auth_headers)
    resp = client.patch(
        f"/admin/endpoints/{created['endpoint']['id']}", data={"path": "/admin/sneaky"}, headers=auth_headers
    )
    assert resp.status_code == 422


def test_update_auth_type(client, auth_headers):
    created = _create(client, auth_headers)
    endpoint_id = created["endpoint"]["id"]

    resp = client.patch(
        f"/admin/endpoints/{endpoint_id}", data={"auth_type": "api_key"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["endpoint"]["auth_type"] == "api_key"

    # Now protected — unauthenticated access is rejected.
    assert client.get("/api/users").status_code == 401


def test_update_replaces_artifact_file_and_removes_old_one(client, auth_headers):
    from app import storage

    created = _create(client, auth_headers, content=CSV_CONTENT, filename="old.csv")
    endpoint_id = created["endpoint"]["id"]
    old_artifact_id = created["artifact"]["id"]
    old_file_path = storage.ARTIFACTS_DIR / created["artifact"]["filename"]
    assert old_file_path.exists()

    resp = client.patch(
        f"/admin/endpoints/{endpoint_id}",
        data={},
        files={"file": ("new.json", JSON_CONTENT, "application/json")},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["artifact"]["name"] == "new.json"
    assert body["artifact"]["format"] == "json"
    assert body["artifact"]["row_count"] == 3
    assert body["artifact"]["id"] != old_artifact_id

    # Old artifact record and file are both gone.
    assert not old_file_path.exists()
    assert old_artifact_id not in storage.get_data().artifacts

    # The mock now serves the new content (JSON preserves the int type,
    # unlike CSV which stringifies every value).
    served = client.get("/api/users")
    assert served.json() == [{"id": 1}, {"id": 2}, {"id": 3}]


def test_update_replacement_file_is_still_validated(client, auth_headers):
    created = _create(client, auth_headers)
    resp = client.patch(
        f"/admin/endpoints/{created['endpoint']['id']}",
        data={},
        files={"file": ("bad.json", b"not json", "application/json")},
        headers=auth_headers,
    )
    assert resp.status_code == 422
