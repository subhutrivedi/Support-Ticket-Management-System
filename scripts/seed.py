"""Create a deterministic, idempotent demo dataset after `alembic upgrade head`."""

from dataclasses import dataclass

from app.db import SessionLocal
from app.models import TicketCategory, TicketPriority, TicketStatus
from app.schemas import TicketCreate
from app.services import ProcessingService, TicketService


@dataclass(frozen=True)
class SeedScenario:
    key: str
    customer_name: str
    customer_email: str
    subject: str
    description: str
    priority: TicketPriority
    category: TicketCategory
    target_status: TicketStatus
    agent: str | None = None

    def payload(self) -> TicketCreate:
        return TicketCreate(
            customer_name=self.customer_name,
            customer_email=self.customer_email,
            subject=self.subject,
            description=self.description,
            priority=self.priority,
            category=self.category,
        )


SCENARIOS = (
    SeedScenario(
        "01-account-login",
        "Ava Sharma",
        "ava@example.com",
        "Unable to sign in",
        "I cannot sign in after changing to a new mobile phone.",
        TicketPriority.LOW,
        TicketCategory.ACCOUNT,
        TicketStatus.OPEN,
    ),
    SeedScenario(
        "02-billing-fee",
        "Liam Patel",
        "liam@example.com",
        "Unexpected monthly fee",
        "A monthly service fee appeared on my statement this morning.",
        TicketPriority.MEDIUM,
        TicketCategory.BILLING,
        TicketStatus.IN_PROGRESS,
        "agent:alex",
    ),
    SeedScenario(
        "03-card-replacement",
        "Noah Kim",
        "noah@example.com",
        "Replacement card not received",
        "My replacement card has not arrived after the expected delivery date.",
        TicketPriority.HIGH,
        TicketCategory.CARD,
        TicketStatus.RESOLVED,
        "agent:blair",
    ),
    SeedScenario(
        "04-payment-refund",
        "Mia Rao",
        "mia@example.com",
        "Refund is still pending",
        "A merchant confirmed a refund but the balance has not updated yet.",
        TicketPriority.URGENT,
        TicketCategory.PAYMENT,
        TicketStatus.CLOSED,
        "agent:casey",
    ),
    SeedScenario(
        "05-technical-crash",
        "Ava Sharma",
        "ava@example.com",
        "Mobile app crashes on launch",
        "The mobile app closes immediately after I open it on my phone.",
        TicketPriority.LOW,
        TicketCategory.TECHNICAL,
        TicketStatus.OPEN,
    ),
    SeedScenario(
        "06-other-feedback",
        "Omar Siddiqui",
        "omar@example.com",
        "Feature feedback for statements",
        "I would like to download account statements in a spreadsheet format.",
        TicketPriority.MEDIUM,
        TicketCategory.OTHER,
        TicketStatus.IN_PROGRESS,
        "agent:alex",
    ),
    SeedScenario(
        "07-account-verification",
        "Ava Sharma",
        "ava@example.com",
        "Identity verification delayed",
        "My identity verification has been pending for two business days.",
        TicketPriority.HIGH,
        TicketCategory.ACCOUNT,
        TicketStatus.RESOLVED,
        "agent:blair",
    ),
    SeedScenario(
        "08-billing-invoice",
        "Priya Nair",
        "priya@example.com",
        "Invoice amount looks incorrect",
        "The invoice total differs from the plan price displayed in the application.",
        TicketPriority.URGENT,
        TicketCategory.BILLING,
        TicketStatus.CLOSED,
        "agent:casey",
    ),
    SeedScenario(
        "09-card-contactless",
        "Chen Wu",
        "chen@example.com",
        "Contactless payments stopped working",
        "My card works with chip and PIN but contactless payments are declined.",
        TicketPriority.LOW,
        TicketCategory.CARD,
        TicketStatus.OPEN,
    ),
    SeedScenario(
        "10-payment-transfer",
        "Disha Kapoor",
        "disha@example.com",
        "Bank transfer recipient missing",
        "A completed bank transfer is not visible to the intended recipient.",
        TicketPriority.MEDIUM,
        TicketCategory.PAYMENT,
        TicketStatus.IN_PROGRESS,
        "agent:alex",
    ),
    SeedScenario(
        "11-technical-notification",
        "Elias Martin",
        "elias@example.com",
        "Push notifications are delayed",
        "Transaction notifications arrive several hours after the transaction completes.",
        TicketPriority.HIGH,
        TicketCategory.TECHNICAL,
        TicketStatus.RESOLVED,
        "agent:blair",
    ),
    SeedScenario(
        "12-other-closure",
        "Ava Sharma",
        "ava@example.com",
        "Request to close unused feature",
        "Please remove access to an unused reporting feature from my account.",
        TicketPriority.URGENT,
        TicketCategory.OTHER,
        TicketStatus.CLOSED,
        "agent:casey",
    ),
    SeedScenario(
        "13-account-profile",
        "Fatima Khan",
        "fatima@example.com",
        "Profile details need updating",
        "I need to update my legal name after submitting the required documents.",
        TicketPriority.MEDIUM,
        TicketCategory.ACCOUNT,
        TicketStatus.OPEN,
    ),
    SeedScenario(
        "14-billing-payment-method",
        "Liam Patel",
        "liam@example.com",
        "Unable to update payment method",
        "The billing page rejects my new payment method before it can be saved.",
        TicketPriority.HIGH,
        TicketCategory.BILLING,
        TicketStatus.IN_PROGRESS,
        "agent:alex",
    ),
    SeedScenario(
        "15-card-cash-withdrawal",
        "Grace Thomas",
        "grace@example.com",
        "Cash withdrawal was declined",
        "My card was declined at an ATM despite having enough available balance.",
        TicketPriority.URGENT,
        TicketCategory.CARD,
        TicketStatus.RESOLVED,
        "agent:blair",
    ),
    SeedScenario(
        "16-payment-duplicate",
        "Ava Sharma",
        "ava@example.com",
        "Duplicate merchant payment",
        "The same merchant payment appears twice in my recent transaction history.",
        TicketPriority.LOW,
        TicketCategory.PAYMENT,
        TicketStatus.CLOSED,
        "agent:casey",
    ),
    SeedScenario(
        "17-technical-browser",
        "Hari Singh",
        "hari@example.com",
        "Dashboard does not load in browser",
        "The dashboard remains blank after sign in using the latest browser version.",
        TicketPriority.MEDIUM,
        TicketCategory.TECHNICAL,
        TicketStatus.OPEN,
    ),
    SeedScenario(
        "18-other-document",
        "Inez Garcia",
        "inez@example.com",
        "Need a confirmation document",
        "Please provide a formal document confirming my account is active.",
        TicketPriority.HIGH,
        TicketCategory.OTHER,
        TicketStatus.IN_PROGRESS,
        "agent:alex",
    ),
    SeedScenario(
        "19-payment-spam",
        "Jules Bernard",
        "jules@example.com",
        "Urgent payment verification needed",
        "Please visit http://example.invalid immediately to verify an urgent payment.",
        TicketPriority.URGENT,
        TicketCategory.PAYMENT,
        TicketStatus.RESOLVED,
        "agent:blair",
    ),
    SeedScenario(
        "20-card-pin",
        "Kiara Bose",
        "kiara@example.com",
        "PIN change did not apply",
        "My new card PIN was accepted but the old PIN still works at terminals.",
        TicketPriority.LOW,
        TicketCategory.CARD,
        TicketStatus.CLOSED,
        "agent:casey",
    ),
)


def advance_status(
    service: TicketService,
    ticket_id: int,
    target: TicketStatus,
    agent: str | None,
) -> None:
    if target is TicketStatus.OPEN:
        return
    if agent is None:
        raise ValueError("A non-open seeded ticket requires an agent")
    service.update_status(ticket_id, TicketStatus.IN_PROGRESS, agent)
    if target is TicketStatus.RESOLVED:
        service.update_status(ticket_id, TicketStatus.RESOLVED, agent)
    elif target is TicketStatus.CLOSED:
        service.update_status(ticket_id, TicketStatus.CLOSED, agent)


def main() -> None:
    db = SessionLocal()
    created = 0
    reused = 0
    try:
        ticket_service = TicketService(db)
        processing_service = ProcessingService(db)
        for scenario in SCENARIOS:
            ticket, was_created = ticket_service.create_ticket_idempotent(
                scenario.payload(), f"seed-ticket-{scenario.key}"
            )
            if not was_created:
                reused += 1
                continue

            created += 1
            if processing_service.begin(ticket.id, f"seed-processing-{scenario.key}"):
                processing_service.complete(ticket.id, f"seed-processing-{scenario.key}")
            advance_status(ticket_service, ticket.id, scenario.target_status, scenario.agent)

        replay, was_created = ticket_service.create_ticket_idempotent(
            SCENARIOS[0].payload(), f"seed-ticket-{SCENARIOS[0].key}"
        )
        assert not was_created
        print(f"Seeded {created} tickets; reused {reused} existing tickets.")
        print(f"Idempotency replay confirmed for ticket #{replay.id}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
