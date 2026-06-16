"""User preferences CRUD endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session as DBSession

from staged_recipe_dashboard.backend.app import get_db, require_user
from staged_recipe_dashboard.backend.models import UserPreference

router = APIRouter(prefix="/api")


# ── Response models ────────────────────────────────────────────────────────────


class PrefsResponse(BaseModel):
    starred: list[int]
    ignored: list[int]
    notes: dict[str, str]


class NoteBody(BaseModel):
    text: str


class MigrateResult(BaseModel):
    imported: dict[str, int]


# ── Helper ─────────────────────────────────────────────────────────────────────


def _get_all_prefs(user_id: int, db: DBSession) -> PrefsResponse:
    rows = db.execute(
        select(UserPreference).where(UserPreference.user_id == user_id)
    ).scalars().all()
    starred = []
    ignored = []
    notes: dict[str, str] = {}
    for row in rows:
        if row.pref_type == "starred":
            starred.append(row.pr_number)
        elif row.pref_type == "ignored":
            ignored.append(row.pr_number)
        elif row.pref_type == "note" and row.data:
            notes[str(row.pr_number)] = row.data.get("text", "")
    return PrefsResponse(starred=starred, ignored=ignored, notes=notes)


def _upsert_pref(user_id: int, pref_type: str, pr_number: int, data: Any, db: DBSession) -> None:
    stmt = (
        insert(UserPreference)
        .values(user_id=user_id, pref_type=pref_type, pr_number=pr_number, data=data)
        .on_conflict_do_update(
            index_elements=["user_id", "pref_type", "pr_number"],
            set_={"data": data},
        )
    )
    db.execute(stmt)
    db.commit()


def _delete_pref(user_id: int, pref_type: str, pr_number: int, db: DBSession) -> None:
    db.execute(
        delete(UserPreference).where(
            UserPreference.user_id == user_id,
            UserPreference.pref_type == pref_type,
            UserPreference.pr_number == pr_number,
        )
    )
    db.commit()


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/prefs", response_model=PrefsResponse)
def get_prefs(current_user=Depends(require_user), db: DBSession = Depends(get_db)):
    """Return all preferences for the authenticated user."""
    return _get_all_prefs(current_user.id, db)


@router.put("/prefs/star/{pr_number}", status_code=200)
def star_pr(pr_number: int, current_user=Depends(require_user), db: DBSession = Depends(get_db)):
    _upsert_pref(current_user.id, "starred", pr_number, None, db)
    return {"ok": True}


@router.delete("/prefs/star/{pr_number}", status_code=200)
def unstar_pr(pr_number: int, current_user=Depends(require_user), db: DBSession = Depends(get_db)):
    _delete_pref(current_user.id, "starred", pr_number, db)
    return {"ok": True}


@router.put("/prefs/ignore/{pr_number}", status_code=200)
def ignore_pr(pr_number: int, current_user=Depends(require_user), db: DBSession = Depends(get_db)):
    _upsert_pref(current_user.id, "ignored", pr_number, None, db)
    return {"ok": True}


@router.delete("/prefs/ignore/{pr_number}", status_code=200)
def unignore_pr(pr_number: int, current_user=Depends(require_user), db: DBSession = Depends(get_db)):
    _delete_pref(current_user.id, "ignored", pr_number, db)
    return {"ok": True}


@router.put("/prefs/note/{pr_number}", status_code=200)
def set_note(
    pr_number: int,
    body: NoteBody,
    current_user=Depends(require_user),
    db: DBSession = Depends(get_db),
):
    if not body.text or not body.text.strip():
        _delete_pref(current_user.id, "note", pr_number, db)
    else:
        _upsert_pref(current_user.id, "note", pr_number, {"text": body.text}, db)
    return {"ok": True}


@router.delete("/prefs/note/{pr_number}", status_code=200)
def delete_note(pr_number: int, current_user=Depends(require_user), db: DBSession = Depends(get_db)):
    _delete_pref(current_user.id, "note", pr_number, db)
    return {"ok": True}


# ── Migration ─────────────────────────────────────────────────────────────────


def _migrate_blob(raw: dict) -> dict:
    """Apply the same migration logic as the frontend migrate() function.

    Handles v1, v2, v3 of the srdb-preferences schema.
    Falls back to empty prefs for unknown versions.
    """
    version = raw.get("version")
    if version == 3:
        return raw
    if version == 2:
        return {**raw, "version": 3, "ignored": {"prs": {}}, "notes": {"prs": {}}}
    if version == 1:
        v2 = {**raw, "version": 2, "starred": {"prs": {}}}
        return _migrate_blob(v2)
    # Unknown version — treat as empty
    return {"version": 3, "profile": {"githubUsername": None}, "starred": {"prs": {}}, "ignored": {"prs": {}}, "notes": {"prs": {}}}


@router.post("/prefs/migrate", response_model=MigrateResult)
def migrate_prefs(
    body: dict,
    current_user=Depends(require_user),
    db: DBSession = Depends(get_db),
):
    """Import an srdb-preferences localStorage blob into server-side preferences.

    Uses INSERT ... ON CONFLICT DO NOTHING so it is idempotent.
    """
    migrated = _migrate_blob(body)

    starred_count = 0
    ignored_count = 0
    notes_count = 0

    starred_prs = migrated.get("starred", {}).get("prs", {})
    ignored_prs = migrated.get("ignored", {}).get("prs", {})
    notes_prs = migrated.get("notes", {}).get("prs", {})

    for key in starred_prs:
        try:
            pr_number = int(key)
        except (ValueError, TypeError):
            continue
        stmt = (
            insert(UserPreference)
            .values(user_id=current_user.id, pref_type="starred", pr_number=pr_number, data=None)
            .on_conflict_do_nothing()
        )
        db.execute(stmt)
        starred_count += 1

    for key in ignored_prs:
        try:
            pr_number = int(key)
        except (ValueError, TypeError):
            continue
        stmt = (
            insert(UserPreference)
            .values(user_id=current_user.id, pref_type="ignored", pr_number=pr_number, data=None)
            .on_conflict_do_nothing()
        )
        db.execute(stmt)
        ignored_count += 1

    for key, text in notes_prs.items():
        try:
            pr_number = int(key)
        except (ValueError, TypeError):
            continue
        if not isinstance(text, str):
            continue
        stmt = (
            insert(UserPreference)
            .values(user_id=current_user.id, pref_type="note", pr_number=pr_number, data={"text": text})
            .on_conflict_do_nothing()
        )
        db.execute(stmt)
        notes_count += 1

    db.commit()
    return MigrateResult(imported={"starred": starred_count, "ignored": ignored_count, "notes": notes_count})
