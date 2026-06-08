"""
File-backed JSON storage.

All state lives in DATA_DIR (default /data) as a single config.json.
Uploaded artifact files sit in DATA_DIR/artifacts/.

Thread safety: a simple threading.Lock guards reads and writes in process.
For multi-process deployments a proper DB would be needed; this is intentional
V1 scope for single-container EC2 use.
"""

import os
import threading
from pathlib import Path
from typing import Callable

from app.models import AppData

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
ARTIFACTS_DIR = DATA_DIR / "artifacts"
CONFIG_FILE = DATA_DIR / "config.json"

_lock = threading.Lock()
_data: AppData | None = None


def init_storage() -> None:
    global _data
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    if CONFIG_FILE.exists():
        raw = CONFIG_FILE.read_text(encoding="utf-8")
        _data = AppData.model_validate_json(raw)
    else:
        _data = AppData()
        _flush()


def get_data() -> AppData:
    assert _data is not None, "Storage not initialised — call init_storage() first"
    return _data


def mutate(fn: Callable[[AppData], None]) -> None:
    """Apply fn to the in-memory AppData then persist to disk."""
    with _lock:
        fn(_data)
        _flush()


def _flush() -> None:
    tmp = CONFIG_FILE.with_suffix(".tmp")
    tmp.write_text(_data.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(CONFIG_FILE)   # atomic on POSIX
