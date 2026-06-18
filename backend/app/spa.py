"""Serve the built React PWA from FastAPI (production single-container deploy)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import app.config as config

_RUNTIME_CONFIG_MARKER = "<!--macroreel-runtime-config-->"
_NO_CACHE_HEADERS = {"Cache-Control": "no-cache, no-store, must-revalidate"}


def _inject_runtime_config(html: str) -> str:
    if _RUNTIME_CONFIG_MARKER not in html:
        return html
    payload = json.dumps({"google_client_id": config.GOOGLE_CLIENT_ID})
    snippet = f"<script>window.__MACROREEL_CONFIG__={payload}</script>"
    return html.replace(_RUNTIME_CONFIG_MARKER, snippet)


def _serve_index(static_dir: Path) -> HTMLResponse:
    html = (static_dir / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(_inject_runtime_config(html), headers=_NO_CACHE_HEADERS)


def mount_spa(app: FastAPI, static_dir: Path) -> None:
    if not static_dir.is_dir():
        return

    def _file(path: Path) -> FileResponse:
        headers = {}
        if path.name in {"index.html", "sw.js", "manifest.webmanifest"}:
            headers.update(_NO_CACHE_HEADERS)
        return FileResponse(path, headers=headers)

    assets = static_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/", include_in_schema=False)
    async def spa_root() -> HTMLResponse:
        return _serve_index(static_dir)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse | HTMLResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = static_dir / full_path
        if candidate.is_file():
            return _file(candidate)
        return _serve_index(static_dir)
