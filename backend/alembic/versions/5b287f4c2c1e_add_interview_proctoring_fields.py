
"""add interview proctoring fields

Revision ID: 5b287f4c2c1e
Revises: 55d9e3267298
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5b287f4c2c1e"
down_revision: Union[str, Sequence[str], None] = "55d9e3267298"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "interviews",
        sa.Column(
            "tab_switch_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.add_column(
        "interviews",
        sa.Column(
            "proctoring_paused",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.add_column(
        "interviews",
        sa.Column(
            "proctoring_events",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("interviews", "proctoring_events")
    op.drop_column("interviews", "proctoring_paused")
    op.drop_column("interviews", "tab_switch_count")
