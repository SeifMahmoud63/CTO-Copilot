"""Initial 2-table schema: pull_requests + engineers.

Revision ID: 0001_initial_two_tables
Revises: None
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_two_tables"
down_revision = None
branch_labels = None
depends_on = None

LEGACY_TABLES = ("pr_summaries", "pr_impact_scores", "pr_approvals", "audit_logs")


def upgrade() -> None:
    op.create_table(
        "pull_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("github_pr_id", sa.BigInteger(), nullable=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("author", sa.String(length=100), nullable=False),
        sa.Column("author_avatar", sa.String(length=500), nullable=True),
        sa.Column("state", sa.String(length=50), nullable=False, server_default="open"),
        sa.Column("head_branch", sa.String(length=150), nullable=False),
        sa.Column("base_branch", sa.String(length=150), nullable=False),
        sa.Column("html_url", sa.String(length=500), nullable=False),
        sa.Column("diff_url", sa.String(length=500), nullable=True),
        sa.Column("is_overdue", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("overdue_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("summary_provider", sa.String(length=50), nullable=True),
        sa.Column("summary_timestamp", sa.DateTime(), nullable=True),
        sa.Column("impact_score", sa.Float(), nullable=True),
        sa.Column("impact_tier", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pull_requests_number", "pull_requests", ["number"], unique=True)
    op.create_index("ix_pull_requests_author", "pull_requests", ["author"], unique=False)
    op.create_index("ix_pull_requests_state", "pull_requests", ["state"], unique=False)
    op.create_index("ix_pull_requests_is_overdue", "pull_requests", ["is_overdue"], unique=False)

    op.create_table(
        "engineers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("author", sa.String(length=100), nullable=False),
        sa.Column("author_avatar", sa.String(length=500), nullable=True),
        sa.Column("pr_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tier", sa.String(length=50), nullable=False, server_default="Routine Support"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_engineers_author", "engineers", ["author"], unique=True)

    # Converge databases coming from the old 5-table schema.
    for legacy in LEGACY_TABLES:
        op.execute(sa.text(f"DROP TABLE IF EXISTS {legacy}"))


def downgrade() -> None:
    op.drop_index("ix_engineers_author", table_name="engineers")
    op.drop_table("engineers")
    op.drop_index("ix_pull_requests_is_overdue", table_name="pull_requests")
    op.drop_index("ix_pull_requests_state", table_name="pull_requests")
    op.drop_index("ix_pull_requests_author", table_name="pull_requests")
    op.drop_index("ix_pull_requests_number", table_name="pull_requests")
    op.drop_table("pull_requests")
