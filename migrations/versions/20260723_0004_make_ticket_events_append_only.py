"""Make ticket-event audit history append-only.

Revision ID: 202607230004
Revises: 202607230003
Create Date: 2026-07-23
"""

from alembic import op

revision = "202607230004"
down_revision = "202607230003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION prevent_ticket_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'ticket_events is append-only; % is not permitted', TG_OP
                USING ERRCODE = '55000';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER ticket_events_append_only
        BEFORE UPDATE OR DELETE ON ticket_events
        FOR EACH ROW
        EXECUTE FUNCTION prevent_ticket_event_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER ticket_events_append_only ON ticket_events")
    op.execute("DROP FUNCTION prevent_ticket_event_mutation()")
