"""Daily CTO reports table.

Revision ID: 0002_daily_reports
Revises: 0001_initial_two_tables
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_daily_reports"
down_revision = "0001_initial_two_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("executive_summary", sa.Text(), nullable=True),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("pdf_path", sa.String(length=500), nullable=True),
        sa.Column("prs_opened", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prs_merged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prs_closed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overdue_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_daily_reports_report_date", "daily_reports", ["report_date"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_daily_reports_report_date", table_name="daily_reports")
    op.drop_table("daily_reports")
