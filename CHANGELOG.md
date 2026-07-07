# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Versions before 2.4.0 were tagged retroactively against the commit history —
dates reflect when each change actually merged, not when this file was
introduced. Version bumps follow: **MAJOR** for changes that break an
existing deployment's upgrade path (a config that used to work no longer
does, without manual intervention) or the admin API's contract; **MINOR**
for new, backwards-compatible capability — including tooling/process
improvements with no runtime effect, since they're still a real addition to
the project; **PATCH** for fixes with no new capability.

## [Unreleased]

## [2.4.0] - 2026-07-07

### Added

- `mockapi endpoint create --root/--name` builds and slugifies a path for
  you (e.g. `--root /api/Defender --name "Vulnerability scanning"` →
  `/api/Defender/vulnerability-scanning`) instead of hand-typing it —
  `--path` still works exactly as before.
- The web UI's Build New form has the same Root + Endpoint name builder,
  with autocomplete over existing endpoint paths and a live preview of the
  path it will register.
- `mockapi endpoint list` and the UI's Connectors page now visually group
  an endpoint with others nested one level beneath it, when the shared
  parent path is itself a real, existing endpoint.

## [2.3.0] - 2026-07-06

### Added

- Web UI (React + Vite + TypeScript), served at `/ui` by the same
  container: Home (server overview and address), Connectors (list, edit,
  delete), and Build New — a full alternative to the CLI against the same
  admin API.
- Multi-stage Dockerfile: compiles the UI in a Node build stage and serves
  the static output from the existing Python image.

## [2.2.0] - 2026-07-06

### Added

- `PATCH /admin/endpoints/{id}` and `mockapi endpoint update` — update an
  existing endpoint's path, method, auth type, description, and/or
  replace its data file in place, without deleting and recreating it.

## [2.1.0] - 2026-07-01

### Added

- Structured, consistent `422` validation errors
  (`{"detail": {"errors": [{"field", "reason"}]}}`) for both hand-written
  checks and FastAPI's own request validation.
- CSV validation: rejects empty files, rows with a different column count
  than the header, and files over 10,000 rows.
- JSON validation: the top level must be an object or an array of objects
  — bare scalars and arrays of non-objects are rejected.
- `path` validation: rejects embedded query strings, fragments, or
  whitespace, and collisions with the reserved `/admin/*` and `/health`
  paths (which would otherwise be silently unreachable).
- `method` is now a real enum (`GET`/`POST`/`PUT`/`PATCH`/`DELETE`/`HEAD`/`OPTIONS`)
  instead of an unvalidated string.

### Changed

- Malformed-upload and unsupported-file-type errors now return `422`
  instead of `400` (the request was well-formed; the payload wasn't).

## [2.0.0] - 2026-07-01

### Security

- Admin-token comparison now uses `secrets.compare_digest` instead of
  `!=`, closing a timing side-channel that could leak how many leading
  characters of a guessed token were correct.
- **Breaking:** the server now refuses to start if `ADMIN_TOKEN` is unset
  or left as the `changeme` default, instead of silently accepting it.
  Deployments relying on the implicit default will no longer boot until a
  real token is set.
- **Breaking:** API keys are now stored as a salted hash, not plaintext.
  Any API key created before this version stops validating and must be
  regenerated.
- XML uploads are parsed with `defusedxml` instead of stdlib
  `ElementTree`, closing an entity-expansion ("billion laughs") DoS — a
  small crafted upload could previously expand to megabytes in memory.
- Uploads are capped at 5MB and read in bounded chunks, rather than
  buffering an unbounded body before checking its size.
- **Breaking:** the container now runs as a non-root user (UID/GID `999`)
  instead of root. Existing deployments need a one-time
  `chown -R 999:999` of the `mockapi_data` volume — documented in the
  README.

### Removed

- A dead, unfixed duplicate admin-token check in `app/auth.py`
  (`require_admin`, unused — the live check is `app/admin.py`'s
  `_check_admin`).

## [1.1.0] - 2026-07-01

### Added

- Full pytest suite covering the server, CLI, and storage layer.
- GitHub Actions CI, running the suite on Python 3.11 and 3.12 on every
  push and pull request.
- `.gitignore`; removed `__pycache__` files that had been committed.

## [1.0.0] - 2026-06-08

### Added

- Initial release: a FastAPI mock server plus a Typer CLI. Upload a CSV,
  JSON, or XML file and register it as an HTTP mock endpoint. Per-endpoint
  authentication: none, API key, Basic, or JWT. Single JSON-file storage.
  Deploys as one Docker container.
