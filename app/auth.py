"""
Authentication helpers used by both admin routes (admin token check)
and mock route handlers (per-endpoint auth checks).
"""

import base64

import bcrypt
import jwt as pyjwt
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models import AuthType
from app.storage import get_data

# ── Admin auth ─────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=True)


def require_admin(credentials: HTTPAuthorizationCredentials = None):
    """FastAPI dependency: validates the admin Bearer token."""
    import os
    admin_token = os.getenv("ADMIN_TOKEN", "changeme")
    if credentials is None or credentials.credentials != admin_token:
        raise HTTPException(status_code=403, detail="Invalid or missing admin token")
    return credentials


# ── Mock-endpoint auth ─────────────────────────────────────────

async def enforce_auth(request: Request, auth_type: AuthType) -> None:
    """
    Called before serving a mock response.
    Raises HTTPException on any auth failure.
    """
    if auth_type == AuthType.none:
        return

    data = get_data()

    if auth_type == AuthType.api_key:
        key = (
            request.headers.get("X-API-Key")
            or request.query_params.get("api_key")
        )
        if not key:
            raise HTTPException(
                status_code=401,
                headers={"WWW-Authenticate": "ApiKey"},
                detail="API key required — pass X-API-Key header or ?api_key= query param",
            )
        valid = {rec.key for rec in data.api_keys.values()}
        if key not in valid:
            raise HTTPException(status_code=403, detail="Invalid API key")

    elif auth_type == AuthType.basic:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Basic "):
            raise HTTPException(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="MockAPI"'},
                detail="Basic authentication required",
            )
        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            username, password = decoded.split(":", 1)
        except Exception:
            raise HTTPException(status_code=400, detail="Malformed Basic auth header")

        user = data.basic_users.get(username)
        if not user or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            raise HTTPException(status_code=403, detail="Invalid credentials")

    elif auth_type == AuthType.jwt:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
                detail="Bearer JWT required",
            )
        token = auth_header[7:]

        if not data.jwt_config:
            raise HTTPException(
                status_code=500,
                detail="JWT auth is not configured on this server",
            )
        try:
            pyjwt.decode(
                token,
                data.jwt_config.secret,
                algorithms=[data.jwt_config.algorithm],
            )
        except pyjwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except pyjwt.InvalidTokenError as exc:
            raise HTTPException(status_code=403, detail=f"Invalid token: {exc}")
