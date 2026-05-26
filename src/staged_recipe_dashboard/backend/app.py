"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_engine = None
_SessionLocal = None


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

    return app


app = create_app()
