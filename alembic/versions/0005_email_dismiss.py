"""Dismiss flag for email triage (hide from the list without deleting).

Revision ID: 0005_email_dismiss
Revises: 0004_emails
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_email_dismiss"
down_revision = "0004_emails"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "emails",
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("emails", "is_hidden")
