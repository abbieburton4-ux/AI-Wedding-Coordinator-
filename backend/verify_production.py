"""Production configuration and execution checks; never uses real credentials."""
import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["SYNC_DATABASE_URL"] = "sqlite://"
os.environ["DEVELOPMENT_MODE"] = "False"
os.environ["ALLOW_MOCK_AUTH"] = "False"
os.environ["REPLIT_MANAGED_DATABASE"] = "False"
os.environ["DIRECT_AGENT_EXECUTION"] = "True"

from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.config import Settings, settings
from app.utils.tasks import enqueue_agent_task


async def check_execution():
    with patch("app.utils.direct_tasks.execute_agent_task", new_callable=AsyncMock) as run:
        run.return_value = {"status": "success"}
        assert await enqueue_agent_task("intake-planner", {"wedding_id": "fictional"})
        run.assert_awaited_once_with("intake-planner", {"wedding_id": "fictional"})
        run.side_effect = RuntimeError("private provider error")
        try:
            await enqueue_agent_task("venue-matcher", {"wedding_id": "fictional"})
            raise AssertionError("Failed execution was acknowledged")
        except HTTPException as exc:
            assert exc.status_code == 502
            assert "private provider error" not in str(exc.detail)
        run.side_effect = None
        run.return_value = {"status": "blocked", "error_kind": "budget_guardrail"}
        try:
            await enqueue_agent_task("intake-planner", {"wedding_id": "fictional"})
            raise AssertionError("Guardrail block was acknowledged as success")
        except HTTPException as exc:
            assert exc.status_code == 422
            assert exc.detail["error_kind"] == "budget_guardrail"
    settings.DIRECT_AGENT_EXECUTION = False
    try:
        await enqueue_agent_task("intake-planner", {"wedding_id": "fictional"})
        raise AssertionError("Unconfigured production queue was acknowledged")
    except HTTPException as exc:
        assert exc.status_code == 503
    finally:
        settings.DIRECT_AGENT_EXECUTION = True


def check_config():
    config = Settings(
        _env_file=None,
        DATABASE_URL="postgresql://test_user:test_password@database/test?sslmode=require",
        SYNC_DATABASE_URL=None,
    )
    assert config.DATABASE_URL.startswith("postgresql+asyncpg:")
    assert "ssl=require" in config.DATABASE_URL and "sslmode" not in config.DATABASE_URL
    assert config.SYNC_DATABASE_URL.startswith("postgresql+psycopg2:")
    assert "sslmode=require" in config.SYNC_DATABASE_URL


def check_static_and_auth():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "index.html").write_text("<html>production SPA</html>")
        Path(tmp, "test.js").write_text("console.log('asset')")
        settings.FRONTEND_DIST_DIR = tmp
        from app.production import app
        # Startup is tested separately against the development PostgreSQL schema.
        client = TestClient(app)
        assert "production SPA" in client.get("/").text
        assert "production SPA" in client.get("/wedding/intake").text
        assert client.get("/test.js").status_code == 200
        assert client.get("/missing.js").status_code == 404
        assert client.get("/api/not-a-route").status_code == 404
        assert client.get("/tasks/not-a-route").status_code == 404
        assert client.get("/api/health").json()["environment"] == "production"
        assert client.get("/api/v1/auth/me").status_code == 401
        assert client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer mock-couple_2"}
        ).status_code == 401
        assert client.post("/tasks/intake-planner", json={"wedding_id": "x"}).status_code == 403


if __name__ == "__main__":
    check_config()
    asyncio.run(check_execution())
    check_static_and_auth()
    print("--- PRODUCTION CONFIGURATION AND EXECUTION VERIFICATION PASSED ---")
