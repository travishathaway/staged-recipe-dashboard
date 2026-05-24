"""REST API endpoints for the dashboard."""

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, exists, func, not_, select, text
from sqlalchemy.orm import Session

from staged_recipe_dashboard.backend.app import get_db
from staged_recipe_dashboard.backend.models import PRLabel, PRLabelHistory, PullRequest

router = APIRouter(prefix="/api")

# Labels that carry status meaning, not team assignment.
STATUS_LABELS = {"review-requested", "Awaiting author contribution"}


# ── Pydantic response schemas ─────────────────────────────────────────────────


class PRResponse(BaseModel):
    number: int
    title: str | None
    author: str | None
    state: str
    html_url: str | None
    created_at: datetime | None
    waiting_since: datetime | None
    labels: list[str]

    class Config:
        from_attributes = True


class TeamResponse(BaseModel):
    name: str
    needs_review_count: int
    blocked_count: int


class StatsResponse(BaseModel):
    total_open: int
    needs_review: int
    blocked: int
    by_team: list[TeamResponse]


# ── Reusable query fragments ──────────────────────────────────────────────────


def _has_label(label: str):
    """Subquery: PR has a specific label."""
    return exists(
        select(PRLabel.pr_number).where(
            and_(PRLabel.pr_number == PullRequest.number, PRLabel.label_name == label)
        )
    )


def _needs_review_filter():
    return and_(
        PullRequest.state == "open",
        _has_label("review-requested"),
        not_(_has_label("Awaiting author contribution")),
    )


def _blocked_filter():
    return and_(
        PullRequest.state == "open",
        _has_label("review-requested"),
        _has_label("Awaiting author contribution"),
    )


def _get_labels(db: Session, pr_number: int) -> list[str]:
    rows = db.execute(
        select(PRLabel.label_name).where(PRLabel.pr_number == pr_number)
    ).scalars().all()
    return list(rows)


def _to_pr_response(pr: PullRequest, waiting_since: datetime | None, db: Session) -> PRResponse:
    return PRResponse(
        number=pr.number,
        title=pr.title,
        author=pr.author,
        state=pr.state,
        html_url=pr.html_url,
        created_at=pr.created_at,
        waiting_since=waiting_since,
        labels=_get_labels(db, pr.number),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/prs", response_model=list[PRResponse])
def list_prs(
    team: str | None = Query(None, description="Filter by team label (e.g. 'python', 'rust')"),
    status: Literal["needs_review", "blocked", "all"] = Query(
        "needs_review", description="Which PRs to return"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List open PRs, optionally filtered by team and review status."""
    waiting_since_col = PRLabelHistory.applied_at.label("waiting_since")

    stmt = (
        select(PullRequest, waiting_since_col)
        .outerjoin(
            PRLabelHistory,
            and_(
                PRLabelHistory.pr_number == PullRequest.number,
                PRLabelHistory.label_name == "review-requested",
            ),
        )
        .where(PullRequest.state == "open")
    )

    if status == "needs_review":
        stmt = stmt.where(_needs_review_filter())
    elif status == "blocked":
        stmt = stmt.where(_blocked_filter())

    if team:
        stmt = stmt.where(_has_label(team))

    stmt = stmt.order_by(PRLabelHistory.applied_at.asc().nullslast()).limit(limit).offset(offset)

    rows = db.execute(stmt).all()
    return [_to_pr_response(pr, waiting_since, db) for pr, waiting_since in rows]


@router.get("/teams", response_model=list[TeamResponse])
def list_teams(db: Session = Depends(get_db)):
    """List all review teams with their needs-review and blocked PR counts."""
    # Discover team labels dynamically (any label on an open PR that isn't a status label).
    team_labels = db.execute(
        select(PRLabel.label_name)
        .join(PullRequest, PRLabel.pr_number == PullRequest.number)
        .where(
            PullRequest.state == "open",
            PRLabel.label_name.notin_(STATUS_LABELS),
        )
        .distinct()
        .order_by(PRLabel.label_name)
    ).scalars().all()

    results = []
    for team_name in team_labels:
        needs_review = db.scalar(
            select(func.count()).select_from(PullRequest).where(
                _needs_review_filter(),
                _has_label(team_name),
            )
        ) or 0

        blocked = db.scalar(
            select(func.count()).select_from(PullRequest).where(
                _blocked_filter(),
                _has_label(team_name),
            )
        ) or 0

        results.append(TeamResponse(
            name=team_name,
            needs_review_count=needs_review,
            blocked_count=blocked,
        ))

    return results


@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    """Aggregate statistics across all open PRs."""
    total_open = db.scalar(
        select(func.count()).select_from(PullRequest).where(PullRequest.state == "open")
    ) or 0

    needs_review = db.scalar(
        select(func.count()).select_from(PullRequest).where(_needs_review_filter())
    ) or 0

    blocked = db.scalar(
        select(func.count()).select_from(PullRequest).where(_blocked_filter())
    ) or 0

    # Reuse list_teams for by_team breakdown.
    by_team = list_teams(db=db)

    return StatsResponse(
        total_open=total_open,
        needs_review=needs_review,
        blocked=blocked,
        by_team=by_team,
    )


@router.get("/prs/{number}", response_model=PRResponse)
def get_pr(number: int, db: Session = Depends(get_db)):
    """Get a single PR with its full label history."""
    pr = db.scalar(select(PullRequest).where(PullRequest.number == number))
    if pr is None:
        raise HTTPException(status_code=404, detail=f"PR #{number} not found")

    waiting_since = db.scalar(
        select(PRLabelHistory.applied_at).where(
            PRLabelHistory.pr_number == number,
            PRLabelHistory.label_name == "review-requested",
        )
    )

    return _to_pr_response(pr, waiting_since, db)


# ── Scoreboard ────────────────────────────────────────────────────────────────

_PERIOD_DELTAS = {
    "30d": timedelta(days=30),
    "90d": timedelta(days=90),
    "1y": timedelta(days=365),
    "3y": timedelta(days=365 * 3),
}


class ReviewerScore(BaseModel):
    login: str
    formal_reviews: int
    approved: int
    changes_requested: int
    dismissed: int
    review_comments: int
    last_active: datetime | None


class ScoreboardResponse(BaseModel):
    period: str
    team: str | None
    human_reviewers: list[ReviewerScore]
    bots: list[ReviewerScore]


@router.get("/scoreboard", response_model=ScoreboardResponse)
def get_scoreboard(
    period: Literal["30d", "90d", "1y", "3y"] = Query(
        ..., description="Rolling time window for the scoreboard."
    ),
    team: str | None = Query(None, description="Filter to reviews on PRs tagged for this team."),
    db: Session = Depends(get_db),
):
    """Reviewer scoreboard: formal reviews and review comments per contributor."""
    cutoff = datetime.now(timezone.utc) - _PERIOD_DELTAS[period]

    team_subquery = (
        "AND r.pr_number IN (SELECT pr_number FROM pr_labels WHERE label_name = :team)"
        if team else ""
    )
    comment_team_subquery = (
        "AND c.pr_number IN (SELECT pr_number FROM pr_labels WHERE label_name = :team)"
        if team else ""
    )

    params: dict = {"cutoff": cutoff}
    if team:
        params["team"] = team

    sql = text(f"""
        WITH review_stats AS (
            SELECT
                r.reviewer                                                              AS login,
                r.reviewer_type,
                COUNT(*) FILTER (WHERE r.state IN ('APPROVED','CHANGES_REQUESTED','DISMISSED'))
                                                                                        AS formal_reviews,
                COUNT(*) FILTER (WHERE r.state = 'APPROVED')                           AS approved,
                COUNT(*) FILTER (WHERE r.state = 'CHANGES_REQUESTED')                  AS changes_requested,
                COUNT(*) FILTER (WHERE r.state = 'DISMISSED')                          AS dismissed,
                COUNT(*) FILTER (WHERE r.state = 'COMMENTED')                          AS commented_reviews,
                MAX(r.submitted_at)                                                     AS last_review_at
            FROM pr_reviews r
            WHERE r.submitted_at >= :cutoff
              {team_subquery}
            GROUP BY r.reviewer, r.reviewer_type
        ),
        comment_stats AS (
            SELECT
                c.commenter                                                             AS login,
                c.commenter_type                                                        AS reviewer_type,
                COUNT(*)                                                                AS comment_count,
                MAX(c.created_at)                                                       AS last_comment_at
            FROM pr_review_comments c
            WHERE c.created_at >= :cutoff
              {comment_team_subquery}
            GROUP BY c.commenter, c.commenter_type
        )
        SELECT
            COALESCE(r.login, c.login)                                                  AS login,
            COALESCE(r.reviewer_type, c.reviewer_type)                                  AS reviewer_type,
            COALESCE(r.formal_reviews, 0)                                               AS formal_reviews,
            COALESCE(r.approved, 0)                                                     AS approved,
            COALESCE(r.changes_requested, 0)                                            AS changes_requested,
            COALESCE(r.dismissed, 0)                                                    AS dismissed,
            COALESCE(r.commented_reviews, 0) + COALESCE(c.comment_count, 0)            AS review_comments,
            GREATEST(r.last_review_at, c.last_comment_at)                              AS last_active
        FROM review_stats r
        FULL OUTER JOIN comment_stats c ON r.login = c.login
        ORDER BY formal_reviews DESC, review_comments DESC
    """)

    rows = db.execute(sql, params).mappings().all()

    human_reviewers = []
    bots = []
    for row in rows:
        score = ReviewerScore(
            login=row["login"],
            formal_reviews=row["formal_reviews"],
            approved=row["approved"],
            changes_requested=row["changes_requested"],
            dismissed=row["dismissed"],
            review_comments=row["review_comments"],
            last_active=row["last_active"],
        )
        if row["reviewer_type"] == "Bot":
            bots.append(score)
        else:
            human_reviewers.append(score)

    return ScoreboardResponse(
        period=period,
        team=team,
        human_reviewers=human_reviewers,
        bots=bots,
    )
