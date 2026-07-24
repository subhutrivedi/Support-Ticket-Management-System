from sqlalchemy.orm import Session

from app.core.errors import InvalidStateTransitionError, ResourceNotFoundError
from app.models import (
    Actor,
    ActorType,
    Agent,
    Customer,
    OutboxMessage,
    Ticket,
    TicketCategory,
    TicketEvent,
    TicketPriority,
    TicketStatus,
)
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
        customer = self._get_or_create_customer(payload.customer_name, str(payload.customer_email))
        ticket_data = payload.model_dump(exclude={"customer_name", "customer_email"})
        ticket = self.repo.create(Ticket(customer_id=customer.id, **ticket_data))
        self.repo.add_event(
            TicketEvent(
                ticket_id=ticket.id,
                event_type="CREATED",
                to_status=TicketStatus.OPEN,
                actor_id=customer.id,
                actor_type=ActorType.CUSTOMER,
            )
        )
        self.db.add(OutboxMessage(ticket_id=ticket.id, topic="ticket.process"))
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def _get_or_create_customer(self, name: str, email: str) -> Customer:
        normalized_email = email.lower()
        customer = self.repo.get_customer_by_email(normalized_email)
        if customer:
            if customer.actor.display_name != name:
                customer.actor.display_name = name
            return customer

        actor = Actor(
            actor_type=ActorType.CUSTOMER,
            display_name=name,
            external_reference=f"customer:{normalized_email}",
        )
        self.db.add(actor)
        self.db.flush()
        customer = Customer(id=actor.id, email=normalized_email)
        self.db.add(customer)
        self.db.flush()
        return customer

    def _get_or_create_agent(self, reference: str) -> Agent:
        actor = self.repo.get_actor_by_reference(reference)
        if actor:
            if (
                actor.actor_type is not ActorType.AGENT
                or not actor.agent
                or not actor.agent.is_active
            ):
                raise InvalidStateTransitionError("Actor is not an active agent")
            return actor.agent

        actor = Actor(
            actor_type=ActorType.AGENT,
            display_name=reference,
            external_reference=reference,
        )
        self.db.add(actor)
        self.db.flush()
        agent = Agent(id=actor.id)
        self.db.add(agent)
        self.db.flush()
        return agent

    def get_ticket(self, ticket_id: int, include_events: bool = False) -> Ticket:
        ticket = self.repo.get(ticket_id, include_events)
        if not ticket:
            raise ResourceNotFoundError(f"Ticket {ticket_id} was not found")
        return ticket

    def update_status(self, ticket_id: int, next_status: TicketStatus, actor: str) -> Ticket:
        ticket = self.get_ticket(ticket_id)
        if next_status == ticket.status:
            raise InvalidStateTransitionError("Ticket is already in the requested status")
        if next_status not in ALLOWED_TRANSITIONS[ticket.status]:
            raise InvalidStateTransitionError(
                f"Invalid transition: {ticket.status.value} -> {next_status.value}"
            )
        previous_status = ticket.status
        agent = self._get_or_create_agent(actor)
        ticket.status = next_status
        self.repo.add_event(
            TicketEvent(
                ticket_id=ticket.id,
                event_type="STATUS_CHANGED",
                from_status=previous_status,
                to_status=next_status,
                actor_id=agent.id,
                actor_type=ActorType.AGENT,
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
