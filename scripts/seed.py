"""Idempotent local seed data. Run after `alembic upgrade head`."""
from app.db import SessionLocal
from app.models import Ticket, TicketCategory, TicketPriority
from app.schemas import TicketCreate
from app.services import TicketService


def main() -> None:
    db = SessionLocal()
    try:
        if db.query(Ticket).count():
            print("Seed skipped: tickets already exist")
            return
        ticket = TicketService(db).create_ticket(
            TicketCreate(
            customer_name="Ava Sharma",
            customer_email="ava@gmail.com",
            subject="Card payment pending",
            description="My card payment has been pending for more than 24 hours.",
            priority=TicketPriority.HIGH,
            category=TicketCategory.PAYMENT,
            )
        )
        print(f"Created ticket #{ticket.id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
