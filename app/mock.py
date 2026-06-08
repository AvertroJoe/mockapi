"""
Mock request handler — serves the data for registered endpoints.
Called by the catch-all route in main.py.

Response format mirrors the source file:
  CSV  → application/json  (list of objects, one per row)
  JSON → application/json
  XML  → application/xml   (the file is returned as-is)
"""

import csv
import io
import json

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response

from app.auth import enforce_auth
from app.storage import ARTIFACTS_DIR, get_data


def _build_response(artifact_id: str) -> Response:
    data = get_data()
    artifact = data.artifacts.get(artifact_id)
    if not artifact:
        raise HTTPException(status_code=500, detail="Artifact record missing — server misconfigured")

    file_path = ARTIFACTS_DIR / artifact.filename
    if not file_path.exists():
        raise HTTPException(status_code=500, detail="Artifact file missing from disk")

    text = file_path.read_text(encoding="utf-8")

    if artifact.format == "json":
        return JSONResponse(content=json.loads(text))

    elif artifact.format == "csv":
        rows = list(csv.DictReader(io.StringIO(text)))
        return JSONResponse(content=rows)

    elif artifact.format == "xml":
        return Response(content=text, media_type="application/xml")

    else:
        raise HTTPException(status_code=500, detail=f"Unknown artifact format: {artifact.format!r}")


async def handle_mock_request(path: str, request: Request) -> Response:
    norm_path = f"/{path}" if not path.startswith("/") else path

    data = get_data()
    endpoint = None
    for ep in data.endpoints.values():
        if ep.path == norm_path and ep.method.upper() == request.method.upper():
            endpoint = ep
            break

    if not endpoint:
        raise HTTPException(
            status_code=404,
            detail=f"No mock endpoint registered for {request.method} {norm_path}",
        )

    await enforce_auth(request, endpoint.auth_type)

    return _build_response(endpoint.artifact_id)
