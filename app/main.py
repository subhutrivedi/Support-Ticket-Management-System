import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db import get_db
from app.models import TicketCategory, TicketPriority, TicketStatus
from app.schemas import ErrorResponse, TicketCreate, TicketDetailResponse, TicketListResponse, TicketResponse, TicketStatusUpdate
from app.services import TicketService
from app.worker import process_ticket_task

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("application_started", extra={"environment": settings.environment})
    yield
    logger.info("application_stopped")


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)


def error_response(request: Request, status_code: int, error: str, detail: object) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(status_code=status_code, content={"error": error, "detail": str(detail), "request_id": request_id})


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return error_response(request, 422, "validation_error", exc.errors())


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    return error_response(request, exc.status_code, "request_error", exc.detail)


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("unhandled_error", extra={"request_id": getattr(request.state, "request_id", None)})
    return error_response(request, 500, "internal_error", "An unexpected error occurred")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ticketflow"}


@app.post("/v1/tickets", response_model=TicketResponse, status_code=status.HTTP_201_CREATED, tags=["tickets"])
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)) -> TicketResponse:
    ticket = TicketService(db).create_ticket(payload)
    if settings.auto_process_tickets:
        process_ticket_task.delay(ticket.id)
    return TicketResponse.model_validate(ticket)


@app.get("/v1/tickets/{ticket_id}", response_model=TicketDetailResponse, responses={404: {"model": ErrorResponse}}, tags=["tickets"])
def get_ticket(ticket_id: int, db: Session = Depends(get_db)) -> TicketDetailResponse:
    return TicketDetailResponse.model_validate(TicketService(db).get_ticket(ticket_id, include_events=True))


@app.get("/v1/tickets", response_model=TicketListResponse, tags=["tickets"])
def list_tickets(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    status_filter: TicketStatus | None = Query(None, alias="status"), priority: TicketPriority | None = None,
    category: TicketCategory | None = None, db: Session = Depends(get_db),
) -> TicketListResponse:
    items, total = TicketService(db).list_tickets(page, page_size, status_filter, priority, category)
    return TicketListResponse(items=[TicketResponse.model_validate(item) for item in items], page=page, page_size=page_size, total=total)


@app.patch("/v1/tickets/{ticket_id}/status", response_model=TicketResponse, responses={404: {"model": ErrorResponse}}, tags=["tickets"])
def update_ticket_status(ticket_id: int, payload: TicketStatusUpdate, db: Session = Depends(get_db)) -> TicketResponse:
    return TicketResponse.model_validate(TicketService(db).update_status(ticket_id, payload.status, payload.actor))
