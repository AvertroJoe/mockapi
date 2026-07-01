from app.admin import MAX_CSV_ROWS


def _upload(client, headers, path="/api/data", filename="data.csv", content=b"", method="GET"):
    data = {"path": path, "method": method, "auth_type": "none"}
    files = {"file": (filename, content, "application/octet-stream")}
    return client.post("/admin/endpoints", data=data, files=files, headers=headers)


def _errors(resp):
    return resp.json()["detail"]["errors"]


# ── File content: empty / encoding ──────────────────────────────

def test_rejects_empty_csv(client, auth_headers):
    resp = _upload(client, auth_headers, filename="empty.csv", content=b"")
    assert resp.status_code == 422
    assert _errors(resp) == [{"field": "file", "reason": "File is empty"}]


def test_rejects_whitespace_only_json(client, auth_headers):
    resp = _upload(client, auth_headers, filename="blank.json", content=b"   \n  ")
    assert resp.status_code == 422
    assert _errors(resp)[0]["reason"] == "File is empty"


def test_rejects_non_utf8_file(client, auth_headers):
    resp = _upload(client, auth_headers, filename="bad.csv", content=b"\xff\xfe\x00\x01")
    assert resp.status_code == 422
    assert _errors(resp) == [{"field": "file", "reason": "File is not valid UTF-8 text"}]


# ── CSV structural validation ───────────────────────────────────

def test_accepts_header_only_csv_with_zero_rows(client, auth_headers):
    resp = _upload(client, auth_headers, filename="data.csv", content=b"id,name\n")
    assert resp.status_code == 200
    assert resp.json()["artifact"]["row_count"] == 0


def test_rejects_csv_row_with_extra_column(client, auth_headers):
    content = b"id,name\n1,Alice,extra\n"
    resp = _upload(client, auth_headers, filename="ragged.csv", content=content)
    assert resp.status_code == 422
    assert "Row 2" in _errors(resp)[0]["reason"]


def test_rejects_csv_row_with_missing_column(client, auth_headers):
    content = b"id,name,email\n1,Alice\n"
    resp = _upload(client, auth_headers, filename="ragged.csv", content=content)
    assert resp.status_code == 422
    assert "Row 2" in _errors(resp)[0]["reason"]


def test_rejects_csv_exceeding_max_rows(client, auth_headers):
    header = "id\n"
    rows = "\n".join(str(i) for i in range(MAX_CSV_ROWS + 1))
    content = (header + rows).encode()
    resp = _upload(client, auth_headers, filename="huge.csv", content=content)
    assert resp.status_code == 422
    assert "maximum" in _errors(resp)[0]["reason"]


def test_accepts_csv_at_max_rows(client, auth_headers):
    header = "id\n"
    rows = "\n".join(str(i) for i in range(MAX_CSV_ROWS))
    content = (header + rows).encode()
    resp = _upload(client, auth_headers, filename="atmax.csv", content=content)
    assert resp.status_code == 200
    assert resp.json()["artifact"]["row_count"] == MAX_CSV_ROWS


# ── JSON shape validation ────────────────────────────────────────

def test_rejects_json_scalar(client, auth_headers):
    resp = _upload(client, auth_headers, filename="scalar.json", content=b"42")
    assert resp.status_code == 422
    assert _errors(resp) == [
        {"field": "file", "reason": "JSON file must be an object or an array of objects"}
    ]


def test_rejects_json_array_of_non_objects(client, auth_headers):
    resp = _upload(client, auth_headers, filename="list.json", content=b'["a", "b", "c"]')
    assert resp.status_code == 422
    assert _errors(resp) == [{"field": "file", "reason": "JSON array must contain only objects"}]


def test_accepts_single_json_object(client, auth_headers):
    resp = _upload(client, auth_headers, filename="obj.json", content=b'{"id": 1, "name": "Widget"}')
    assert resp.status_code == 200
    assert resp.json()["artifact"]["row_count"] is None


# ── Path validation ──────────────────────────────────────────────

def test_rejects_empty_path(client, auth_headers):
    resp = _upload(client, auth_headers, path="/", content=b"id\n1\n")
    assert resp.status_code == 422
    assert _errors(resp) == [{"field": "path", "reason": "Path must not be empty"}]


def test_rejects_path_with_query_string(client, auth_headers):
    resp = _upload(client, auth_headers, path="/api/users?x=1", content=b"id\n1\n")
    assert resp.status_code == 422
    assert _errors(resp)[0]["field"] == "path"


def test_rejects_path_with_whitespace(client, auth_headers):
    resp = _upload(client, auth_headers, path="/api/us ers", content=b"id\n1\n")
    assert resp.status_code == 422
    assert _errors(resp)[0]["field"] == "path"


def test_rejects_path_colliding_with_admin(client, auth_headers):
    resp = _upload(client, auth_headers, path="/admin/sneaky", content=b"id\n1\n")
    assert resp.status_code == 422
    assert "reserved" in _errors(resp)[0]["reason"]


def test_rejects_path_colliding_with_health(client, auth_headers):
    resp = _upload(client, auth_headers, path="/health", content=b"id\n1\n")
    assert resp.status_code == 422
    assert "reserved" in _errors(resp)[0]["reason"]


# ── Method validation ────────────────────────────────────────────

def test_rejects_invalid_http_method(client, auth_headers):
    resp = _upload(client, auth_headers, content=b"id\n1\n", method="FETCH")
    assert resp.status_code == 422
    errors = _errors(resp)
    assert errors[0]["field"] == "method"


def test_rejects_lowercase_http_method(client, auth_headers):
    # HTTP method tokens are case-sensitive per RFC 7231 — "get" isn't "GET".
    resp = _upload(client, auth_headers, content=b"id\n1\n", method="get")
    assert resp.status_code == 422
    assert _errors(resp)[0]["field"] == "method"


def test_accepts_every_valid_http_method(client, auth_headers):
    for i, method in enumerate(["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]):
        resp = _upload(client, auth_headers, path=f"/api/m{i}", content=b"id\n1\n", method=method)
        assert resp.status_code == 200, resp.text
