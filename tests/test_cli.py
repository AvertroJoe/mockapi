import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

import cli.main as cli_main
from app.main import app as fastapi_app

runner = CliRunner()


@pytest.fixture
def cli_env(data_dir, admin_token, monkeypatch):
    """Point the CLI's HTTP client at the real app in-process.

    TestClient wraps its own transport that runs the ASGI app synchronously
    via a blocking portal, which is what cli.main's `with _client() as c:`
    pattern needs (plain httpx.ASGITransport only supports async).
    """

    def _fake_client():
        return TestClient(fastapi_app, headers={"Authorization": f"Bearer {admin_token}"})

    monkeypatch.setattr(cli_main, "_client", _fake_client)
    monkeypatch.setenv("MOCKAPI_URL", "http://testserver")
    return _fake_client


def test_ping(cli_env):
    result = runner.invoke(cli_main.app, ["ping"])
    assert result.exit_code == 0
    assert "Server is up" in result.stdout


def test_endpoint_create_and_list(cli_env, tmp_path):
    csv_file = tmp_path / "users.csv"
    csv_file.write_text("id,name\n1,Alice\n2,Bob\n")

    created = runner.invoke(
        cli_main.app,
        ["endpoint", "create", "--path", "/api/users", "--file", str(csv_file)],
    )
    assert created.exit_code == 0, created.stdout
    assert "Endpoint created" in created.stdout
    assert "/api/users" in created.stdout

    listed = runner.invoke(cli_main.app, ["endpoint", "list"])
    assert listed.exit_code == 0
    assert "/api/users" in listed.stdout
    assert "users.csv" in listed.stdout


def test_endpoint_create_with_root_and_name_slugifies_path(cli_env, tmp_path):
    csv_file = tmp_path / "scan.csv"
    csv_file.write_text("id,severity\n1,high\n")

    result = runner.invoke(
        cli_main.app,
        [
            "endpoint", "create",
            "--root", "/api/Defender",
            "--name", "Vulnerability scanning",
            "--file", str(csv_file),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "/api/Defender/vulnerability-scanning" in result.stdout


def test_endpoint_create_with_root_only_creates_the_root_itself(cli_env, tmp_path):
    csv_file = tmp_path / "root.csv"
    csv_file.write_text("id\n1\n")

    result = runner.invoke(
        cli_main.app,
        ["endpoint", "create", "--root", "/api/Defender", "--file", str(csv_file)],
    )
    assert result.exit_code == 0, result.stdout
    assert "/api/Defender" in result.stdout


def test_endpoint_create_rejects_path_and_root_together(cli_env, tmp_path):
    csv_file = tmp_path / "x.csv"
    csv_file.write_text("id\n1\n")

    result = runner.invoke(
        cli_main.app,
        ["endpoint", "create", "--path", "/api/x", "--root", "/api/y", "--file", str(csv_file)],
    )
    assert result.exit_code != 0
    assert "not both" in result.stdout


def test_endpoint_create_rejects_neither_path_nor_root(cli_env, tmp_path):
    csv_file = tmp_path / "x.csv"
    csv_file.write_text("id\n1\n")

    result = runner.invoke(cli_main.app, ["endpoint", "create", "--file", str(csv_file)])
    assert result.exit_code != 0
    assert "Provide either" in result.stdout


def test_endpoint_create_rejects_name_without_root(cli_env, tmp_path):
    csv_file = tmp_path / "x.csv"
    csv_file.write_text("id\n1\n")

    result = runner.invoke(
        cli_main.app,
        ["endpoint", "create", "--path", "/api/x", "--name", "Something", "--file", str(csv_file)],
    )
    assert result.exit_code != 0
    assert "--name only makes sense" in result.stdout


def test_endpoint_create_shows_structured_validation_error(cli_env, tmp_path):
    csv_file = tmp_path / "users.csv"
    csv_file.write_text("id,name\n1,Alice\n")

    result = runner.invoke(
        cli_main.app,
        ["endpoint", "create", "--path", "/health", "--file", str(csv_file)],
    )
    assert result.exit_code != 0
    assert "path" in result.stdout
    assert "reserved" in result.stdout


def test_endpoint_create_missing_file_errors(cli_env, tmp_path):
    missing = tmp_path / "does-not-exist.csv"
    result = runner.invoke(cli_main.app, ["endpoint", "create", "--path", "/api/x", "--file", str(missing)])
    assert result.exit_code != 0
    assert "File not found" in result.stdout


def test_endpoint_update(cli_env, tmp_path):
    csv_file = tmp_path / "users.csv"
    csv_file.write_text("id,name\n1,Alice\n")
    created = runner.invoke(cli_main.app, ["endpoint", "create", "--path", "/api/users", "--file", str(csv_file)])
    id_line = next(line for line in created.stdout.splitlines() if line.strip().startswith("ID:"))
    endpoint_id = id_line.split("ID:")[1].strip()

    result = runner.invoke(cli_main.app, ["endpoint", "update", endpoint_id, "--desc", "updated description"])
    assert result.exit_code == 0, result.stdout
    assert "Endpoint updated" in result.stdout


def test_endpoint_update_with_no_fields_errors(cli_env, tmp_path):
    csv_file = tmp_path / "users.csv"
    csv_file.write_text("id,name\n1,Alice\n")
    created = runner.invoke(cli_main.app, ["endpoint", "create", "--path", "/api/users", "--file", str(csv_file)])
    id_line = next(line for line in created.stdout.splitlines() if line.strip().startswith("ID:"))
    endpoint_id = id_line.split("ID:")[1].strip()

    result = runner.invoke(cli_main.app, ["endpoint", "update", endpoint_id])
    assert result.exit_code != 0
    assert "Nothing to update" in result.stdout


def test_endpoint_list_empty(cli_env):
    result = runner.invoke(cli_main.app, ["endpoint", "list"])
    assert result.exit_code == 0
    assert "No endpoints registered" in result.stdout


def test_endpoint_list_shows_grouped_root_and_children(cli_env, tmp_path):
    root_file = tmp_path / "root.csv"
    root_file.write_text("id\n1\n")
    child_file = tmp_path / "child.csv"
    child_file.write_text("id\n1\n")
    other_file = tmp_path / "other.csv"
    other_file.write_text("id\n1\n")

    runner.invoke(cli_main.app, ["endpoint", "create", "--root", "/api/Defender", "--file", str(root_file)])
    runner.invoke(
        cli_main.app,
        ["endpoint", "create", "--root", "/api/Defender", "--name", "NIST", "--file", str(child_file)],
    )
    runner.invoke(cli_main.app, ["endpoint", "create", "--path", "/api/users", "--file", str(other_file)])

    result = runner.invoke(cli_main.app, ["endpoint", "list"], color=False)
    assert result.exit_code == 0
    assert "/api/Defender" in result.stdout
    assert "└─ /api/Defender/nist" in result.stdout
    assert "/api/users" in result.stdout
    # The grouped child line should appear after its root, not before.
    assert result.stdout.index("/api/Defender ") < result.stdout.index("└─ /api/Defender/nist")


def test_endpoint_delete_with_confirmation(cli_env, tmp_path):
    csv_file = tmp_path / "users.csv"
    csv_file.write_text("id,name\n1,Alice\n")
    created = runner.invoke(cli_main.app, ["endpoint", "create", "--path", "/api/users", "--file", str(csv_file)])
    id_line = next(line for line in created.stdout.splitlines() if line.strip().startswith("ID:"))
    endpoint_id = id_line.split("ID:")[1].strip()

    result = runner.invoke(cli_main.app, ["endpoint", "delete", endpoint_id], input="y\n")
    assert result.exit_code == 0
    assert "Deleted" in result.stdout


def test_api_key_create_and_list(cli_env):
    created = runner.invoke(cli_main.app, ["auth", "api-key", "create", "my-service"])
    assert created.exit_code == 0
    assert "API key created" in created.stdout

    listed = runner.invoke(cli_main.app, ["auth", "api-key", "list"])
    assert listed.exit_code == 0
    assert "my-service" in listed.stdout


def test_user_create_with_password_option(cli_env):
    result = runner.invoke(cli_main.app, ["auth", "user", "create", "--username", "alice", "--password", "hunter2"])
    assert result.exit_code == 0
    assert "User created" in result.stdout

    listed = runner.invoke(cli_main.app, ["auth", "user", "list"])
    assert "alice" in listed.stdout


def test_jwt_config_status_and_token(cli_env):
    status_before = runner.invoke(cli_main.app, ["auth", "jwt", "status"])
    assert "not configured" in status_before.stdout

    configured = runner.invoke(cli_main.app, ["auth", "jwt", "config"])
    assert configured.exit_code == 0
    assert "JWT configured" in configured.stdout

    status_after = runner.invoke(cli_main.app, ["auth", "jwt", "status"])
    assert "is configured" in status_after.stdout

    token = runner.invoke(cli_main.app, ["auth", "jwt", "token", "--subject", "svc"])
    assert token.exit_code == 0
    assert "Token" in token.stdout
