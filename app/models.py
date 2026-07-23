import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TicketStatus(enum.StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketPriority(enum.StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TicketCategory(enum.StrEnum):
    ACCOUNT = "ACCOUNT"
    BILLING = "BILLING"
    CARD = "CARD"
    PAYMENT = "PAYMENT"
    TECHNICAL = "TECHNICAL"
    OTHER = "OTHER"


class ActorType(enum.StrEnum):
    CUSTOMER = "CUSTOMER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


class ProcessingStatus(enum.StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class OutboxStatus(enum.StrEnum):
    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"


class Actor(Base):
    __tablename__ = "actors"
    __table_args__ = (UniqueConstraint("id", "actor_type", name="uq_actors_id_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_type: Mapped[ActorType] = mapped_column(
        Enum(ActorType, name="actor_type"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    customer: Mapped["Customer | None"] = relationship(back_populates="actor", uselist=False)
    agent: Mapped["Agent | None"] = relationship(back_populates="actor", uselist=False)
    events: Mapped[list["TicketEvent"]] = relationship(back_populates="actor")


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint("actor_type = 'CUSTOMER'", name="ck_customers_actor_type"),
        ForeignKeyConstraint(
            ["id", "actor_type"],
            ["actors.id", "actors.actor_type"],
            name="fk_customers_actor",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_type: Mapped[ActorType] = mapped_column(
        Enum(ActorType, name="actor_type"),
        nullable=False,
        default=ActorType.CUSTOMER,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actor: Mapped[Actor] = relationship(back_populates="customer")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="customer")


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint("actor_type = 'AGENT'", name="ck_agents_actor_type"),
        ForeignKeyConstraint(
            ["id", "actor_type"],
            ["actors.id", "actors.actor_type"],
            name="fk_agents_actor",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_type: Mapped[ActorType] = mapped_column(
        Enum(ActorType, name="actor_type"), nullable=False, default=ActorType.AGENT
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actor: Mapped[Actor] = relationship(back_populates="agent")


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("length(trim(subject)) >= 3", name="ck_tickets_subject_length"),
        CheckConstraint("length(trim(description)) >= 10", name="ck_tickets_description_length"),
        CheckConstraint(
            "spam_score IS NULL OR spam_score BETWEEN 0 AND 100",
            name="ck_tickets_spam_score_range",
        ),
        CheckConstraint(
            "(processing_summary IS NULL AND assigned_department IS NULL AND spam_score IS NULL) "
            "OR (processing_summary IS NOT NULL AND assigned_department IS NOT NULL "
            "AND spam_score IS NOT NULL)",
            name="ck_tickets_processing_fields_complete",
        ),
        Index("ix_tickets_status_created_at", "status", "created_at"),
        Index("ix_tickets_priority_created_at", "priority", "created_at"),
        Index("ix_tickets_category_created_at", "category", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[TicketPriority] = mapped_column(
        Enum(TicketPriority, name="ticket_priority"), nullable=False
    )
    category: Mapped[TicketCategory] = mapped_column(
        Enum(TicketCategory, name="ticket_category"), nullable=False
    )
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticket_status"), nullable=False, default=TicketStatus.OPEN
    )
    processing_summary: Mapped[str | None] = mapped_column(Text)
    assigned_department: Mapped[str | None] = mapped_column(String(80))
    spam_score: Mapped[int | None] = mapped_column(Integer)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status"),
        nullable=False,
        default=ProcessingStatus.PENDING,
    )
    processing_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processing_error: Mapped[str | None] = mapped_column(Text)
    processing_task_id: Mapped[str | None] = mapped_column(String(50), unique=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    events: Mapped[list["TicketEvent"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
    customer: Mapped[Customer] = relationship(back_populates="tickets")
    outbox_messages: Mapped[list["OutboxMessage"]] = relationship(back_populates="ticket")


class TicketEvent(Base):
    __tablename__ = "ticket_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('CREATED', 'STATUS_CHANGED', 'AUTO_PROCESSED')",
            name="ck_ticket_events_event_type",
        ),
        CheckConstraint(
            "(event_type = 'CREATED' AND actor_type = 'CUSTOMER' "
            "AND from_status IS NULL AND to_status = 'OPEN') "
            "OR (event_type = 'STATUS_CHANGED' AND from_status IS NOT NULL "
            "AND to_status IS NOT NULL AND from_status <> to_status AND actor_type = 'AGENT') "
            "OR (event_type = 'AUTO_PROCESSED' AND actor_type = 'SYSTEM' "
            "AND from_status IS NULL AND to_status IS NULL)",
            name="ck_ticket_events_status_shape",
        ),
        ForeignKeyConstraint(
            ["actor_id", "actor_type"],
            ["actors.id", "actors.actor_type"],
            name="fk_ticket_events_actor",
            ondelete="RESTRICT",
        ),
        Index("ix_ticket_events_ticket_id_created_at", "ticket_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    from_status: Mapped[TicketStatus | None] = mapped_column(
        Enum(TicketStatus, name="ticket_status")
    )
    to_status: Mapped[TicketStatus | None] = mapped_column(
        Enum(TicketStatus, name="ticket_status")
    )
    actor_id: Mapped[int] = mapped_column(nullable=False)
    actor_type: Mapped[ActorType] = mapped_column(
        Enum(ActorType, name="actor_type"), nullable=False
    )
    metadata_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ticket: Mapped[Ticket] = relationship(back_populates="events")
    actor: Mapped[Actor] = relationship(back_populates="events")


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    topic: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[OutboxStatus] = mapped_column(
        Enum(OutboxStatus, name="outbox_status"),
        nullable=False,
        default=OutboxStatus.PENDING,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ticket: Mapped[Ticket] = relationship(back_populates="outbox_messages")


class DeadLetterMessage(Base):
    __tablename__ = "dead_letter_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False
    )
    task_id: Mapped[str] = mapped_column(String(50), nullable=False)
    error: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
