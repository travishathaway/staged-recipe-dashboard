"""FastAPI application factory."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_engine = None
_SessionLocal = None

STATIC_DIR = Path(__file__).parent.parent / "static"


def get_engine():
    global _engine
    if _engine is None:
        from staged_recipe_dashboard.config import load_config

        _engine = create_engine(load_config().database.url, pool_pre_ping=True)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
    return _SessionLocal


def get_db():
    """FastAPI dependency that yields a SQLAlchemy session."""
    Session = get_session_factory()
    db = Session()
    try:
        yield db
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_engine()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="staged-recipe-dashboard",
        description="Dashboard API for conda-forge staged-recipe reviewers",
        lifespan=lifespan,
    )

    from staged_recipe_dashboard.backend.routes.api import router

    app.include_router(router)

    # Serve Vite-generated assets (mounted before the catch-all).
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # SPA catch-all: any non-/api path returns index.html so Svelte routing works.
    @app.get("/{path:path}", include_in_schema=False)
    async def spa_fallback(path: str):
        index = STATIC_DIR / "index.html"
        if not index.exists():
            return {"detail": "Frontend not built. Run `srdb build-ui` first."}
        return FileResponse(str(index))

    return app
