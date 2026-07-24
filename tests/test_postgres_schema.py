import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models import DeadLetterMessage, ProcessingStatus, TicketCategory
from app.schemas import TicketCreate
from app.services import ProcessingService, TicketService

pytestmark = pytest.mark.skipif(
    not os.getenv("POSTGRES_INTEGRATION_URL"),
    reason="requires the PostgreSQL integration database",
)


def create_ticket(db: Session):
    identifier = uuid4().hex
    return TicketService(db).create_ticket(
        TicketCreate(
            customer_name="PostgreSQL Integration Test",
            customer_email=f"integration-{identifier}@example.com",
            subject="Verify durable ticket processing",
            description="This ticket exercises PostgreSQL-only integration guarantees.",
            category=TicketCategory.TECHNICAL,
        )
    )


def test_postgres_migrations_create_required_schema() -> None:
    engine = create_engine(os.environ["POSTGRES_INTEGRATION_URL"])
    inspector = inspect(engine)

    assert {"tickets", "ticket_events", "outbox_messages", "dead_letter_messages"} <= set(
        inspector.get_table_names()
    )
    with engine.connect() as connection:
        trigger_names = {
            trigger["name"]
            for trigger in connection.execute(
                text("SELECT tgname AS name FROM pg_trigger WHERE NOT tgisinternal")
            ).mappings()
        }
    assert "ticket_events_append_only" in trigger_names


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE ticket_events SET metadata_json = '{}' WHERE id = :event_id",
        "DELETE FROM ticket_events WHERE id = :event_id",
    ],
)
def test_postgres_rejects_ticket_event_mutation(statement: str) -> None:
    engine = create_engine(os.environ["POSTGRES_INTEGRATION_URL"])
    with Session(engine) as db:
        ticket = create_ticket(db)
        event_id = db.scalar(
            text("SELECT id FROM ticket_events WHERE ticket_id = :ticket_id"),
            {"ticket_id": ticket.id},
        )

    with engine.connect() as connection:
        with pytest.raises(DBAPIError, match="append-only"):
            connection.execute(text(statement), {"event_id": event_id})
        connection.rollback()

    engine.dispose()


def test_postgres_duplicate_processing_creates_one_event() -> None:
    engine = create_engine(os.environ["POSTGRES_INTEGRATION_URL"])
    with Session(engine) as db:
        ticket = create_ticket(db)
        processing = ProcessingService(db)
        first_task_id = f"task-{uuid4().hex}"
        duplicate_task_id = f"task-{uuid4().hex}"

        assert processing.begin(ticket.id, first_task_id)
        assert not processing.begin(ticket.id, duplicate_task_id)
        processing.complete(ticket.id, first_task_id)
        processing.complete(ticket.id, duplicate_task_id)

        auto_processed_events = db.scalar(
            text(
                "SELECT count(*) FROM ticket_events "
                "WHERE ticket_id = :ticket_id AND event_type = 'AUTO_PROCESSED'"
            ),
            {"ticket_id": ticket.id},
        )
        assert auto_processed_events == 1

    engine.dispose()


def test_postgres_terminal_failure_persists_dead_letter_message() -> None:
    engine = create_engine(os.environ["POSTGRES_INTEGRATION_URL"])
    with Session(engine) as db:
        ticket = create_ticket(db)
        processing = ProcessingService(db)
        task_id = f"task-{uuid4().hex}"

        assert processing.begin(ticket.id, task_id)
        processing.fail(ticket.id, task_id, RuntimeError("broker timeout"), False)

        failed_ticket = TicketService(db).get_ticket(ticket.id)
        dead_letter = db.scalar(
            select(DeadLetterMessage).where(DeadLetterMessage.ticket_id == ticket.id)
        )
        assert failed_ticket.processing_status is ProcessingStatus.FAILED
        assert failed_ticket.processing_error == "broker timeout"
        assert dead_letter is not None
        assert dead_letter.task_id == task_id
        assert dead_letter.attempts == 1

    engine.dispose()
