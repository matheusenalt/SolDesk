from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.config import Settings
from app.main import create_app


@pytest.fixture
def database(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("SOLDESK_MODE", "community")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:8080,http://localhost:5173")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)
    command.upgrade(config, "0001")
    return url, config


def test_health_and_info_persist_across_restart_and_repeat_migration(database):
    url, config = database
    with TestClient(create_app(Settings(database_url=url))) as client:
        assert client.get("/api/v1/health").json() == {"status": "ok", "database": "connected"}
        first = client.get("/api/v1/server-info").json()
        UUID(first["instance_id"])
        assert first["capabilities"] == ["health", "server_info"]
        assert first["mode"] == "community"
        assert set(inspect(client.app.state.sessions.kw["bind"]).get_table_names()) == {
            "installation",
            "alembic_version",
        }
    command.upgrade(config, "0001")
    with TestClient(create_app(Settings(database_url=url))) as client:
        assert client.get("/api/v1/server-info").json() == first


def test_unmigrated_database_is_not_reported_healthy(tmp_path):
    with TestClient(create_app(Settings(database_url=f"sqlite:///{tmp_path}/empty.db"))) as c:
        for endpoint in ("health", "server-info"):
            response = c.get(f"/api/v1/{endpoint}")
            assert response.status_code == 503
            assert response.headers["content-type"] == "application/problem+json"
            assert "sqlite" not in response.text


def test_problem_details_and_business_requires_postgresql(database):
    with TestClient(create_app(Settings(database_url=database[0]))) as client:
        response = client.get("/api/v1/clients")
        assert response.status_code == 503
        assert response.headers["content-type"] == "application/problem+json"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.json()["request_id"] == response.headers["x-request-id"]
        assert client.get("/openapi.json").status_code == 200


def test_cors_rejects_untrusted_origin(database):
    with TestClient(create_app(Settings(database_url=database[0]))) as client:
        allowed = client.get("/api/v1/health", headers={"Origin": "http://localhost:8080"})
        assert allowed.headers["access-control-allow-origin"] == "http://localhost:8080"
        denied = client.get("/api/v1/health", headers={"Origin": "https://untrusted.invalid"})
        assert "access-control-allow-origin" not in denied.headers
        assert client.post("/api/v1/health").status_code == 405


def test_cloud_mode_and_invalid_configuration(database):
    with TestClient(create_app(Settings(database_url=database[0], soldesk_mode="cloud"))) as c:
        assert c.get("/api/v1/server-info").json()["mode"] == "cloud"
    with pytest.raises(ValueError):
        Settings(cors_origins="*")
    with pytest.raises(ValueError):
        Settings(soldesk_mode="invalid")
