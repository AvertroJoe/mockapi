from app import storage
from app.models import ArtifactRecord


def test_init_storage_creates_dirs_and_empty_config(data_dir):
    storage.init_storage()

    assert storage.DATA_DIR.exists()
    assert storage.ARTIFACTS_DIR.exists()
    assert storage.CONFIG_FILE.exists()

    data = storage.get_data()
    assert data.artifacts == {}
    assert data.endpoints == {}


def test_init_storage_loads_existing_config(data_dir, monkeypatch):
    storage.init_storage()
    storage.mutate(lambda d: d.artifacts.update({"a1": ArtifactRecord(id="a1", name="x.csv", filename="a1.csv", format="csv")}))

    # Simulate a fresh process picking the config back up.
    monkeypatch.setattr(storage, "_data", None)
    storage.init_storage()

    data = storage.get_data()
    assert "a1" in data.artifacts
    assert data.artifacts["a1"].name == "x.csv"


def test_mutate_persists_to_disk(data_dir):
    storage.init_storage()
    storage.mutate(lambda d: d.artifacts.update({"a1": ArtifactRecord(id="a1", name="y.json", filename="a1.json", format="json")}))

    raw = storage.CONFIG_FILE.read_text(encoding="utf-8")
    assert "y.json" in raw


def test_get_data_before_init_raises(monkeypatch):
    monkeypatch.setattr(storage, "_data", None)
    try:
        storage.get_data()
        assert False, "expected AssertionError"
    except AssertionError:
        pass
