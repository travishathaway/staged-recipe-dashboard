"""FastAPI application factory."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Cookie, Depends, FastAPI, HTTPException
from sqlalchemy import select
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


def get_current_user(
    session_token: str | None = Cookie(default=None, alias="session"),
    db=Depends(get_db),
):
    """Returns the authenticated User ORM object, or None if not logged in / session expired."""
    if not session_token:
        return None
    from staged_recipe_dashboard.backend.models import UserSession

    now = datetime.now(timezone.utc)
    session = db.execute(
        select(UserSession)
        .where(
            UserSession.token == session_token,
            UserSession.expires_at > now,
        )
        .join(UserSession.user)
    ).scalar_one_or_none()
    return session.user if session else None


def require_user(user=Depends(get_current_user)):
    """Like get_current_user but raises 401 if not authenticated."""
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


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
    from staged_recipe_dashboard.backend.routes.auth import router as auth_router
    from staged_recipe_dashboard.backend.routes.me import router as me_router
    from staged_recipe_dashboard.backend.routes.prefs import router as prefs_router

    app.include_router(router)
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(prefs_router)

    return app


app = create_app()
