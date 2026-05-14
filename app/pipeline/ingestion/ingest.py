import logging
# import time
from sqlalchemy import select
from app.core.logging_config import setup_logging
from app.core.database import SessionLocal
from app.pipeline.ingestion import gmail_api
from app.core.models import Message, MessageStatus, Attachment
from app.pipeline.ingestion import email_parser

logger = logging.getLogger(__name__)

def run():
    """
    Fetch latest unread emails from mailbox and persist to database
    """
    logger.info("Starting email ingestion ...")

    emails = gmail_api.fetch_email_list()
    logger.info("Fetched %d emails", len(emails))

    saved = 0
    skipped = 0

    with SessionLocal() as db:
        # Dedup - check if message id already exist in db 
        # NOTE: Use one bulk query upfront for all candidate ids, then skip in the loop.
        # This way we avoid the expensive `fetch_email` API for known duplicates, 
        # and don't do N+1 queries.
        candidate_ids = [e['id'] for e in emails]
        existing_ids = set(
            db.scalars(select(Message.id).where(Message.id.in_(candidate_ids))).all()
        )
        if existing_ids:
            logger.info("Skipping %d already-ingested emails", len(existing_ids))

        for email in emails:
            if email['id'] in existing_ids:
                skipped += 1
                continue
            try:
                # Fetch email from gmail servers
                msg = gmail_api.fetch_email(email['id'])
                
                # Parse email
                parsed_message = email_parser.parse_message(msg)

                attachments = [Attachment(**a) for a in parsed_message.pop('attachments', [])]
                message = Message(**parsed_message, status=MessageStatus.FETCHED, attachments=attachments)
                db.add(message)
                db.commit()
                saved += 1
                logger.debug("Saved message in db message_id=%s", message.id)
                # time.sleep(0.1)
            except Exception:
                logger.exception("Failed to process email id=%s", email['id'])
                continue

    failed = len(emails) - saved - skipped
    logger.info("Ingestion complete: saved=%d skipped=%d failed=%d", saved, skipped, failed)


if __name__ == "__main__":
    setup_logging()
    run()