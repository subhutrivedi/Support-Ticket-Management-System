"""Persist idempotent worker-processing lifecycle state.

Revision ID: 202607230005
Revises: 202607230004
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "202607230005"
down_revision = "202607230004"
branch_labels = None
depends_on = None

processing_status = postgresql.ENUM(
    "PENDING", "PROCESSING", "COMPLETED", "FAILED", name="processing_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    processing_status.create(bind, checkfirst=True)
    op.add_column(
        "tickets",
        sa.Column("processing_status", processing_status, nullable=False, server_default="PENDING"),
    )
    op.add_column(
        "tickets",
        sa.Column("processing_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("tickets", sa.Column("processing_error", sa.Text()))
    op.add_column("tickets", sa.Column("processing_task_id", sa.String(50), unique=True))
    op.add_column("tickets", sa.Column("processing_started_at", sa.DateTime(timezone=True)))
    op.add_column("tickets", sa.Column("processing_completed_at", sa.DateTime(timezone=True)))
    op.create_check_constraint(
        "ck_tickets_processing_attempts_nonnegative", "tickets", "processing_attempts >= 0"
    )
    op.create_index("ix_tickets_processing_status", "tickets", ["processing_status"])


def downgrade() -> None:
    op.drop_index("ix_tickets_processing_status", table_name="tickets")
    op.drop_constraint("ck_tickets_processing_attempts_nonnegative", "tickets", type_="check")
    op.drop_column("tickets", "processing_completed_at")
    op.drop_column("tickets", "processing_started_at")
    op.drop_column("tickets", "processing_task_id")
    op.drop_column("tickets", "processing_error")
    op.drop_column("tickets", "processing_attempts")
    op.drop_column("tickets", "processing_status")
    processing_status.drop(op.get_bind(), checkfirst=True)
