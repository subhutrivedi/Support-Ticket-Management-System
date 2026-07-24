import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.tickets import Ticket, TicketEvent


class ActorType(enum.StrEnum):
    CUSTOMER = "CUSTOMER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


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
        Enum(ActorType, name="actor_type"), nullable=False, default=ActorType.CUSTOMER
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
