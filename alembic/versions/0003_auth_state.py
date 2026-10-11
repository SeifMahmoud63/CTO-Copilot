"""Access-gate state table (TOTP enrollment).

Revision ID: 0003_auth_state
Revises: 0002_daily_reports
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_auth_state"
down_revision = "0002_daily_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_state",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("totp_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("totp_enrolled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("auth_state")
