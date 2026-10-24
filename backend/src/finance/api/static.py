"""Service du frontend compilé, avec repli sur index.html pour les routes de l'application."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles


def mount_frontend(app: FastAPI, directory: Path) -> bool:
    """Monte le frontend de `directory` ; renvoie faux s'il n'y a pas de build."""
    index = directory / "index.html"
    if not index.is_file():
        return False
    root = directory.resolve()

    assets = directory / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/") or path == "api":
            raise HTTPException(status_code=404, detail="Ressource introuvable")
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index, headers={"cache-control": "no-cache"})

    return True
