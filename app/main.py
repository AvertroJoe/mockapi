import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.admin import router as admin_router
from app.mock import handle_mock_request
from app.storage import init_storage

UI_DIST = Path(__file__).resolve().parent.parent / "ui" / "dist"

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


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Reshape FastAPI's built-in validation errors to match the shape our
    own manual validation raises (see app.admin.validation_error) — one
    consistent {"errors": [{"field", "reason"}, ...]} body for every 422,
    whether it came from a Pydantic/Form type check or our own checks.
    """
    errors = [
        {
            # loc is a tuple like ("body", "method") or ("form", "path");
            # drop the first segment (the request location, not a field name).
            "field": ".".join(str(p) for p in err["loc"][1:]) or str(err["loc"][-1]),
            "reason": err["msg"],
        }
        for err in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": {"errors": errors}})


# Admin routes registered BEFORE the catch-all so they take priority.
app.include_router(admin_router)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}


# Web UI, if it's been built (ui/dist exists — see the Dockerfile's frontend
# build stage). Registered ahead of the catch-all, same as /admin and
# /health, so it isn't shadowed by the mock handler.
if UI_DIST.exists():
    app.mount("/ui/assets", StaticFiles(directory=UI_DIST / "assets"), name="ui-assets")

    @app.get("/ui", include_in_schema=False)
    @app.get("/ui/{full_path:path}", include_in_schema=False)
    async def serve_ui(full_path: str = "") -> FileResponse:
        # A single-page app: any /ui/* path that isn't a real asset file is
        # a client-side route (e.g. /ui/connectors/new) — always hand back
        # index.html and let React Router take it from there.
        return FileResponse(UI_DIST / "index.html")


# Catch-all: everything that isn't /admin/*, /health, or /ui/* is a potential mock endpoint.
@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    include_in_schema=False,
)
async def mock_catch_all(path: str, request: Request) -> JSONResponse:
    return await handle_mock_request(path, request)
