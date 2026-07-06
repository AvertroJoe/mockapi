"""
Admin API — all routes are prefixed /admin and require the admin Bearer token.

Endpoints:
  POST   /admin/endpoints          create endpoint + upload its artifact in one step
  GET    /admin/endpoints          list endpoints
  PATCH  /admin/endpoints/{id}     update endpoint fields and/or replace its artifact
  DELETE /admin/endpoints/{id}     delete endpoint + its artifact file

  GET    /admin/auth/api-keys      list API keys (masked)
  POST   /admin/auth/api-keys      create API key
  DELETE /admin/auth/api-keys/{id} delete API key

  GET    /admin/auth/users         list basic-auth users
  POST   /admin/auth/users         create basic-auth user
  DELETE /admin/auth/users/{u}     delete basic-auth user

  GET    /admin/auth/jwt           show JWT config status
  POST   /admin/auth/jwt/config    set JWT secret
  POST   /admin/auth/jwt/token     generate a signed JWT
"""

import csv
import io
import json
import os
import defusedxml.ElementTree as ET
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import bcrypt
import jwt as pyjwt
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app import storage
from app.auth import _bearer_scheme, hash_api_key
from app.models import (
    APIKeyRecord,
    ArtifactRecord,
    AuthType,
    BasicUserRecord,
    EndpointRecord,
    HTTPMethod,
    JWTConfigRecord,
)

router = APIRouter(prefix="/admin", tags=["admin"])

_bearer = HTTPBearer(auto_error=True)


def _check_admin(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    admin_token = os.getenv("ADMIN_TOKEN", "changeme")
    # secrets.compare_digest runs in constant time regardless of where the
    # strings differ, unlike `!=`, which short-circuits on the first
    # mismatched byte and so leaks a timing signal an attacker could use to
    # guess the token character-by-character.
    if not secrets.compare_digest(credentials.credentials.encode(), admin_token.encode()):
        raise HTTPException(status_code=403, detail="Invalid admin token")


# ── Endpoints + artifact (combined, 1:1) ───────────────────────

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


async def _read_limited(file: UploadFile, max_bytes: int) -> bytes:
    """Read an upload in fixed-size chunks, rejecting it as soon as the
    running total exceeds max_bytes.

    Plain `await file.read()` buffers the entire body first and only lets
    you inspect its size afterwards — for an upload with no size limit at
    all, that's an easy memory/disk exhaustion DoS (send one huge file,
    repeat). Reading in chunks means we never hold more than a few KB past
    the limit before bailing out.
    """
    chunks = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds the maximum upload size of {max_bytes} bytes",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def validation_error(field: str, reason: str) -> HTTPException:
    """A 422 shaped the same way as app.main's RequestValidationError
    handler, so every validation failure — ours or FastAPI's own — comes
    back as `{"detail": {"errors": [{"field", "reason"}, ...]}}`."""
    return HTTPException(status_code=422, detail={"errors": [{"field": field, "reason": reason}]})


# Reserved so a mock endpoint can never be registered somewhere it could
# never actually be reached — /admin/* and /health are matched by routes
# registered ahead of the catch-all mock handler (see app/main.py).
_RESERVED_EXACT_PATHS = {"/admin", "/health"}
_RESERVED_PREFIXES = ("/admin/",)

MAX_CSV_ROWS = 10_000


def _validate_path(raw_path: str) -> str:
    path = raw_path if raw_path.startswith("/") else f"/{raw_path}"

    if any(c in path for c in "?#") or any(c.isspace() for c in path):
        raise validation_error(
            "path", "Path must be a bare URL path — no query string, fragment, or whitespace"
        )
    if path.strip("/") == "":
        raise validation_error("path", "Path must not be empty")
    if path in _RESERVED_EXACT_PATHS or path.startswith(_RESERVED_PREFIXES):
        raise validation_error(
            "path",
            f"{path!r} is reserved by the server itself (/admin/* and /health) and "
            "could never be reached by a mock endpoint",
        )
    return path


def _validate_csv(text: str) -> int:
    # text is already known non-empty (checked by the caller), so
    # DictReader always finds at least a header row here.
    reader = csv.DictReader(io.StringIO(text))

    row_count = 0
    for i, row in enumerate(reader, start=2):  # row 1 is the header
        # csv.DictReader fills missing trailing fields with None (restval)
        # and collects extra fields under a None key (restkey) — either
        # means this row doesn't have the same column count as the header.
        if None in row or None in row.values():
            raise validation_error(
                "file", f"Row {i} has a different number of columns than the header"
            )
        row_count += 1
        if row_count > MAX_CSV_ROWS:
            raise validation_error("file", f"CSV file exceeds the maximum of {MAX_CSV_ROWS} rows")

    return row_count


def _validate_json(text: str) -> Optional[int]:
    parsed = json.loads(text)  # may raise json.JSONDecodeError — caller wraps that

    if isinstance(parsed, list):
        if not all(isinstance(item, dict) for item in parsed):
            raise validation_error("file", "JSON array must contain only objects")
        return len(parsed)
    elif isinstance(parsed, dict):
        return None
    else:
        raise validation_error("file", "JSON file must be an object or an array of objects")


def _validate_xml(text: str) -> int:
    root = ET.fromstring(text)  # may raise — caller wraps that
    # Count direct children of the root — e.g. <users><user/><user/></users> → 2
    return len(list(root))


def _detect_format(filename: str) -> str:
    if filename.endswith(".csv"):
        return "csv"
    elif filename.endswith(".json"):
        return "json"
    elif filename.endswith(".xml"):
        return "xml"
    raise validation_error("file", "Only .csv, .json, and .xml files are supported")


def _decode_nonempty_text(content: bytes) -> str:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise validation_error("file", "File is not valid UTF-8 text")
    if not text.strip():
        raise validation_error("file", "File is empty")
    return text


def _validate_file_content(fmt: str, text: str) -> Optional[int]:
    try:
        if fmt == "csv":
            return _validate_csv(text)
        elif fmt == "json":
            return _validate_json(text)
        else:  # xml
            return _validate_xml(text)
    except HTTPException:
        raise
    except Exception as exc:
        raise validation_error("file", f"Could not parse file: {exc}")


async def _process_upload(file: UploadFile) -> ArtifactRecord:
    """Validate an uploaded file end to end and persist it, returning the
    new artifact record. Shared by create_endpoint and update_endpoint."""
    content = await _read_limited(file, MAX_UPLOAD_BYTES)
    original_name = file.filename or "upload"

    fmt = _detect_format(original_name)
    text = _decode_nonempty_text(content)
    row_count = _validate_file_content(fmt, text)

    artifact_id = str(uuid.uuid4())
    stored_filename = f"{artifact_id}{Path(original_name).suffix}"
    (storage.ARTIFACTS_DIR / stored_filename).write_bytes(content)

    return ArtifactRecord(
        id=artifact_id,
        name=original_name,
        filename=stored_filename,
        format=fmt,
        row_count=row_count,
    )


def _check_no_conflicting_endpoint(data, path: str, method: str, ignore_id: Optional[str] = None) -> None:
    for ep in data.endpoints.values():
        if ep.id == ignore_id:
            continue
        if ep.path == path and ep.method == method:
            raise HTTPException(
                status_code=409, detail=f"Endpoint {method} {path} already exists"
            )


@router.post("/endpoints", summary="Create a mock endpoint (uploads file atomically)")
async def create_endpoint(
    path: str = Form(..., description="URL path, e.g. /api/users"),
    method: HTTPMethod = Form(HTTPMethod.GET, description="HTTP method"),
    auth_type: AuthType = Form(AuthType.none),
    description: Optional[str] = Form(None),
    file: UploadFile = File(..., description="CSV, JSON, or XML artifact"),
    _: None = Depends(_check_admin),
):
    path = _validate_path(path)
    artifact = await _process_upload(file)

    _check_no_conflicting_endpoint(storage.get_data(), path, method.value)

    endpoint = EndpointRecord(
        path=path,
        method=method.value,
        artifact_id=artifact.id,
        auth_type=auth_type,
        description=description,
    )

    def _apply(d):
        d.artifacts[artifact.id] = artifact
        d.endpoints[endpoint.id] = endpoint

    storage.mutate(_apply)

    return {
        "endpoint": endpoint.model_dump(),
        "artifact": artifact.model_dump(),
    }


@router.get("/endpoints", summary="List all mock endpoints")
async def list_endpoints(_: None = Depends(_check_admin)):
    data = storage.get_data()
    result = []
    for ep in data.endpoints.values():
        artifact = data.artifacts.get(ep.artifact_id)
        result.append(
            {
                **ep.model_dump(),
                "artifact_name": artifact.name if artifact else None,
                "artifact_rows": artifact.row_count if artifact else None,
            }
        )
    return result


@router.patch("/endpoints/{endpoint_id}", summary="Update an existing endpoint")
async def update_endpoint(
    endpoint_id: str,
    path: Optional[str] = Form(None, description="New URL path, e.g. /api/users"),
    method: Optional[HTTPMethod] = Form(None, description="New HTTP method"),
    auth_type: Optional[AuthType] = Form(None),
    description: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None, description="Replacement CSV, JSON, or XML artifact"),
    _: None = Depends(_check_admin),
):
    """All fields are optional — only what's provided gets changed. Omit
    `file` to keep the existing artifact; provide one to replace it."""
    data = storage.get_data()
    endpoint = data.endpoints.get(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    new_path = _validate_path(path) if path is not None else endpoint.path
    new_method = method.value if method is not None else endpoint.method
    _check_no_conflicting_endpoint(data, new_path, new_method, ignore_id=endpoint_id)

    new_artifact = await _process_upload(file) if file is not None else None
    # Captured before mutate() runs — d.artifacts and data.artifacts are the
    # same dict (mutate operates on the process-wide storage in place), so
    # reading this *after* mutate would find it already deleted below.
    old_artifact = data.artifacts.get(endpoint.artifact_id) if new_artifact is not None else None

    def _apply(d):
        ep = d.endpoints[endpoint_id]
        ep.path = new_path
        ep.method = new_method
        if auth_type is not None:
            ep.auth_type = auth_type
        if description is not None:
            ep.description = description
        if new_artifact is not None:
            ep.artifact_id = new_artifact.id
            d.artifacts[new_artifact.id] = new_artifact
            d.artifacts.pop(old_artifact.id, None)

    storage.mutate(_apply)

    # Remove the replaced file from disk after the state change is committed.
    if old_artifact is not None:
        old_path = storage.ARTIFACTS_DIR / old_artifact.filename
        if old_path.exists():
            old_path.unlink()

    updated_artifact = new_artifact if new_artifact is not None else data.artifacts[endpoint.artifact_id]
    return {
        "endpoint": endpoint.model_dump(),
        "artifact": updated_artifact.model_dump(),
    }


@router.delete("/endpoints/{endpoint_id}", summary="Delete endpoint and its artifact")
async def delete_endpoint(endpoint_id: str, _: None = Depends(_check_admin)):
    data = storage.get_data()
    endpoint = data.endpoints.get(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    artifact = data.artifacts.get(endpoint.artifact_id)

    def _apply(d):
        del d.endpoints[endpoint_id]
        if endpoint.artifact_id in d.artifacts:
            del d.artifacts[endpoint.artifact_id]

    storage.mutate(_apply)

    # Remove file after mutation committed
    if artifact:
        file_path = storage.ARTIFACTS_DIR / artifact.filename
        if file_path.exists():
            file_path.unlink()

    return {"deleted_endpoint": endpoint_id, "deleted_artifact": endpoint.artifact_id}


# ── Auth: API Keys ─────────────────────────────────────────────

class _APIKeyCreate(BaseModel):
    name: str


@router.get("/auth/api-keys", summary="List API keys (keys are masked)")
async def list_api_keys(_: None = Depends(_check_admin)):
    # Only the prefix + creation metadata are returned — key_hash never
    # leaves the server, and there's no plaintext key left to show anyway.
    return [
        {
            "id": r.id,
            "name": r.name,
            "key": r.key_prefix + "…",
            "created_at": r.created_at,
        }
        for r in storage.get_data().api_keys.values()
    ]


@router.post("/auth/api-keys", summary="Create a new API key")
async def create_api_key(body: _APIKeyCreate, _: None = Depends(_check_admin)):
    key_value = secrets.token_urlsafe(32)
    record = APIKeyRecord(
        name=body.name,
        key_prefix=key_value[:8],
        key_hash=hash_api_key(key_value),
    )

    storage.mutate(lambda d: d.api_keys.update({record.id: record}))

    # The full key is only ever available here, at creation time — only
    # its hash is persisted, so this is the caller's one chance to save it.
    return {
        "id": record.id,
        "name": record.name,
        "created_at": record.created_at,
        "key": key_value,
        "_note": "Save this key — it won't be shown again",
    }


@router.delete("/auth/api-keys/{key_id}", summary="Delete an API key")
async def delete_api_key(key_id: str, _: None = Depends(_check_admin)):
    data = storage.get_data()
    if key_id not in data.api_keys:
        raise HTTPException(status_code=404, detail="API key not found")
    storage.mutate(lambda d: d.api_keys.pop(key_id))
    return {"deleted": key_id}


# ── Auth: Basic users ──────────────────────────────────────────

class _UserCreate(BaseModel):
    username: str
    password: str


@router.get("/auth/users", summary="List basic-auth users")
async def list_users(_: None = Depends(_check_admin)):
    return [
        {"username": u, "created_at": r.created_at}
        for u, r in storage.get_data().basic_users.items()
    ]


@router.post("/auth/users", summary="Create a basic-auth user")
async def create_user(body: _UserCreate, _: None = Depends(_check_admin)):
    data = storage.get_data()
    if body.username in data.basic_users:
        raise HTTPException(status_code=409, detail="Username already exists")

    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    record = BasicUserRecord(username=body.username, password_hash=pw_hash)

    storage.mutate(lambda d: d.basic_users.update({body.username: record}))
    return {"username": record.username, "created_at": record.created_at}


@router.delete("/auth/users/{username}", summary="Delete a basic-auth user")
async def delete_user(username: str, _: None = Depends(_check_admin)):
    data = storage.get_data()
    if username not in data.basic_users:
        raise HTTPException(status_code=404, detail="User not found")
    storage.mutate(lambda d: d.basic_users.pop(username))
    return {"deleted": username}


# ── Auth: JWT ──────────────────────────────────────────────────

class _JWTSecretSet(BaseModel):
    secret: Optional[str] = None   # auto-generate if omitted
    algorithm: str = "HS256"


class _JWTTokenCreate(BaseModel):
    subject: str = "mockapi-client"
    expires_in_seconds: int = 3600
    extra_claims: dict = {}


@router.get("/auth/jwt", summary="Show JWT config status")
async def get_jwt_status(_: None = Depends(_check_admin)):
    cfg = storage.get_data().jwt_config
    if not cfg:
        return {"configured": False}
    return {"configured": True, "algorithm": cfg.algorithm}


@router.post("/auth/jwt/config", summary="Set the JWT signing secret")
async def set_jwt_config(body: _JWTSecretSet, _: None = Depends(_check_admin)):
    secret = body.secret or secrets.token_urlsafe(32)
    record = JWTConfigRecord(secret=secret, algorithm=body.algorithm)
    storage.mutate(lambda d: setattr(d, "jwt_config", record))
    return {
        "algorithm": record.algorithm,
        "secret": secret,
        "_note": "Save this secret — it's needed to verify tokens",
    }


@router.post("/auth/jwt/token", summary="Generate a signed JWT")
async def generate_token(body: _JWTTokenCreate, _: None = Depends(_check_admin)):
    data = storage.get_data()
    if not data.jwt_config:
        raise HTTPException(
            status_code=400,
            detail="JWT not configured. POST /admin/auth/jwt/config first.",
        )

    now = datetime.now(timezone.utc)
    payload = {
        "sub": body.subject,
        "iat": now,
        "exp": now + timedelta(seconds=body.expires_in_seconds),
        **body.extra_claims,
    }
    token = pyjwt.encode(
        payload,
        data.jwt_config.secret,
        algorithm=data.jwt_config.algorithm,
    )
    return {
        "token": token,
        "expires_in_seconds": body.expires_in_seconds,
        "subject": body.subject,
    }
