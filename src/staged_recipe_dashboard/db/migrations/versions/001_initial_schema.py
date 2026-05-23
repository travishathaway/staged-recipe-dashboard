"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pull_requests",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("html_url", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data", JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )
    op.create_index("idx_pr_state", "pull_requests", ["state"])
    op.create_index("idx_pr_author", "pull_requests", ["author"])
    op.create_index("idx_pr_created_at", "pull_requests", ["created_at"])

    op.create_table(
        "pr_labels",
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("label_name", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["pr_number"], ["pull_requests.number"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("pr_number", "label_name"),
    )
    op.create_index("idx_label_name", "pr_labels", ["label_name"])

    op.create_table(
        "pr_label_history",
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("label_name", sa.String(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pr_number"], ["pull_requests.number"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("pr_number", "label_name"),
    )
    op.create_index("idx_history_label", "pr_label_history", ["label_name"])


def downgrade() -> None:
    op.drop_table("pr_label_history")
    op.drop_table("pr_labels")
    op.drop_table("pull_requests")
