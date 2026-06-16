"""GitHub OAuth authentication routes."""

import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from staged_recipe_dashboard.backend.app import get_db
from staged_recipe_dashboard.backend.models import User, UserSession
from staged_recipe_dashboard.config import load_config

router = APIRouter(prefix="/auth")

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"

SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days in seconds
OAUTH_STATE_MAX_AGE = 300  # 5 minutes


@router.get("/login")
def login():
    """Redirect the browser to GitHub's OAuth authorization page."""
    cfg = load_config().auth
    state = secrets.token_hex(16)

    params = urlencode({
        "client_id": cfg.github_client_id,
        "redirect_uri": f"{cfg.base_url}/auth/callback",
        "scope": "read:user",
        "state": state,
    })
    response = RedirectResponse(url=f"{GITHUB_AUTHORIZE_URL}?{params}", status_code=302)
    response.set_cookie(
        "oauth_state",
        state,
        httponly=True,
        samesite="lax",
        max_age=OAUTH_STATE_MAX_AGE,
    )
    return response


@router.get("/callback")
def callback(
    code: str = Query(...),
    state: str = Query(...),
    oauth_state: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
):
    """Exchange OAuth code for access token, upsert user, create session."""
    # 1. Verify CSRF state
    if not oauth_state or oauth_state != state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    cfg = load_config().auth

    # 2. Exchange code for access token
    with httpx.Client() as client:
        token_resp = client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": cfg.github_client_id,
                "client_secret": cfg.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
    token_resp.raise_for_status()
    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        error = token_data.get("error", "unknown")
        error_desc = token_data.get("error_description", "")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to obtain access token from GitHub: {error} — {error_desc}",
        )

    # 3. Fetch GitHub user profile
    with httpx.Client() as client:
        user_resp = client.get(
            GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
    user_resp.raise_for_status()
    gh_user = user_resp.json()
    github_id = gh_user["id"]
    github_login = gh_user["login"]
    avatar_url = gh_user.get("avatar_url")

    # 4. Upsert user
    user = db.execute(
        select(User).where(User.github_id == github_id)
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if user is None:
        user = User(
            github_id=github_id,
            github_login=github_login,
            avatar_url=avatar_url,
            created_at=now,
        )
        db.add(user)
        db.flush()  # get user.id
    else:
        user.github_login = github_login
        user.avatar_url = avatar_url

    # 5. Create session
    session_token = secrets.token_hex(32)
    session = UserSession(
        token=session_token,
        user_id=user.id,
        created_at=now,
        expires_at=now + timedelta(days=30),
    )
    db.add(session)
    db.commit()

    # 6. Redirect to home with session cookie
    response = RedirectResponse(url=f"{cfg.base_url}/", status_code=302)
    response.set_cookie(
        "session",
        session_token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=SESSION_MAX_AGE,
    )
    # Clear the oauth_state cookie
    response.delete_cookie("oauth_state")
    return response


@router.get("/logout")
def logout(
    session_token: str | None = Cookie(default=None, alias="session"),
    db: DBSession = Depends(get_db),
):
    """Delete the session and clear the cookie."""
    if session_token:
        session = db.execute(
            select(UserSession).where(UserSession.token == session_token)
        ).scalar_one_or_none()
        if session:
            db.delete(session)
            db.commit()

    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session", path="/")
    return response
