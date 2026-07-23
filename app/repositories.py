from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Actor,
    Customer,
    Ticket,
    TicketCategory,
    TicketEvent,
    TicketPriority,
    TicketStatus,
)


class TicketRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, ticket: Ticket) -> Ticket:
        self.db.add(ticket)
        self.db.flush()
        return ticket

    def add_event(self, event: TicketEvent) -> None:
        self.db.add(event)

    def get_customer_by_email(self, email: str) -> Customer | None:
        statement = (
            select(Customer)
            .join(Customer.actor)
            .where(Customer.email == email)
            .options(selectinload(Customer.actor))
        )
        return self.db.scalar(statement)

    def get_actor_by_reference(self, reference: str) -> Actor | None:
        return self.db.scalar(select(Actor).where(Actor.external_reference == reference))

    def get(self, ticket_id: int, include_events: bool = False) -> Ticket | None:
        statement: Select[tuple[Ticket]] = select(Ticket).where(Ticket.id == ticket_id)
        if include_events:
            statement = statement.options(
                selectinload(Ticket.customer).selectinload(Customer.actor),
                selectinload(Ticket.events).selectinload(TicketEvent.actor),
            )
        else:
            statement = statement.options(
                selectinload(Ticket.customer).selectinload(Customer.actor)
            )
        return self.db.scalar(statement)

    def list(
        self, page: int, page_size: int, status: TicketStatus | None,
        priority: TicketPriority | None, category: TicketCategory | None,
    ) -> tuple[list[Ticket], int]:
        filters = []
        if status:
            filters.append(Ticket.status == status)
        if priority:
            filters.append(Ticket.priority == priority)
        if category:
            filters.append(Ticket.category == category)
        statement = (
            select(Ticket)
            .where(*filters)
            .options(selectinload(Ticket.customer).selectinload(Customer.actor))
            .order_by(Ticket.created_at.desc())
        )
        items = list(self.db.scalars(statement.offset((page - 1) * page_size).limit(page_size)))
        total = self.db.scalar(select(func.count()).select_from(Ticket).where(*filters)) or 0
        return items, total
