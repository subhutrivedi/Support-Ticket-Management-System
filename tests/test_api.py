from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app, settings


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    monkeypatch.setattr(settings, "auto_process_tickets", False)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def ticket_payload() -> dict[str, str]:
    return {
        "customer_name": "Jane Doe",
        "customer_email": "jane@gmail.com",
        "subject": "Cannot see payout",
        "description": "My payout has not appeared in my account yet.",
        "category": "PAYMENT",
    }


def test_validation_error_has_consistent_contract(client: TestClient) -> None:
    response = client.post("/v1/tickets", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_error"
    assert body["message"] == "Request validation failed"
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert body["details"]


def test_not_found_error_has_consistent_contract(client: TestClient) -> None:
    response = client.get("/v1/tickets/999", headers={"X-Request-ID": "trace-123"})

    assert response.status_code == 404
    assert response.json() == {
        "error": "not_found",
        "message": "Ticket 999 was not found",
        "request_id": "trace-123",
        "details": None,
    }


def test_list_filters_and_pagination(client: TestClient) -> None:
    first = client.post("/v1/tickets", json=ticket_payload())
    second_payload = ticket_payload() | {"customer_email": "mira@gmail.com", "category": "CARD"}
    second = client.post("/v1/tickets", json=second_payload)

    response = client.get("/v1/tickets?category=PAYMENT&page=1&page_size=1")

    assert first.status_code == 201
    assert second.status_code == 201
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["category"] == "PAYMENT"
    assert response.json()["items"][0]["customer"]["email"] == "jane@gmail.com"


def test_readiness_checks_database(client: TestClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
