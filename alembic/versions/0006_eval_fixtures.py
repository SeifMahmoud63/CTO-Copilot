"""Synthetic eval fixtures table (clearly-fake rows for torture tests).

Revision ID: 0006_eval_fixtures
Revises: 0005_email_dismiss
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_eval_fixtures"
down_revision = "0005_email_dismiss"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eval_fixtures",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("ref_name", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("state", sa.String(length=50), nullable=True),
        sa.Column("event_date", sa.DateTime(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("tier", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_eval_fixtures_kind"), "eval_fixtures", ["kind"], unique=False)
    op.create_index(op.f("ix_eval_fixtures_ref_name"), "eval_fixtures", ["ref_name"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_eval_fixtures_ref_name"), table_name="eval_fixtures")
    op.drop_index(op.f("ix_eval_fixtures_kind"), table_name="eval_fixtures")
    op.drop_table("eval_fixtures")
