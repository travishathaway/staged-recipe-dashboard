"""SQLAlchemy 2.x ORM models."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
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
