import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.admin import router as admin_router
from app.mock import handle_mock_request
from app.storage import init_storage

_INSECURE_DEFAULT_TOKEN = "changeme"


def _require_real_admin_token() -> None:
    """Refuse to boot with no admin token, or the well-known default.

    Every /admin/* route is protected by comparing against ADMIN_TOKEN, so
    an unset or default token means the whole admin API — and therefore
    every mock endpoint it can create — is unprotected. Failing fast here
    turns a silent misconfiguration into a startup error you can't miss.
    """
    token = os.getenv("ADMIN_TOKEN")
    if not token or token == _INSECURE_DEFAULT_TOKEN:
        raise RuntimeError(
            "ADMIN_TOKEN is not set (or is left as the insecure default "
            f"{_INSECURE_DEFAULT_TOKEN!r}). Set a real secret via the ADMIN_TOKEN "
            "environment variable before starting the server."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _require_real_admin_token()
    init_storage()
    yield


app = FastAPI(
    title="MockAPI",
    description=(
        "API mocking tool. Upload CSV/JSON files, register them as HTTP endpoints, "
        "and configure per-endpoint authentication."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Admin routes registered BEFORE the catch-all so they take priority.
app.include_router(admin_router)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}


# Catch-all: everything that isn't /admin/* or /health is a potential mock endpoint.
@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    include_in_schema=False,
)
async def mock_catch_all(path: str, request: Request) -> JSONResponse:
    return await handle_mock_request(path, request)
