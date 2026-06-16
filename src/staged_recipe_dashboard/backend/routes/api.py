"""REST API endpoints for the dashboard."""

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, exists, func, not_, or_, select, text, union_all
from sqlalchemy.orm import Session

from staged_recipe_dashboard.backend.app import get_current_user, get_db
from staged_recipe_dashboard.backend.models import PRLabel, PRLabelHistory, PRReview, PRReviewComment, PullRequest

router = APIRouter(prefix="/api")

# Labels that carry status meaning, not team assignment.
STATUS_LABELS = {"review-requested", "Awaiting author contribution"}
TEAM_LABELS = {
    "python", "python-c", "java", "c-cpp",
    "nodejs", "R", "go", "rust", "perl",
}

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
    roles: list[str] = []
    last_commenter: str | None = None
    author_replied: bool = False

    class Config:
        from_attributes = True


class TeamResponse(BaseModel):
    name: str
    needs_review_count: int
    blocked_count: int


class PRListResponse(BaseModel):
    results: list[PRResponse]
    total: int
    last_updated_at: datetime | None = None


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


def _no_human_formal_review_filter():
    """Subquery: PR has no non-bot APPROVED/CHANGES_REQUESTED/DISMISSED review."""
    return not_(
        exists(
            select(PRReview.id).where(
                PRReview.pr_number == PullRequest.number,
                PRReview.reviewer_type != "Bot",
                PRReview.state.in_(["APPROVED", "CHANGES_REQUESTED", "DISMISSED"]),
            )
        )
    )


def _get_labels(db: Session, pr_number: int) -> list[str]:
    rows = db.execute(
        select(PRLabel.label_name).where(PRLabel.pr_number == pr_number)
    ).scalars().all()
    return list(rows)


def _to_pr_response(pr: PullRequest, waiting_since: datetime | None, db: Session, roles: list[str] | None = None, last_commenter: str | None = None) -> PRResponse:
    author_replied = bool(last_commenter and last_commenter == pr.author)
    return PRResponse(
        number=pr.number,
        title=pr.title,
        author=pr.author,
        state=pr.state,
        html_url=pr.html_url,
        created_at=pr.created_at,
        waiting_since=waiting_since,
        labels=_get_labels(db, pr.number),
        roles=roles if roles is not None else [],
        last_commenter=last_commenter,
        author_replied=author_replied,
    )


def _role_annotations(username: str):
    """Return three boolean SELECT columns for author/reviewer/commenter roles."""
    is_author = (PullRequest.author == username).label("is_author")

    is_reviewer = exists(
        select(PRReview.id).where(
            PRReview.pr_number == PullRequest.number,
            PRReview.reviewer == username,
        )
    ).label("is_reviewer")

    is_commenter = exists(
        select(PRReviewComment.id).where(
            PRReviewComment.pr_number == PullRequest.number,
            PRReviewComment.commenter == username,
        )
    ).label("is_commenter")

    return is_author, is_reviewer, is_commenter


def _build_roles(is_author: bool, is_reviewer: bool, is_commenter: bool) -> list[str]:
    """Build the roles list from boolean flags."""
    roles = []
    if is_author:
        roles.append("author")
    if is_reviewer:
        roles.append("reviewer")
    if is_commenter:
        roles.append("commenter")
    return roles


def _last_human_commenter_subquery():
    """
    Returns a scalar subquery yielding the GitHub login of the most recent human
    commenter on a given PR, or NULL if there are none.

    Unions pr_review_comments (issue comments) and pr_reviews (formal reviews).
    Bots are excluded by filtering on commenter_type / reviewer_type = 'User'.
    The subquery is correlated on PullRequest.number.
    """
    comments_q = (
        select(
            PRReviewComment.pr_number.label("pr_number"),
            PRReviewComment.commenter.label("commenter"),
            PRReviewComment.created_at.label("ts"),
        )
        .where(PRReviewComment.commenter_type == "User")
    )
    reviews_q = (
        select(
            PRReview.pr_number.label("pr_number"),
            PRReview.reviewer.label("commenter"),
            PRReview.submitted_at.label("ts"),
        )
        .where(PRReview.reviewer_type == "User")
    )
    combined = union_all(comments_q, reviews_q).subquery("all_human_comments")

    return (
        select(combined.c.commenter)
        .where(combined.c.pr_number == PullRequest.number)
        .order_by(combined.c.ts.desc())
        .limit(1)
        .correlate(PullRequest)
        .scalar_subquery()
        .label("last_commenter")
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/prs", response_model=PRListResponse)
def list_prs(
    numbers: str | None = Query(
        None,
        description="Comma-separated PR numbers to fetch (e.g. for starred PRs). "
                    "When provided, status/team/limit/offset are ignored.",
    ),
    team: str | None = Query(None, description="Filter by team label (e.g. 'python', 'rust')"),
    status: Literal["needs_review", "blocked", "all"] = Query(
        "needs_review", description="Which PRs to return"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    roles: str | None = Query(None, description="Comma-separated roles to filter by: author, reviewer, commenter"),
    unreviewed: bool = Query(False, description="If true, only return PRs with no formal human review (APPROVED/CHANGES_REQUESTED/DISMISSED)"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List open PRs, optionally filtered by team and review status."""
    username = current_user.github_login if current_user else None
    waiting_since_col = PRLabelHistory.applied_at.label("waiting_since")

    # Parse comma-separated roles string into a list.
    role_list = [r.strip() for r in roles.split(",") if r.strip()] if roles else []

    # Build annotation columns when username is provided.
    if username:
        is_author_col, is_reviewer_col, is_commenter_col = _role_annotations(username)
        annotation_cols = (is_author_col, is_reviewer_col, is_commenter_col)
    else:
        annotation_cols = None

    def _extract_roles(row) -> list[str]:
        if annotation_cols is None:
            return []
        return _build_roles(row.is_author, row.is_reviewer, row.is_commenter)

    # Starred / explicit-numbers path: return exactly these open PR numbers.
    if numbers is not None:
        number_list = [
            int(n.strip()) for n in numbers.split(",") if n.strip().isdigit()
        ]
        if not number_list:
            return PRListResponse(results=[], total=0)
        select_cols = [PullRequest, waiting_since_col, _last_human_commenter_subquery()]
        if annotation_cols:
            select_cols.extend(annotation_cols)
        stmt = (
            select(*select_cols)
            .outerjoin(
                PRLabelHistory,
                and_(
                    PRLabelHistory.pr_number == PullRequest.number,
                    PRLabelHistory.label_name == "review-requested",
                ),
            )
            .where(
                PullRequest.state == "open",
                PullRequest.number.in_(number_list),
            )
            .order_by(PRLabelHistory.applied_at.asc().nullslast())
        )
        rows = db.execute(stmt).all()
        results = [_to_pr_response(row[0], row[1], db, _extract_roles(row), getattr(row, "last_commenter", None)) for row in rows]
        # COUNT using the same filters for consistency.
        total = db.scalar(
            select(func.count()).select_from(PullRequest).where(
                PullRequest.state == "open",
                PullRequest.number.in_(number_list),
            )
        ) or 0
        last_updated = db.scalar(
            select(func.max(PullRequest.updated_at)).where(PullRequest.state == "open")
        )
        return PRListResponse(results=results, total=total, last_updated_at=last_updated)

    # Build the base WHERE conditions (reused for both COUNT and data queries).
    base_conditions = [PullRequest.state == "open"]

    if status == "needs_review":
        base_conditions.append(_needs_review_filter())
    elif status == "blocked":
        base_conditions.append(_blocked_filter())

    if team:
        base_conditions.append(_has_label(team))

    # Role filter: only PRs where the user holds at least one requested role.
    role_condition = None
    if username and role_list:
        role_conditions = []
        if "author" in role_list:
            role_conditions.append(PullRequest.author == username)
        if "reviewer" in role_list:
            role_conditions.append(
                exists(select(PRReview.id).where(
                    PRReview.pr_number == PullRequest.number,
                    PRReview.reviewer == username,
                ))
            )
        if "commenter" in role_list:
            role_conditions.append(
                exists(select(PRReviewComment.id).where(
                    PRReviewComment.pr_number == PullRequest.number,
                    PRReviewComment.commenter == username,
                ))
            )
        if role_conditions:
            role_condition = or_(*role_conditions)

    if role_condition is not None:
        base_conditions.append(role_condition)

    if unreviewed:
        base_conditions.append(_no_human_formal_review_filter())

    # COUNT query — same filters, no limit/offset.
    total = db.scalar(
        select(func.count()).select_from(PullRequest).where(*base_conditions)
    ) or 0

    # Data query — add annotation columns and paginate.
    select_cols = [PullRequest, waiting_since_col, _last_human_commenter_subquery()]
    if annotation_cols:
        select_cols.extend(annotation_cols)

    stmt = (
        select(*select_cols)
        .outerjoin(
            PRLabelHistory,
            and_(
                PRLabelHistory.pr_number == PullRequest.number,
                PRLabelHistory.label_name == "review-requested",
            ),
        )
        .where(*base_conditions)
        .order_by(PRLabelHistory.applied_at.asc().nullslast())
        .limit(limit)
        .offset(offset)
    )

    rows = db.execute(stmt).all()
    results = [_to_pr_response(row[0], row[1], db, _extract_roles(row), getattr(row, "last_commenter", None)) for row in rows]
    last_updated = db.scalar(
        select(func.max(PullRequest.updated_at)).where(PullRequest.state == "open")
    )
    return PRListResponse(results=results, total=total, last_updated_at=last_updated)


@router.get("/teams", response_model=list[TeamResponse])
def list_teams(
    roles: str | None = Query(None),
    unreviewed: bool = Query(False),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all review teams with their needs-review and blocked PR counts."""
    username = current_user.github_login if current_user else None
    # Parse roles and build extra filter conditions (same logic as list_prs).
    role_list = [r.strip() for r in roles.split(",") if r.strip()] if roles else []

    extra_conditions = []
    if username and role_list:
        role_conditions = []
        if "author" in role_list:
            role_conditions.append(PullRequest.author == username)
        if "reviewer" in role_list:
            role_conditions.append(
                exists(select(PRReview.id).where(
                    PRReview.pr_number == PullRequest.number,
                    PRReview.reviewer == username,
                ))
            )
        if "commenter" in role_list:
            role_conditions.append(
                exists(select(PRReviewComment.id).where(
                    PRReviewComment.pr_number == PullRequest.number,
                    PRReviewComment.commenter == username,
                ))
            )
        if role_conditions:
            extra_conditions.append(or_(*role_conditions))

    if unreviewed:
        extra_conditions.append(_no_human_formal_review_filter())

    # Discover team labels dynamically (any label on an open PR that isn't a status label).
    team_labels = db.execute(
        select(PRLabel.label_name)
        .join(PullRequest, PRLabel.pr_number == PullRequest.number)
        .where(
            PullRequest.state == "open",
            PRLabel.label_name.in_(TEAM_LABELS),
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
                *extra_conditions,
            )
        ) or 0

        blocked = db.scalar(
            select(func.count()).select_from(PullRequest).where(
                _blocked_filter(),
                _has_label(team_name),
                *extra_conditions,
            )
        ) or 0

        results.append(TeamResponse(
            name=team_name,
            needs_review_count=needs_review,
            blocked_count=blocked,
        ))

    return results


@router.get("/stats", response_model=StatsResponse)
def get_stats(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
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
    by_team = list_teams(current_user=current_user, db=db)

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
        WITH ranked_reviews AS (
            SELECT
                r.reviewer,
                r.reviewer_type,
                r.pr_number,
                r.state,
                r.submitted_at,
                ROW_NUMBER() OVER (
                    PARTITION BY r.pr_number, r.reviewer
                    ORDER BY r.submitted_at DESC
                ) AS rn
            FROM pr_reviews r
            JOIN pull_requests p ON p.number = r.pr_number
            WHERE r.state IN ('APPROVED', 'CHANGES_REQUESTED', 'COMMENTED')
              AND r.submitted_at >= :cutoff
              AND r.reviewer != p.author
              {team_subquery}
        ),
        latest_review_states AS (
            SELECT reviewer, reviewer_type, pr_number, state, submitted_at
            FROM ranked_reviews
            WHERE rn = 1
        ),
        effective_reviews AS (
            SELECT reviewer, reviewer_type, pr_number, state, submitted_at FROM latest_review_states
        ),
        review_stats AS (
            SELECT
                reviewer                                                                AS login,
                reviewer_type,
                COUNT(*) FILTER (WHERE state IN ('APPROVED', 'CHANGES_REQUESTED', 'COMMENTED'))     AS formal_reviews,
                COUNT(*) FILTER (WHERE state = 'APPROVED')                             AS approved,
                COUNT(*) FILTER (WHERE state = 'CHANGES_REQUESTED')                    AS changes_requested,
                COUNT(*) FILTER (WHERE state = 'COMMENTED')                            AS commented_reviews,
                MAX(submitted_at)                                                       AS last_review_at
            FROM effective_reviews
            GROUP BY reviewer, reviewer_type
        )
        SELECT
            r.login                                                  AS login,
            r.reviewer_type                                 AS reviewer_type,
            COALESCE(r.formal_reviews, 0)                                               AS formal_reviews,
            COALESCE(r.approved, 0)                                                     AS approved,
            COALESCE(r.changes_requested, 0)                                            AS changes_requested,
            COALESCE(r.commented_reviews, 0)            AS review_comments,
            r.last_review_at                              AS last_active
        FROM review_stats r
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
