"""Serve the built React PWA from FastAPI (production single-container deploy)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_spa(app: FastAPI, static_dir: Path) -> None:
    if not static_dir.is_dir():
        return

    def _file(path: Path) -> FileResponse:
        headers = {}
        if path.name in {"index.html", "sw.js", "manifest.webmanifest"}:
            headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return FileResponse(path, headers=headers)

    assets = static_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/", include_in_schema=False)
    async def spa_root() -> FileResponse:
        return _file(static_dir / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = static_dir / full_path
        if candidate.is_file():
            return _file(candidate)
        return _file(static_dir / "index.html")
