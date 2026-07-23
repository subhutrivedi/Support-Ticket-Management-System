"""initial ticketing schema

Revision ID: 202607220001
Revises:
Create Date: 2026-07-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "202607220001"
down_revision = None
branch_labels = None
depends_on = None

ticket_status = postgresql.ENUM(
    "OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED", name="ticket_status", create_type=False
)
ticket_priority = postgresql.ENUM(
    "LOW", "MEDIUM", "HIGH", "URGENT", name="ticket_priority", create_type=False
)
ticket_category = postgresql.ENUM(
    "ACCOUNT", "BILLING", "CARD", "PAYMENT", "TECHNICAL", "OTHER",
    name="ticket_category",
    create_type=False,
)


def upgrade() -> None:
    ticket_status.create(op.get_bind(), checkfirst=True)
    ticket_priority.create(op.get_bind(), checkfirst=True)
    ticket_category.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_name", sa.String(120), nullable=False),
        sa.Column("customer_email", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", ticket_priority, nullable=False),
        sa.Column("category", ticket_category, nullable=False),
        sa.Column("status", ticket_status, nullable=False, server_default="OPEN"),
        sa.Column("processing_summary", sa.Text()),
        sa.Column("assigned_department", sa.String(80)),
        sa.Column("spam_score", sa.Integer()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_tickets_customer_email", "tickets", ["customer_email"])
    op.create_index("ix_tickets_status_created_at", "tickets", ["status", "created_at"])
    op.create_index("ix_tickets_priority_created_at", "tickets", ["priority", "created_at"])
    op.create_index("ix_tickets_category_created_at", "tickets", ["category", "created_at"])
    op.create_table(
        "ticket_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("from_status", ticket_status),
        sa.Column("to_status", ticket_status),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("metadata_json", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_ticket_events_ticket_id_created_at",
        "ticket_events",
        ["ticket_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("ticket_events")
    op.drop_table("tickets")
    ticket_category.drop(op.get_bind(), checkfirst=True)
    ticket_priority.drop(op.get_bind(), checkfirst=True)
    ticket_status.drop(op.get_bind(), checkfirst=True)
