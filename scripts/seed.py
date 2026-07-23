"""Idempotent-ish local seed data. Run after `alembic upgrade head`."""
from app.db import SessionLocal
from app.models import Ticket, TicketCategory, TicketEvent, TicketPriority, TicketStatus


def main() -> None:
    db = SessionLocal()
    try:
        if db.query(Ticket).count():
            print("Seed skipped: tickets already exist")
            return
        ticket = Ticket(customer_name="Ava Sharma", customer_email="ava@example.com", subject="Card payment pending", description="My card payment has been pending for more than 24 hours.", priority=TicketPriority.HIGH, category=TicketCategory.PAYMENT, status=TicketStatus.OPEN)
        db.add(ticket)
        db.flush()
        db.add(TicketEvent(ticket_id=ticket.id, event_type="CREATED", to_status=TicketStatus.OPEN, actor="seed"))
        db.commit()
        print(f"Created ticket #{ticket.id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
