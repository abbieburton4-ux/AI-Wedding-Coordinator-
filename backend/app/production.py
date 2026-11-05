"""Serve the existing SPA and API together, without the Vite development server."""
from pathlib import Path

from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.main import app


class FrontendFiles(StaticFiles):
    async def get_response(self, path, scope):
        # Unknown API/internal routes must never turn into a successful HTML page.
        if path.split("/", 1)[0] in {"api", "tasks"}:
            raise HTTPException(status_code=404, detail="Not found")
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            # Only extensionless SPA routes get the entry point, not missing assets.
            if exc.status_code == 404 and not Path(path).suffix:
                return await super().get_response("index.html", scope)
            raise


if not settings.FRONTEND_DIST_DIR:
    raise RuntimeError("FRONTEND_DIST_DIR is required for the production server.")
dist = Path(settings.FRONTEND_DIST_DIR)
if not (dist / "index.html").is_file():
    raise RuntimeError("Frontend build is missing. Run scripts/replit-build.sh first.")
app.mount("/", FrontendFiles(directory=dist), name="frontend")
