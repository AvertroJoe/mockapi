CSV_CONTENT = b"id,name,email,role\n1,Alice,alice@example.com,admin\n2,Bob,bob@example.com,viewer\n"
JSON_CONTENT = b'[{"id": 1, "name": "Widget"}, {"id": 2, "name": "Gadget"}]'
XML_CONTENT = b"""<?xml version="1.0"?><orders><order><id>1</id></order><order><id>2</id></order></orders>"""


def _upload(client, headers, path="/api/users", filename="users.csv", content=CSV_CONTENT, **fields):
    data = {"path": path, "method": "GET", "auth_type": "none", **fields}
    files = {"file": (filename, content, "application/octet-stream")}
    return client.post("/admin/endpoints", data=data, files=files, headers=headers)


def test_create_endpoint_requires_admin_token(client):
    resp = _upload(client, headers={})
    assert resp.status_code in (401, 403)


def test_create_endpoint_rejects_wrong_admin_token(client):
    resp = _upload(client, headers={"Authorization": "Bearer wrong-token"})
    assert resp.status_code == 403


def test_create_csv_endpoint(client, auth_headers):
    resp = _upload(client, auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["endpoint"]["path"] == "/api/users"
    assert body["endpoint"]["method"] == "GET"
    assert body["artifact"]["format"] == "csv"
    assert body["artifact"]["row_count"] == 2


def test_create_json_endpoint(client, auth_headers):
    resp = _upload(client, auth_headers, path="/api/products", filename="products.json", content=JSON_CONTENT)
    assert resp.status_code == 200
    body = resp.json()
    assert body["artifact"]["format"] == "json"
    assert body["artifact"]["row_count"] == 2


def test_create_xml_endpoint(client, auth_headers):
    resp = _upload(client, auth_headers, path="/api/orders", filename="orders.xml", content=XML_CONTENT)
    assert resp.status_code == 200
    body = resp.json()
    assert body["artifact"]["format"] == "xml"
    assert body["artifact"]["row_count"] == 2


def test_create_endpoint_rejects_unsupported_extension(client, auth_headers):
    resp = _upload(client, auth_headers, filename="notes.txt", content=b"hello")
    assert resp.status_code == 422
    errors = resp.json()["detail"]["errors"]
    assert errors == [{"field": "file", "reason": "Only .csv, .json, and .xml files are supported"}]


def test_create_endpoint_rejects_oversized_file(client, auth_headers):
    from app.admin import MAX_UPLOAD_BYTES

    oversized = b"a" * (MAX_UPLOAD_BYTES + 1)
    resp = _upload(client, auth_headers, filename="huge.json", content=oversized)
    assert resp.status_code == 413


def test_create_endpoint_rejects_malformed_json(client, auth_headers):
    resp = _upload(client, auth_headers, filename="bad.json", content=b"{not valid json")
    assert resp.status_code == 422
    assert resp.json()["detail"]["errors"][0]["field"] == "file"


def test_create_endpoint_rejects_xml_entity_expansion_bomb(client, auth_headers):
    bomb = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY a "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA">
 <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
 <!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">
]>
<lolz>&c;</lolz>"""
    resp = _upload(client, auth_headers, path="/api/bomb", filename="bomb.xml", content=bomb)
    assert resp.status_code == 422
    assert resp.json()["detail"]["errors"][0]["field"] == "file"


def test_create_endpoint_rejects_duplicate_path_and_method(client, auth_headers):
    first = _upload(client, auth_headers)
    assert first.status_code == 200

    dup = _upload(client, auth_headers, filename="users2.csv")
    assert dup.status_code == 409


def test_path_without_leading_slash_is_normalised(client, auth_headers):
    resp = _upload(client, auth_headers, path="api/users")
    assert resp.status_code == 200
    assert resp.json()["endpoint"]["path"] == "/api/users"


def test_list_endpoints(client, auth_headers):
    _upload(client, auth_headers)
    resp = client.get("/admin/endpoints", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["path"] == "/api/users"
    assert items[0]["artifact_name"] == "users.csv"
    assert items[0]["artifact_rows"] == 2


def test_delete_endpoint_removes_endpoint_and_file(client, auth_headers):
    created = _upload(client, auth_headers).json()
    endpoint_id = created["endpoint"]["id"]

    resp = client.delete(f"/admin/endpoints/{endpoint_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted_endpoint"] == endpoint_id

    listing = client.get("/admin/endpoints", headers=auth_headers).json()
    assert listing == []


def test_delete_unknown_endpoint_returns_404(client, auth_headers):
    resp = client.delete("/admin/endpoints/does-not-exist", headers=auth_headers)
    assert resp.status_code == 404
