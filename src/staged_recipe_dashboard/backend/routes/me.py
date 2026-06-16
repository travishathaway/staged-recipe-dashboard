"""Current user identity endpoint."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from staged_recipe_dashboard.backend.app import get_current_user

router = APIRouter(prefix="/api")


class MeResponse(BaseModel):
    authenticated: bool
    login: str | None = None
    avatar_url: str | None = None


@router.get("/me", response_model=MeResponse)
def get_me(current_user=Depends(get_current_user)):
    """Return current user identity. Always 200; authenticated=false when not logged in."""
    if current_user is None:
        return MeResponse(authenticated=False)
    return MeResponse(
        authenticated=True,
        login=current_user.github_login,
        avatar_url=current_user.avatar_url,
    )
