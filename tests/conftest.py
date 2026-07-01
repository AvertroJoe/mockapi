import pytest
from fastapi.testclient import TestClient

from app import storage
from app.main import app as fastapi_app

TEST_ADMIN_TOKEN = "test-admin-token"


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Point app.storage at an isolated, per-test directory."""
    base = tmp_path / "data"
    monkeypatch.setattr(storage, "DATA_DIR", base)
    monkeypatch.setattr(storage, "ARTIFACTS_DIR", base / "artifacts")
    monkeypatch.setattr(storage, "CONFIG_FILE", base / "config.json")
    monkeypatch.setattr(storage, "_data", None)
    return base


@pytest.fixture
def admin_token(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", TEST_ADMIN_TOKEN)
    return TEST_ADMIN_TOKEN


@pytest.fixture
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def client(data_dir, admin_token):
    """A TestClient with isolated storage and a known admin token.

    Entering/exiting the context manager triggers the app's lifespan,
    which calls init_storage() against the patched (empty) data_dir.
    """
    with TestClient(fastapi_app) as c:
        yield c


