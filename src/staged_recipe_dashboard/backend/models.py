"""SQLAlchemy 2.x ORM models."""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[str | None] = mapped_column(String)
    title: Mapped[str | None] = mapped_column(String)
    html_url: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)

    labels: Mapped[list["PRLabel"]] = relationship(
        back_populates="pr", cascade="all, delete-orphan"
    )
    label_history: Mapped[list["PRLabelHistory"]] = relationship(
        back_populates="pr", cascade="all, delete-orphan"
    )


class PRLabel(Base):
    __tablename__ = "pr_labels"

    pr_number: Mapped[int] = mapped_column(
        ForeignKey("pull_requests.number", ondelete="CASCADE"), primary_key=True
    )
    label_name: Mapped[str] = mapped_column(String, primary_key=True)

    pr: Mapped["PullRequest"] = relationship(back_populates="labels")


class PRLabelHistory(Base):
    __tablename__ = "pr_label_history"

    pr_number: Mapped[int] = mapped_column(
        ForeignKey("pull_requests.number", ondelete="CASCADE"), primary_key=True
    )
    label_name: Mapped[str] = mapped_column(String, primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    pr: Mapped["PullRequest"] = relationship(back_populates="label_history")


class PRReview(Base):
    __tablename__ = "pr_reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pr_number: Mapped[int] = mapped_column(
        ForeignKey("pull_requests.number", ondelete="CASCADE"), nullable=False
    )
    reviewer: Mapped[str] = mapped_column(String, nullable=False)
    reviewer_type: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PRReviewComment(Base):
    __tablename__ = "pr_review_comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pr_number: Mapped[int] = mapped_column(
        ForeignKey("pull_requests.number", ondelete="CASCADE"), nullable=False
    )
    commenter: Mapped[str] = mapped_column(String, nullable=False)
    commenter_type: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    github_login: Mapped[str] = mapped_column(String, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    preferences: Mapped[list["UserPreference"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserSession(Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String, primary_key=True)  # 32-byte random hex
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="sessions")


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    pref_type: Mapped[str] = mapped_column(String, primary_key=True)  # 'starred' | 'ignored' | 'note'
    pr_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict | None] = mapped_column(JSONB)  # null for starred/ignored; {"text": "..."} for note

    user: Mapped["User"] = relationship(back_populates="preferences")
