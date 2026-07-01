import pytest
from fastapi.testclient import TestClient

from app.main import app as fastapi_app


def test_server_refuses_to_start_without_admin_token(data_dir, monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="ADMIN_TOKEN"):
        with TestClient(fastapi_app):
            pass


def test_server_refuses_to_start_with_default_admin_token(data_dir, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "changeme")
    with pytest.raises(RuntimeError, match="ADMIN_TOKEN"):
        with TestClient(fastapi_app):
            pass


def test_server_starts_with_a_real_admin_token(data_dir, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "a-real-secret-value")
    with TestClient(fastapi_app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
