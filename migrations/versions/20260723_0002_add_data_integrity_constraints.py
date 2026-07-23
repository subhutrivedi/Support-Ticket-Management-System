"""Add database-enforced ticket and audit-event invariants.

Revision ID: 202607230002
Revises: 202607220001
Create Date: 2026-07-23
"""

from alembic import op

revision = "202607230002"
down_revision = "202607220001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_tickets_customer_name_length",
        "tickets",
        "length(trim(customer_name)) >= 2",
    )
    op.create_check_constraint(
        "ck_tickets_customer_email_format",
        "tickets",
        "customer_email = trim(customer_email) AND customer_email LIKE '%_@_%.__%'",
    )
    op.create_check_constraint(
        "ck_tickets_subject_length",
        "tickets",
        "length(trim(subject)) >= 3",
    )
    op.create_check_constraint(
        "ck_tickets_description_length",
        "tickets",
        "length(trim(description)) >= 10",
    )
    op.create_check_constraint(
        "ck_tickets_spam_score_range",
        "tickets",
        "spam_score IS NULL OR spam_score BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_tickets_processing_fields_complete",
        "tickets",
        "(processing_summary IS NULL AND assigned_department IS NULL AND spam_score IS NULL) "
        "OR (processing_summary IS NOT NULL AND assigned_department IS NOT NULL "
        "AND spam_score IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_ticket_events_actor_nonempty",
        "ticket_events",
        "length(trim(actor)) >= 1",
    )
    op.create_check_constraint(
        "ck_ticket_events_event_type",
        "ticket_events",
        "event_type IN ('CREATED', 'STATUS_CHANGED', 'AUTO_PROCESSED')",
    )
    op.create_check_constraint(
        "ck_ticket_events_status_shape",
        "ticket_events",
        "(event_type = 'CREATED' AND from_status IS NULL AND to_status = 'OPEN') "
        "OR (event_type = 'STATUS_CHANGED' AND from_status IS NOT NULL "
        "AND to_status IS NOT NULL AND from_status <> to_status) "
        "OR (event_type = 'AUTO_PROCESSED' AND from_status IS NULL AND to_status IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_ticket_events_status_shape", "ticket_events", type_="check")
    op.drop_constraint("ck_ticket_events_event_type", "ticket_events", type_="check")
    op.drop_constraint("ck_ticket_events_actor_nonempty", "ticket_events", type_="check")
    op.drop_constraint("ck_tickets_processing_fields_complete", "tickets", type_="check")
    op.drop_constraint("ck_tickets_spam_score_range", "tickets", type_="check")
    op.drop_constraint("ck_tickets_description_length", "tickets", type_="check")
    op.drop_constraint("ck_tickets_subject_length", "tickets", type_="check")
    op.drop_constraint("ck_tickets_customer_email_format", "tickets", type_="check")
    op.drop_constraint("ck_tickets_customer_name_length", "tickets", type_="check")
