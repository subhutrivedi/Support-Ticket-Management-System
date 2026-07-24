"""Add idempotency support for ticket creation.

Revision ID: 202607240007
Revises: 202607230006
Create Date: 2026-07-24
"""

import sqlalchemy as sa
from alembic import op

revision = "202607240007"
down_revision = "202607230006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.add_column(
        "tickets", sa.Column("idempotency_request_hash", sa.String(length=64), nullable=True)
    )
    op.create_unique_constraint("uq_tickets_idempotency_key", "tickets", ["idempotency_key"])
    op.create_check_constraint(
        "ck_tickets_idempotency_fields_complete",
        "tickets",
        "(idempotency_key IS NULL AND idempotency_request_hash IS NULL) "
        "OR (idempotency_key IS NOT NULL AND idempotency_request_hash IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tickets_idempotency_fields_complete", "tickets", type_="check")
    op.drop_constraint("uq_tickets_idempotency_key", "tickets", type_="unique")
    op.drop_column("tickets", "idempotency_request_hash")
    op.drop_column("tickets", "idempotency_key")
