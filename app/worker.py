import logging

from celery import Celery

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db import SessionLocal
from app.services import TicketService

settings = get_settings()
configure_logging(settings.log_level)
celery_app = Celery("ticketflow", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_default_queue = "ticket-processing"
logger = logging.getLogger(__name__)


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def process_ticket_task(self, ticket_id: int) -> None:
    db = SessionLocal()
    try:
        TicketService(db).process_ticket(ticket_id)
        logger.info("ticket_processed", extra={"ticket_id": ticket_id})
    except Exception:
        logger.exception("ticket_processing_failed", extra={"ticket_id": ticket_id})
        raise
    finally:
        db.close()
