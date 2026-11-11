
"""add asked_at to interview questions

Revision ID: fd7e5b0654c3
Revises: 10ae3f39d990
"""

from alembic import op
import sqlalchemy as sa

revision = "fd7e5b0654c3"
down_revision = "10ae3f39d990"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interview_questions",
        sa.Column("asked_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("interview_questions", "asked_at")
