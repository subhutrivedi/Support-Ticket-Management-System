import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import TicketCategory, TicketPriority, TicketStatus
from app.schemas import TicketCreate
from app.services import TicketService


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_create_ticket_creates_audit_event(db: Session) -> None:
    ticket = TicketService(db).create_ticket(TicketCreate(customer_name="Jane Doe", customer_email="jane@example.com", subject="Cannot see payout", description="My payout has not appeared in my account yet.", priority=TicketPriority.HIGH, category=TicketCategory.PAYMENT))
    stored = TicketService(db).get_ticket(ticket.id, include_events=True)
    assert stored.status is TicketStatus.OPEN
    assert len(stored.events) == 1
    assert stored.events[0].event_type == "CREATED"


def test_rejects_invalid_transition(db: Session) -> None:
    service = TicketService(db)
    ticket = service.create_ticket(TicketCreate(customer_name="Jane Doe", customer_email="jane@example.com", subject="Cannot see payout", description="My payout has not appeared in my account yet.", category=TicketCategory.PAYMENT))
    with pytest.raises(HTTPException, match="Invalid transition"):
        service.update_status(ticket.id, TicketStatus.RESOLVED, "agent:alice")


def test_processing_enriches_ticket(db: Session) -> None:
    service = TicketService(db)
    ticket = service.create_ticket(TicketCreate(customer_name="Jane Doe", customer_email="jane@example.com", subject="Need payment help", description="I need help finding a completed bank payment.", category=TicketCategory.PAYMENT))
    service.process_ticket(ticket.id)
    processed = service.get_ticket(ticket.id, include_events=True)
    assert processed.assigned_department == "payments"
    assert processed.processing_summary is not None
    assert any(event.event_type == "AUTO_PROCESSED" for event in processed.events)
