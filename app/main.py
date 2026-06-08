from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.admin import router as admin_router
from app.mock import handle_mock_request
from app.storage import init_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
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
