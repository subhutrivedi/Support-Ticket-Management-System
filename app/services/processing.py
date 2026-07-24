import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import ResourceNotFoundError
from app.models import (
    Actor,
    ActorType,
    DeadLetterMessage,
    ProcessingStatus,
    Ticket,
    TicketCategory,
    TicketEvent,
)
from app.repositories import TicketRepository


class ProcessingService:
    """Owns the asynchronous ticket-processing lifecycle and its durable state."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = TicketRepository(db)

    def _get_ticket(self, ticket_id: int) -> Ticket:
        ticket = self.repo.get(ticket_id)
        if not ticket:
            raise ResourceNotFoundError(f"Ticket {ticket_id} was not found")
        return ticket

    def _get_or_create_system_actor(self, reference: str) -> Actor:
        actor = self.repo.get_actor_by_reference(reference)
        if actor:
            if actor.actor_type is not ActorType.SYSTEM:
                raise RuntimeError(f"Actor reference {reference} is not a system actor")
            return actor
        actor = Actor(
            actor_type=ActorType.SYSTEM,
            display_name=reference,
            external_reference=reference,
        )
        self.db.add(actor)
        self.db.flush()
        return actor

    def begin(self, ticket_id: int, task_id: str) -> bool:
        ticket = self._get_ticket(ticket_id)
        if ticket.processing_status in {ProcessingStatus.COMPLETED, ProcessingStatus.PROCESSING}:
            return False
        ticket.processing_status = ProcessingStatus.PROCESSING
        ticket.processing_task_id = task_id
        ticket.processing_attempts += 1
        ticket.processing_error = None
        ticket.processing_started_at = datetime.now(UTC)
        self.db.commit()
        return True

    def fail(self, ticket_id: int, task_id: str, error: Exception, retrying: bool) -> None:
        ticket = self._get_ticket(ticket_id)
        if (
            ticket.processing_task_id != task_id
            or ticket.processing_status is ProcessingStatus.COMPLETED
        ):
            return
        ticket.processing_status = ProcessingStatus.PENDING if retrying else ProcessingStatus.FAILED
        ticket.processing_error = str(error)[:1000]
        if not retrying:
            self.db.add(
                DeadLetterMessage(
                    ticket_id=ticket.id,
                    task_id=task_id,
                    error=ticket.processing_error,
                    attempts=ticket.processing_attempts,
                )
            )
        self.db.commit()

    def complete(self, ticket_id: int, task_id: str) -> None:
        ticket = self._get_ticket(ticket_id)
        if (
            ticket.processing_status is not ProcessingStatus.PROCESSING
            or ticket.processing_task_id != task_id
        ):
            return
        actor = self._get_or_create_system_actor("worker:ticket-processor")
        routing = {
            TicketCategory.BILLING: "payments",
            TicketCategory.PAYMENT: "payments",
            TicketCategory.CARD: "card-operations",
            TicketCategory.ACCOUNT: "identity",
            TicketCategory.TECHNICAL: "platform",
            TicketCategory.OTHER: "general-support",
        }
        ticket.assigned_department = routing[ticket.category]
        ticket.spam_score = (
            90 if "http" in ticket.description.lower() and "urgent" in ticket.subject.lower() else 3
        )
        ticket.processing_summary = (
            f"{ticket.subject[:100]}. Routed to {ticket.assigned_department}; "
            f"automated spam score: {ticket.spam_score}."
        )
        ticket.processing_status = ProcessingStatus.COMPLETED
        ticket.processing_completed_at = datetime.now(UTC)
        self.repo.add_event(
            TicketEvent(
                ticket_id=ticket.id,
                event_type="AUTO_PROCESSED",
                actor_id=actor.id,
                actor_type=ActorType.SYSTEM,
                metadata_json=json.dumps(
                    {"department": ticket.assigned_department, "spam_score": ticket.spam_score}
                ),
            )
        )
        self.db.commit()
