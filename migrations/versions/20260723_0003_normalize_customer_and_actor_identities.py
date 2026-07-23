"""Normalize customers and audit-event actors.

Revision ID: 202607230003
Revises: 202607230002
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "202607230003"
down_revision = "202607230002"
branch_labels = None
depends_on = None

actor_type = postgresql.ENUM("CUSTOMER", "AGENT", "SYSTEM", name="actor_type", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    actor_type.create(bind, checkfirst=True)

    op.create_table(
        "actors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_type", actor_type, nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("external_reference", sa.String(120), unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("id", "actor_type", name="uq_actors_id_type"),
    )
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_type", actor_type, nullable=False, server_default="CUSTOMER"),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("actor_type = 'CUSTOMER'", name="ck_customers_actor_type"),
        sa.ForeignKeyConstraint(
            ["id", "actor_type"],
            ["actors.id", "actors.actor_type"],
            name="fk_customers_actor",
            ondelete="RESTRICT",
        ),
    )
    op.create_table(
        "agents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_type", actor_type, nullable=False, server_default="AGENT"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("actor_type = 'AGENT'", name="ck_agents_actor_type"),
        sa.ForeignKeyConstraint(
            ["id", "actor_type"],
            ["actors.id", "actors.actor_type"],
            name="fk_agents_actor",
            ondelete="RESTRICT",
        ),
    )

    # Backfill one customer identity per normalized email before removing duplicated fields.
    bind.execute(
        sa.text(
            "INSERT INTO actors (actor_type, display_name, external_reference) "
            "SELECT 'CUSTOMER'::actor_type, min(customer_name), "
            "'customer:' || lower(customer_email) "
            "FROM tickets GROUP BY lower(customer_email)"
        )
    )
    bind.execute(
        sa.text(
            "INSERT INTO customers (id, actor_type, email) "
            "SELECT id, 'CUSTOMER'::actor_type, "
            "substring(external_reference FROM 'customer:(.*)') "
            "FROM actors WHERE actor_type = 'CUSTOMER'"
        )
    )
    op.add_column("tickets", sa.Column("customer_id", sa.Integer(), nullable=True))
    bind.execute(
        sa.text(
            "UPDATE tickets AS ticket SET customer_id = customer.id "
            "FROM customers AS customer "
            "WHERE customer.email = lower(ticket.customer_email)"
        )
    )
    op.alter_column("tickets", "customer_id", nullable=False)
    op.create_foreign_key(
        "fk_tickets_customer", "tickets", "customers", ["customer_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_tickets_customer_id", "tickets", ["customer_id"])

    # Preserve historical actor labels as typed identities while making customer events point
    # to the actual ticket customer.
    bind.execute(
        sa.text(
            "INSERT INTO actors (actor_type, display_name, external_reference) "
            "SELECT 'SYSTEM'::actor_type, 'worker:ticket-processor', 'worker:ticket-processor' "
            "WHERE EXISTS (SELECT 1 FROM ticket_events WHERE actor = 'worker:ticket-processor')"
        )
    )
    bind.execute(
        sa.text(
            "INSERT INTO actors (actor_type, display_name, external_reference) "
            "SELECT 'AGENT'::actor_type, actor, actor "
            "FROM ticket_events "
            "WHERE actor NOT IN ('customer', 'worker:ticket-processor') GROUP BY actor"
        )
    )
    bind.execute(
        sa.text(
            "INSERT INTO agents (id, actor_type) "
            "SELECT id, 'AGENT'::actor_type FROM actors WHERE actor_type = 'AGENT'"
        )
    )
    op.add_column("ticket_events", sa.Column("actor_id", sa.Integer(), nullable=True))
    op.add_column("ticket_events", sa.Column("actor_type", actor_type, nullable=True))
    bind.execute(
        sa.text(
            "UPDATE ticket_events AS event SET "
            "actor_id = CASE "
            "WHEN event.actor = 'customer' THEN ticket.customer_id "
            "ELSE (SELECT id FROM actors WHERE external_reference = event.actor) END, "
            "actor_type = CASE "
            "WHEN event.actor = 'customer' THEN 'CUSTOMER'::actor_type "
            "WHEN event.actor = 'worker:ticket-processor' THEN 'SYSTEM'::actor_type "
            "ELSE 'AGENT'::actor_type END "
            "FROM tickets AS ticket WHERE ticket.id = event.ticket_id"
        )
    )
    op.alter_column("ticket_events", "actor_id", nullable=False)
    op.alter_column("ticket_events", "actor_type", nullable=False)
    op.drop_constraint("ck_ticket_events_actor_nonempty", "ticket_events", type_="check")
    op.drop_constraint("ck_ticket_events_status_shape", "ticket_events", type_="check")
    op.create_check_constraint(
        "ck_ticket_events_status_shape",
        "ticket_events",
        "(event_type = 'CREATED' AND actor_type = 'CUSTOMER' "
        "AND from_status IS NULL AND to_status = 'OPEN') "
        "OR (event_type = 'STATUS_CHANGED' AND from_status IS NOT NULL "
        "AND to_status IS NOT NULL AND from_status <> to_status AND actor_type = 'AGENT') "
        "OR (event_type = 'AUTO_PROCESSED' AND actor_type = 'SYSTEM' "
        "AND from_status IS NULL AND to_status IS NULL)",
    )
    op.create_foreign_key(
        "fk_ticket_events_actor",
        "ticket_events",
        "actors",
        ["actor_id", "actor_type"],
        ["id", "actor_type"],
        ondelete="RESTRICT",
    )

    op.drop_constraint("ck_tickets_customer_name_length", "tickets", type_="check")
    op.drop_constraint("ck_tickets_customer_email_format", "tickets", type_="check")
    op.drop_column("ticket_events", "actor")
    op.drop_column("tickets", "customer_name")
    op.drop_column("tickets", "customer_email")


def downgrade() -> None:
    op.add_column("tickets", sa.Column("customer_name", sa.String(120), nullable=True))
    op.add_column("tickets", sa.Column("customer_email", sa.String(320), nullable=True))
    op.add_column("ticket_events", sa.Column("actor", sa.String(120), nullable=True))
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE tickets AS ticket SET customer_name = actor.display_name, "
            "customer_email = customer.email "
            "FROM customers AS customer JOIN actors AS actor ON actor.id = customer.id "
            "WHERE ticket.customer_id = customer.id"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE ticket_events AS event SET actor = actor_record.display_name "
            "FROM actors AS actor_record WHERE event.actor_id = actor_record.id"
        )
    )
    op.alter_column("tickets", "customer_name", nullable=False)
    op.alter_column("tickets", "customer_email", nullable=False)
    op.alter_column("ticket_events", "actor", nullable=False)
    op.create_check_constraint(
        "ck_tickets_customer_name_length", "tickets", "length(trim(customer_name)) >= 2"
    )
    op.create_check_constraint(
        "ck_tickets_customer_email_format",
        "tickets",
        "customer_email = trim(customer_email) AND customer_email LIKE '%_@_%.__%'",
    )
    op.drop_constraint("fk_ticket_events_actor", "ticket_events", type_="foreignkey")
    op.drop_constraint("ck_ticket_events_status_shape", "ticket_events", type_="check")
    op.drop_column("ticket_events", "actor_type")
    op.drop_column("ticket_events", "actor_id")
    op.drop_index("ix_tickets_customer_id", table_name="tickets")
    op.drop_constraint("fk_tickets_customer", "tickets", type_="foreignkey")
    op.drop_column("tickets", "customer_id")
    op.drop_table("agents")
    op.drop_table("customers")
    op.drop_table("actors")
    actor_type.drop(bind, checkfirst=True)
