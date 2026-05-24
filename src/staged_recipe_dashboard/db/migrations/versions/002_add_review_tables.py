"""add review tables

Revision ID: 002
Revises: 001
Create Date: 2026-05-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pr_reviews",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("reviewer", sa.String(), nullable=False),
        sa.Column("reviewer_type", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["pr_number"], ["pull_requests.number"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_pr_reviews_pr_number", "pr_reviews", ["pr_number"])
    op.create_index("idx_pr_reviews_reviewer", "pr_reviews", ["reviewer"])
    op.create_index("idx_pr_reviews_submitted_at", "pr_reviews", ["submitted_at"])

    op.create_table(
        "pr_review_comments",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("commenter", sa.String(), nullable=False),
        sa.Column("commenter_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["pr_number"], ["pull_requests.number"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_pr_review_comments_pr_number", "pr_review_comments", ["pr_number"])
    op.create_index("idx_pr_review_comments_commenter", "pr_review_comments", ["commenter"])
    op.create_index("idx_pr_review_comments_created_at", "pr_review_comments", ["created_at"])


def downgrade() -> None:
    op.drop_table("pr_review_comments")
    op.drop_table("pr_reviews")
