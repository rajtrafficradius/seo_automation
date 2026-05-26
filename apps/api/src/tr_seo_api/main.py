from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi import Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from tr_seo_api.config import get_settings
from tr_seo_api.routes import health, module0

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(module0.router)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
FRONTEND_DIST = PROJECT_ROOT / "apps" / "portal" / "dist"


@app.get("/", include_in_schema=False, response_model=None)
def serve_frontend_index() -> Response:
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse(
        {
            "message": "Frontend build not found.",
            "next_step": "Run the local launcher script to build the frontend and start the app.",
        },
        status_code=503,
    )


@app.get("/{full_path:path}", include_in_schema=False, response_model=None)
def serve_frontend_assets(full_path: str) -> Response:
    if full_path.startswith("api/") or full_path == "health":
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    requested = (FRONTEND_DIST / full_path).resolve()
    if FRONTEND_DIST.exists() and requested.is_file() and FRONTEND_DIST in requested.parents:
        return FileResponse(requested)

    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)

    return JSONResponse(
        {
            "message": "Frontend build not found.",
            "next_step": "Run the local launcher script to build the frontend and start the app.",
        },
        status_code=503,
    )
