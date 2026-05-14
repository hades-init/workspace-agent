import logging

from dotenv import load_dotenv
from sqlalchemy import select
from app.pipeline.classification.agent import classify_email
from app.core.database import SessionLocal
from app.core.models import Message, MessageStatus
from app.core.logging_config import setup_logging

logger = logging.getLogger(__name__)

def run():
    logger.info("Starting email classification ...")
    success = 0
    failed = 0
    with SessionLocal() as db:
        ready_messages = db.scalars(
            select(Message).where(Message.status == MessageStatus.FETCHED)
        )

        for message in ready_messages:
            try:
                email_category = classify_email(message)
                for key, val in email_category.model_dump().items():
                    setattr(message, key, val)
                message.status = MessageStatus.CLASSIFIED
                success += 1
            except Exception:
                logger.exception("Failed to classify email id=%s", message.id)
                message.status = MessageStatus.FAILED
                failed += 1
        
        db.commit()
        logger.info("Email classification complete: success=%d failed=%d", success, failed)


if __name__ == "__main__":
    setup_logging()
    load_dotenv()
    run()