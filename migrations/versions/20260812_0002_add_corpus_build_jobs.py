"""Add privacy-minimized local corpus-build job state.

Revision ID: 20260812_0002
Revises: 20260801_0001
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0002"
down_revision: str | None = "20260801_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create durable job state without storing paths, filenames, or content."""
    op.create_table(
        "corpus_build_jobs",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=True),
        sa.Column("input_file_count", sa.Integer(), nullable=False),
        sa.Column("corpus_revision_id", sa.String(length=39), nullable=True),
        sa.Column("index_revision_id", sa.String(length=38), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_corpus_build_jobs_status",
        ),
        sa.CheckConstraint(
            "input_file_count BETWEEN 1 AND 10",
            name="ck_corpus_build_jobs_file_count",
        ),
        sa.ForeignKeyConstraint(
            ["corpus_revision_id"],
            ["corpus_revisions.corpus_revision_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["index_revision_id"],
            ["index_revisions.index_revision_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index(
        "ix_corpus_build_jobs_created_at",
        "corpus_build_jobs",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove only the project-owned corpus-build job table."""
    op.drop_index("ix_corpus_build_jobs_created_at", table_name="corpus_build_jobs")
    op.drop_table("corpus_build_jobs")
