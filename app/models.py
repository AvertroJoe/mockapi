from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Enums ──────────────────────────────────────────────────────

class AuthType(str, Enum):
    none = "none"
    api_key = "api_key"
    basic = "basic"
    jwt = "jwt"


class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


# ── Records ────────────────────────────────────────────────────

class ArtifactRecord(BaseModel):
    id: str = Field(default_factory=_uuid)
    name: str
    filename: str          # stored filename inside artifacts dir (uuid-based)
    format: str            # "csv" or "json"
    row_count: Optional[int] = None
    created_at: str = Field(default_factory=_now)


class EndpointRecord(BaseModel):
    id: str = Field(default_factory=_uuid)
    path: str              # e.g. "/api/users" — always starts with /
    method: str = "GET"
    artifact_id: str
    auth_type: AuthType = AuthType.none
    description: Optional[str] = None
    created_at: str = Field(default_factory=_now)


class APIKeyRecord(BaseModel):
    id: str = Field(default_factory=_uuid)
    name: str
    key_prefix: str        # first 8 chars of the plaintext key — safe to display, aids identification
    key_hash: str           # sha256 hex digest of the full key — the plaintext key is never stored
    created_at: str = Field(default_factory=_now)


class BasicUserRecord(BaseModel):
    username: str
    password_hash: str     # bcrypt hash
    created_at: str = Field(default_factory=_now)


class JWTConfigRecord(BaseModel):
    secret: str
    algorithm: str = "HS256"


# ── Root data container ────────────────────────────────────────

class AppData(BaseModel):
    # Keyed by ID for O(1) lookup; artifacts also keyed by ID
    artifacts: dict[str, ArtifactRecord] = {}
    endpoints: dict[str, EndpointRecord] = {}
    api_keys: dict[str, APIKeyRecord] = {}
    basic_users: dict[str, BasicUserRecord] = {}
    jwt_config: Optional[JWTConfigRecord] = None
