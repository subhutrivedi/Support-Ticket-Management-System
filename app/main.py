import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from prometheus_client import Counter, generate_latest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.logging import configure_logging, request_id_context
from app.db import get_db
from app.models import TicketCategory, TicketPriority, TicketStatus
from app.schemas import (
    ErrorResponse,
    TicketCreate,
    TicketDetailResponse,
    TicketListResponse,
    TicketResponse,
    TicketStatusUpdate,
)
from app.services import TicketService
from app.worker import dispatch_outbox_messages

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)
ticket_creation_counter = Counter("ticketflow_tickets_created_total", "Tickets created")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("application_started", extra={"environment": settings.environment})
    yield
    logger.info("application_stopped")


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)


def error_response(
    request: Request,
    status_code: int,
    error: str,
    message: str,
    details: list[dict[str, object]] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    response = JSONResponse(
        status_code=status_code,
        content={"error": error, "message": message, "request_id": request_id, "details": details},
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def request_context(request: Request, call_next):
    supplied_request_id = request.headers.get("X-Request-ID")
    request.state.request_id = (
        supplied_request_id
        if supplied_request_id and len(supplied_request_id) <= 128
        else str(uuid.uuid4())
    )
    token = request_id_context.set(request.state.request_id)
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response
    finally:
        logger.info(
            "request_completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": getattr(locals().get("response"), "status_code", 500),
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
            },
        )
        request_id_context.reset(token)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    details = [
        {"location": list(error["loc"]), "message": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return error_response(request, 422, "validation_error", "Request validation failed", details)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    return error_response(request, exc.status_code, exc.error_code, exc.message)


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "Request could not be completed"
    return error_response(request, exc.status_code, "request_error", message)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("database_error")
    return error_response(request, 503, "service_unavailable", "A required service is unavailable")


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("unhandled_error")
    return error_response(request, 500, "internal_error", "An unexpected error occurred")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ticketflow"}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type="text/plain; version=0.0.4")


@app.get("/ready", tags=["system"])
def readiness(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ready", "service": "ticketflow"}


@app.post(
    "/v1/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["tickets"],
)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)) -> TicketResponse:
    ticket = TicketService(db).create_ticket(payload)
    ticket_creation_counter.inc()
    if settings.auto_process_tickets:
        dispatch_outbox_messages.delay()
    return TicketResponse.model_validate(ticket)


@app.get(
    "/v1/tickets/{ticket_id}",
    response_model=TicketDetailResponse,
    responses={404: {"model": ErrorResponse}},
    tags=["tickets"],
)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)) -> TicketDetailResponse:
    ticket = TicketService(db).get_ticket(ticket_id, include_events=True)
    return TicketDetailResponse.model_validate(ticket)


@app.get("/v1/tickets", response_model=TicketListResponse, tags=["tickets"])
def list_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: TicketStatus | None = Query(None, alias="status"),
    priority: TicketPriority | None = None,
    category: TicketCategory | None = None,
    db: Session = Depends(get_db),
) -> TicketListResponse:
    items, total = TicketService(db).list_tickets(
        page, page_size, status_filter, priority, category
    )
    return TicketListResponse(
        items=[TicketResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@app.patch(
    "/v1/tickets/{ticket_id}/status",
    response_model=TicketResponse,
    responses={404: {"model": ErrorResponse}},
    tags=["tickets"],
)
def update_ticket_status(
    ticket_id: int,
    payload: TicketStatusUpdate,
    db: Session = Depends(get_db),
) -> TicketResponse:
    ticket = TicketService(db).update_status(ticket_id, payload.status, payload.actor)
    return TicketResponse.model_validate(ticket)
