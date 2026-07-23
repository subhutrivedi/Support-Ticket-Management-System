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


@celery_app.task(bind=True, max_retries=3)
def process_ticket_task(self, ticket_id: int) -> None:
    db = SessionLocal()
    try:
        service = TicketService(db)
        task_id = self.request.id or f"ticket-{ticket_id}"
        if not service.begin_processing(ticket_id, task_id):
            logger.info("ticket_processing_skipped", extra={"ticket_id": ticket_id})
            return
        service.process_ticket(ticket_id, task_id)
        logger.info("ticket_processed", extra={"ticket_id": ticket_id})
    except Exception as exc:
        retrying = self.request.retries < self.max_retries
        db.rollback()
        TicketService(db).mark_processing_failed(ticket_id, task_id, exc, retrying)
        logger.exception("ticket_processing_failed", extra={"ticket_id": ticket_id})
        if retrying:
            raise self.retry(exc=exc, countdown=2**self.request.retries) from exc
        raise
    finally:
        db.close()
