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


def check_startup_migrations():
    """Replit production startup runs Alembic (rule 6) and never create_all."""
    import app.db.models  # noqa: F401  (registers every table on the metadata)
    import app.db.session as session_module
    import app.main as main_module
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, text
    from sqlmodel import SQLModel

    previous = (settings.REPLIT_MANAGED_DATABASE, settings.DEVELOPMENT_MODE,
                settings.ALLOW_MOCK_AUTH)
    settings.REPLIT_MANAGED_DATABASE = True
    settings.DEVELOPMENT_MODE = False
    settings.ALLOW_MOCK_AUTH = False
    try:
        with patch.object(main_module, "apply_migrations") as migrate, \
                patch("app.db.seed.seed_database"), \
                patch.object(SQLModel.metadata, "create_all") as create_all:
            main_module.on_startup()
            migrate.assert_called_once_with()
            create_all.assert_not_called()
            for flag in ("DEVELOPMENT_MODE", "ALLOW_MOCK_AUTH"):
                setattr(settings, flag, True)
                try:
                    main_module.on_startup()
                    raise AssertionError(f"Replit startup accepted {flag}")
                except RuntimeError:
                    pass
                finally:
                    setattr(settings, flag, False)
    finally:
        (settings.REPLIT_MANAGED_DATABASE, settings.DEVELOPMENT_MODE,
         settings.ALLOW_MOCK_AUTH) = previous

    here = Path(__file__).resolve().parent
    cfg = Config(str(here / "alembic.ini"))
    cfg.set_main_option("script_location", str(here / "migrations"))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    with tempfile.TemporaryDirectory() as tmp:
        prev_url, prev_engine = settings.SYNC_DATABASE_URL, session_module.sync_engine
        try:
            # A fresh database is migrated to head, and a second start is a no-op.
            url = f"sqlite:///{tmp}/fresh.db"
            settings.SYNC_DATABASE_URL = url
            session_module.sync_engine = create_engine(url)
            main_module.apply_migrations()
            main_module.apply_migrations()
            with session_module.sync_engine.connect() as conn:
                version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            assert version == head, (version, head)

            # Tables built by something other than Alembic (such as a publish-time
            # schema sync) stop the app instead of being migrated over.
            url = f"sqlite:///{tmp}/synced.db"
            settings.SYNC_DATABASE_URL = url
            session_module.sync_engine = create_engine(url)
            SQLModel.metadata.create_all(session_module.sync_engine)
            try:
                main_module.apply_migrations()
                raise AssertionError("An unversioned schema was migrated over")
            except RuntimeError as exc:
                assert "no Alembic migration record" in str(exc)
        finally:
            settings.SYNC_DATABASE_URL, session_module.sync_engine = prev_url, prev_engine


def check_webhook_does_not_invite_redelivery():
    """A failed in-request extraction must not make SendGrid resend the email."""
    from types import SimpleNamespace
    from starlette.requests import Request
    from unittest.mock import MagicMock
    import app.api.v1.endpoints.webhooks as webhooks_module
    from app.db.session import get_db
    from app.main import app

    booking = SimpleNamespace(id="bk_fictional")

    async def fake_db():
        db = MagicMock()
        db.exec = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=booking)))
        yield db

    form = {"to": "booking-bk_fictional@inbox.venueflow.ie", "text": "EUR 1"}

    # python-multipart isn't a backend dependency, so feed the parsed form directly.
    async def fake_form(_request):
        return form

    previous_secret = settings.INBOUND_EMAIL_SECRET
    settings.INBOUND_EMAIL_SECRET = "fictional-inbound-secret"
    app.dependency_overrides[get_db] = fake_db
    form_patch = patch.object(Request, "form", fake_form)
    form_patch.start()
    try:
        client = TestClient(app)
        url = "/api/v1/webhooks/sendgrid/inbound?token=fictional-inbound-secret"
        for code in (422, 502):
            with patch.object(webhooks_module, "enqueue_agent_task",
                              AsyncMock(side_effect=HTTPException(status_code=code))):
                res = client.post(url, data=form)
                assert res.status_code == 200 and res.json()["status"] == "not_processed"
        # A missing execution setup is not logged anywhere, so let SendGrid retry.
        with patch.object(webhooks_module, "enqueue_agent_task",
                          AsyncMock(side_effect=HTTPException(status_code=503))):
            assert client.post(url, data=form).status_code == 503
    finally:
        form_patch.stop()
        app.dependency_overrides.pop(get_db, None)
        settings.INBOUND_EMAIL_SECRET = previous_secret


if __name__ == "__main__":
    check_config()
    asyncio.run(check_execution())
    check_static_and_auth()
    check_startup_migrations()
    check_webhook_does_not_invite_redelivery()
    print("--- PRODUCTION CONFIGURATION AND EXECUTION VERIFICATION PASSED ---")
