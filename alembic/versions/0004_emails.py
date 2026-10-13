"""Email triage table (inbox polling + AI summaries + urgency scores).

Revision ID: 0004_emails
Revises: 0003_auth_state
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_emails"
down_revision = "0003_auth_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "emails",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.String(length=500), nullable=False),
        sa.Column("sender", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("snippet", sa.String(length=500), nullable=True),
        sa.Column("body_excerpt", sa.Text(), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("summary_provider", sa.String(length=50), nullable=True),
        sa.Column("urgency_score", sa.Float(), nullable=True),
        sa.Column("urgency_tier", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_emails_message_id"), "emails", ["message_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_emails_message_id"), table_name="emails")
    op.drop_table("emails")
