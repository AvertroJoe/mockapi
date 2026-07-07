#!/usr/bin/env python3
"""
mockapi CLI — manage a running MockAPI server.

Configuration (env vars or .env file):
  MOCKAPI_URL          Base URL of the server  (default: http://localhost:8000)
  MOCKAPI_ADMIN_TOKEN  Admin Bearer token       (default: changeme)

Usage examples:
  mockapi endpoint create --path /api/users --file users.csv --auth api_key
  mockapi endpoint create --root /api/Defender --name "Vulnerability scanning" --file scan.csv
  mockapi endpoint list
  mockapi endpoint delete <id>

  mockapi auth api-key create my-client
  mockapi auth user create --username alice
  mockapi auth jwt config
  mockapi auth jwt token --subject my-service --expires 7200
"""

import os
import sys
from pathlib import Path
from typing import Optional

import httpx
import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from cli.slug import deslugify, group_endpoints, last_segment, slugify

load_dotenv()

console = Console()

# ── Root app ───────────────────────────────────────────────────

app = typer.Typer(
    name="mockapi",
    help="Manage a MockAPI server.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)

endpoint_app = typer.Typer(help="Manage mock endpoints.", no_args_is_help=True)
auth_app = typer.Typer(help="Manage authentication credentials.", no_args_is_help=True)
api_key_app = typer.Typer(help="Manage API keys.", no_args_is_help=True)
user_app = typer.Typer(help="Manage basic-auth users.", no_args_is_help=True)
jwt_app = typer.Typer(help="Manage JWT configuration.", no_args_is_help=True)

app.add_typer(endpoint_app, name="endpoint")
app.add_typer(auth_app, name="auth")
auth_app.add_typer(api_key_app, name="api-key")
auth_app.add_typer(user_app, name="user")
auth_app.add_typer(jwt_app, name="jwt")


# ── HTTP client helpers ────────────────────────────────────────

def _client() -> httpx.Client:
    base_url = os.getenv("MOCKAPI_URL", "http://localhost:8000")
    token = os.getenv("MOCKAPI_ADMIN_TOKEN", "changeme")
    return httpx.Client(
        base_url=base_url.rstrip("/"),
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )


def _ok(resp: httpx.Response) -> dict:
    """Return parsed JSON or print error and exit."""
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text

        # Validation errors come back as {"errors": [{"field", "reason"}, ...]}
        # — render each on its own line instead of a raw dict repr.
        if isinstance(detail, dict) and isinstance(detail.get("errors"), list):
            console.print(f"[bold red]Error {resp.status_code}:[/bold red]")
            for err in detail["errors"]:
                console.print(f"  [yellow]{err.get('field', '?')}[/yellow]: {err.get('reason', err)}")
        else:
            console.print(f"[bold red]Error {resp.status_code}:[/bold red] {detail}")
        raise typer.Exit(1)
    return resp.json()


# ── Health ─────────────────────────────────────────────────────

@app.command("ping")
def ping():
    """Check the server is reachable."""
    with _client() as c:
        try:
            resp = c.get("/health")
            data = _ok(resp)
            console.print(f"[green]Server is up.[/green] Status: {data.get('status')}")
        except httpx.ConnectError:
            console.print("[red]Cannot connect to server.[/red] Is MOCKAPI_URL correct?")
            raise typer.Exit(1)


# ── Endpoints ──────────────────────────────────────────────────

@endpoint_app.command("create")
def endpoint_create(
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Full URL path, e.g. /api/users"),
    root: Optional[str] = typer.Option(
        None,
        "--root",
        "-r",
        help="Existing or new root path to nest under, e.g. /api/Defender (alternative to --path)",
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        "-n",
        help="Endpoint name under --root, e.g. 'Vulnerability scanning' — auto-slugified",
    ),
    file: Path = typer.Option(..., "--file", "-f", help="CSV or JSON file to serve"),
    method: str = typer.Option("GET", "--method", "-m", help="HTTP method"),
    auth: str = typer.Option(
        "none",
        "--auth",
        "-a",
        help="Auth type: none | api_key | basic | jwt",
    ),
    description: Optional[str] = typer.Option(None, "--desc", "-d", help="Description"),
):
    """Create a mock endpoint and upload its data file (one step).

    Either pass the full --path directly, or build it from --root plus
    --name — e.g. `--root /api/Defender --name "Vulnerability scanning"`
    registers /api/Defender/vulnerability-scanning without hand-typing or
    slugifying it yourself. --root alone (no --name) creates the root
    itself, so it can later show up as the head of a group.
    """
    if path and root:
        console.print("[red]Use either --path or --root/--name, not both.[/red]")
        raise typer.Exit(1)
    if not path and not root:
        console.print("[red]Provide either --path or --root.[/red]")
        raise typer.Exit(1)
    if name and not root:
        console.print("[red]--name only makes sense together with --root.[/red]")
        raise typer.Exit(1)

    if path is None:
        path = root if root.startswith("/") else f"/{root}"
        if name:
            path = f"{path.rstrip('/')}/{slugify(name)}"

    if not file.exists():
        console.print(f"[red]File not found:[/red] {file}")
        raise typer.Exit(1)

    with _client() as c, open(file, "rb") as fh:
        fields: dict = {
            "path": path,
            "method": method.upper(),
            "auth_type": auth,
        }
        if description:
            fields["description"] = description

        resp = c.post(
            "/admin/endpoints",
            data=fields,
            files={"file": (file.name, fh, "application/octet-stream")},
        )

    result = _ok(resp)
    ep = result["endpoint"]
    art = result["artifact"]

    console.print(f"[green]Endpoint created:[/green] {ep['method']} {ep['path']}")
    console.print(f"  ID:       {ep['id']}")
    console.print(f"  Auth:     {ep['auth_type']}")
    console.print(f"  File:     {art['name']}  ({art['format'].upper()}, {art.get('row_count') or '?'} rows)")
    base = os.getenv("MOCKAPI_URL", "http://localhost:8000").rstrip("/")
    console.print(f"  Mock URL: [cyan]{base}{ep['path']}[/cyan]")


@endpoint_app.command("list")
def endpoint_list():
    """List all registered mock endpoints.

    Endpoints nested one level under another endpoint's exact path (e.g.
    created via `endpoint create --root`) are shown grouped: the root
    first, its children indented beneath it.
    """
    with _client() as c:
        items = _ok(c.get("/admin/endpoints"))

    if not items:
        console.print("[yellow]No endpoints registered.[/yellow]")
        return

    table = Table(title="Mock Endpoints", show_lines=True)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Method", style="cyan")
    table.add_column("Path", style="green", no_wrap=True)
    table.add_column("Auth")
    table.add_column("File")
    table.add_column("Rows", justify="right")
    table.add_column("Description")

    def add_row(ep: dict, path_display: str) -> None:
        table.add_row(
            ep["id"][:8] + "…",
            ep["method"],
            path_display,
            ep["auth_type"],
            ep.get("artifact_name") or "-",
            str(ep.get("artifact_rows") or "-"),
            ep.get("description") or "",
        )

    groups, ungrouped = group_endpoints(items)

    for group in groups:
        add_row(group.root, f"[bold]{group.root['path']}[/bold]")
        for child in group.children:
            add_row(child, f"  └─ {child['path']}")

    for ep in ungrouped:
        add_row(ep, ep["path"])

    console.print(table)


@endpoint_app.command("update")
def endpoint_update(
    endpoint_id: str = typer.Argument(..., help="Full endpoint ID (from list)"),
    path: Optional[str] = typer.Option(None, "--path", "-p", help="New URL path"),
    method: Optional[str] = typer.Option(None, "--method", "-m", help="New HTTP method"),
    auth: Optional[str] = typer.Option(None, "--auth", "-a", help="New auth type: none | api_key | basic | jwt"),
    description: Optional[str] = typer.Option(None, "--desc", "-d", help="New description"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Replacement CSV, JSON, or XML file"),
):
    """Update an existing endpoint. Only the fields you pass are changed."""
    if file is not None and not file.exists():
        console.print(f"[red]File not found:[/red] {file}")
        raise typer.Exit(1)

    fields: dict = {}
    if path is not None:
        fields["path"] = path
    if method is not None:
        fields["method"] = method.upper()
    if auth is not None:
        fields["auth_type"] = auth
    if description is not None:
        fields["description"] = description

    if not fields and file is None:
        console.print("[yellow]Nothing to update — pass at least one field to change.[/yellow]")
        raise typer.Exit(1)

    with _client() as c:
        if file is not None:
            with open(file, "rb") as fh:
                resp = c.patch(
                    f"/admin/endpoints/{endpoint_id}",
                    data=fields,
                    files={"file": (file.name, fh, "application/octet-stream")},
                )
        else:
            resp = c.patch(f"/admin/endpoints/{endpoint_id}", data=fields)

    result = _ok(resp)
    ep = result["endpoint"]
    art = result["artifact"]

    console.print(f"[green]Endpoint updated:[/green] {ep['method']} {ep['path']}")
    console.print(f"  Auth:     {ep['auth_type']}")
    console.print(f"  File:     {art['name']}  ({art['format'].upper()}, {art.get('row_count') or '?'} rows)")


@endpoint_app.command("delete")
def endpoint_delete(
    endpoint_id: str = typer.Argument(..., help="Full endpoint ID (from list)"),
):
    """Delete an endpoint and its associated data file."""
    typer.confirm(f"Delete endpoint {endpoint_id} and its data file?", abort=True)
    with _client() as c:
        result = _ok(c.delete(f"/admin/endpoints/{endpoint_id}"))
    console.print(f"[green]Deleted:[/green] endpoint {result['deleted_endpoint']}, artifact {result['deleted_artifact']}")


# ── Auth: API keys ─────────────────────────────────────────────

@api_key_app.command("create")
def api_key_create(name: str = typer.Argument(..., help="Label for this key")):
    """Generate a new API key."""
    with _client() as c:
        result = _ok(c.post("/admin/auth/api-keys", json={"name": name}))

    console.print(f"[green]API key created.[/green]  ID: {result['id']}")
    console.print(f"  Name: {result['name']}")
    console.print(f"[bold yellow]  Key (save this — shown once):[/bold yellow]")
    console.print(f"  [bold]{result['key']}[/bold]")


@api_key_app.command("list")
def api_key_list():
    """List API keys (keys are masked)."""
    with _client() as c:
        items = _ok(c.get("/admin/auth/api-keys"))

    if not items:
        console.print("[yellow]No API keys.[/yellow]")
        return

    table = Table(title="API Keys")
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("Key (masked)")
    table.add_column("Created")
    for item in items:
        table.add_row(item["id"][:8] + "…", item["name"], item["key"], item["created_at"][:19])
    console.print(table)


@api_key_app.command("delete")
def api_key_delete(key_id: str = typer.Argument(..., help="Key ID")):
    """Delete an API key."""
    with _client() as c:
        _ok(c.delete(f"/admin/auth/api-keys/{key_id}"))
    console.print(f"[green]Deleted API key:[/green] {key_id}")


# ── Auth: Basic users ──────────────────────────────────────────

@user_app.command("create")
def user_create(
    username: str = typer.Option(..., "--username", "-u"),
    password: str = typer.Option(
        ..., "--password", "-p", prompt=True, hide_input=True, confirmation_prompt=True
    ),
):
    """Create a basic-auth user."""
    with _client() as c:
        result = _ok(c.post("/admin/auth/users", json={"username": username, "password": password}))
    console.print(f"[green]User created:[/green] {result['username']}")


@user_app.command("list")
def user_list():
    """List basic-auth users."""
    with _client() as c:
        items = _ok(c.get("/admin/auth/users"))

    if not items:
        console.print("[yellow]No users.[/yellow]")
        return

    table = Table(title="Basic Auth Users")
    table.add_column("Username")
    table.add_column("Created")
    for item in items:
        table.add_row(item["username"], item["created_at"][:19])
    console.print(table)


@user_app.command("delete")
def user_delete(username: str = typer.Argument(...)):
    """Delete a basic-auth user."""
    with _client() as c:
        _ok(c.delete(f"/admin/auth/users/{username}"))
    console.print(f"[green]Deleted user:[/green] {username}")


# ── Auth: JWT ──────────────────────────────────────────────────

@jwt_app.command("config")
def jwt_config(
    secret: Optional[str] = typer.Option(
        None, "--secret", help="Signing secret (auto-generated if omitted)"
    ),
    algorithm: str = typer.Option("HS256", "--algorithm"),
):
    """Set or rotate the JWT signing secret."""
    body: dict = {"algorithm": algorithm}
    if secret:
        body["secret"] = secret

    with _client() as c:
        result = _ok(c.post("/admin/auth/jwt/config", json=body))

    console.print(f"[green]JWT configured.[/green]  Algorithm: {result['algorithm']}")
    console.print(f"[bold yellow]  Secret (save this):[/bold yellow] {result['secret']}")


@jwt_app.command("status")
def jwt_status():
    """Show whether JWT is configured."""
    with _client() as c:
        result = _ok(c.get("/admin/auth/jwt"))
    if result.get("configured"):
        console.print(f"[green]JWT is configured.[/green]  Algorithm: {result['algorithm']}")
    else:
        console.print("[yellow]JWT is not configured.[/yellow]  Run: mockapi auth jwt config")


@jwt_app.command("token")
def jwt_token(
    subject: str = typer.Option("mockapi-client", "--subject", "-s", help="Token subject (sub claim)"),
    expires: int = typer.Option(3600, "--expires", "-e", help="Expiry in seconds"),
):
    """Generate a signed JWT for use against JWT-protected endpoints."""
    with _client() as c:
        result = _ok(
            c.post(
                "/admin/auth/jwt/token",
                json={"subject": subject, "expires_in_seconds": expires},
            )
        )
    console.print(f"[green]Token (expires in {result['expires_in_seconds']}s):[/green]")
    console.print(f"[bold]{result['token']}[/bold]")


if __name__ == "__main__":
    app()
