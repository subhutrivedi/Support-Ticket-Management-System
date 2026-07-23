"""Add durable outbox and dead-letter storage.

Revision ID: 202607230006
Revises: 202607230005
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "202607230006"
down_revision = "202607230005"
branch_labels = None
depends_on = None

outbox_status = postgresql.ENUM(
    "PENDING", "PUBLISHED", name="outbox_status", create_type=False
)


def upgrade() -> None:
    outbox_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "outbox_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("topic", sa.String(80), nullable=False),
        sa.Column("status", outbox_status, nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_outbox_messages_pending", "outbox_messages", ["status", "created_at"])
    op.create_table(
        "dead_letter_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("tickets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("task_id", sa.String(50), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("dead_letter_messages")
    op.drop_index("ix_outbox_messages_pending", table_name="outbox_messages")
    op.drop_table("outbox_messages")
    outbox_status.drop(op.get_bind(), checkfirst=True)
