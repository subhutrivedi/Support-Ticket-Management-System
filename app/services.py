import json

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Ticket, TicketCategory, TicketEvent, TicketPriority, TicketStatus
from app.repositories import TicketRepository
from app.schemas import TicketCreate

ALLOWED_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.OPEN: {TicketStatus.IN_PROGRESS, TicketStatus.CLOSED},
    TicketStatus.IN_PROGRESS: {TicketStatus.RESOLVED, TicketStatus.CLOSED},
    TicketStatus.RESOLVED: {TicketStatus.CLOSED, TicketStatus.IN_PROGRESS},
    TicketStatus.CLOSED: set(),
}


class TicketService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = TicketRepository(db)

    def create_ticket(self, payload: TicketCreate) -> Ticket:
        ticket = self.repo.create(Ticket(**payload.model_dump()))
        self.repo.add_event(
            TicketEvent(
                ticket_id=ticket.id,
                event_type="CREATED",
                to_status=TicketStatus.OPEN,
                actor="customer",
            )
        )
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def get_ticket(self, ticket_id: int, include_events: bool = False) -> Ticket:
        ticket = self.repo.get(ticket_id, include_events)
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket {ticket_id} was not found",
            )
        return ticket

    def update_status(self, ticket_id: int, next_status: TicketStatus, actor: str) -> Ticket:
        ticket = self.get_ticket(ticket_id)
        if next_status == ticket.status:
            raise HTTPException(
                status_code=422, detail="Ticket is already in the requested status"
            )
        if next_status not in ALLOWED_TRANSITIONS[ticket.status]:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid transition: {ticket.status.value} -> {next_status.value}",
            )
        previous_status = ticket.status
        ticket.status = next_status
        self.repo.add_event(
            TicketEvent(
                ticket_id=ticket.id,
                event_type="STATUS_CHANGED",
                from_status=previous_status,
                to_status=next_status,
                actor=actor,
            )
        )
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def list_tickets(
        self,
        page: int,
        page_size: int,
        status: TicketStatus | None,
        priority: TicketPriority | None,
        category: TicketCategory | None,
    ) -> tuple[list[Ticket], int]:
        return self.repo.list(page, page_size, status, priority, category)

    def process_ticket(self, ticket_id: int) -> None:
        ticket = self.get_ticket(ticket_id)
        routing = {
            TicketCategory.BILLING: "payments",
            TicketCategory.PAYMENT: "payments",
            TicketCategory.CARD: "card-operations",
            TicketCategory.ACCOUNT: "identity",
            TicketCategory.TECHNICAL: "platform",
            TicketCategory.OTHER: "general-support",
        }
        ticket.assigned_department = routing[ticket.category]
        is_suspicious = "http" in ticket.description.lower() and "urgent" in ticket.subject.lower()
        ticket.spam_score = 90 if is_suspicious else 3
        ticket.processing_summary = (
            f"{ticket.subject[:100]}. Routed to {ticket.assigned_department}; "
            f"automated spam score: {ticket.spam_score}."
        )
        self.repo.add_event(
            TicketEvent(
                ticket_id=ticket.id,
                event_type="AUTO_PROCESSED",
                actor="worker:ticket-processor",
                metadata_json=json.dumps(
                    {"department": ticket.assigned_department, "spam_score": ticket.spam_score}
                ),
            )
        )
        self.db.commit()
