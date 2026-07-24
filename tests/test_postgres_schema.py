import os

import pytest
from sqlalchemy import create_engine, inspect, text


@pytest.mark.skipif(
    not os.getenv("POSTGRES_INTEGRATION_URL"),
    reason="requires the PostgreSQL integration database",
)
def test_postgres_migrations_create_required_schema() -> None:
    engine = create_engine(os.environ["POSTGRES_INTEGRATION_URL"])
    inspector = inspect(engine)

    assert {"tickets", "ticket_events", "outbox_messages", "dead_letter_messages"} <= set(
        inspector.get_table_names()
    )
    with engine.connect() as connection:
        trigger_names = {
            trigger["name"]
            for trigger in connection.execute(
                text("SELECT tgname AS name FROM pg_trigger WHERE NOT tgisinternal")
            ).mappings()
        }
    assert "ticket_events_append_only" in trigger_names
