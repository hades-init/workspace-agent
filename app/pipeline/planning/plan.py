import logging

from dotenv import load_dotenv
from sqlalchemy import select

from app.core.models import Action, Message, MessageStatus, MessageCategory
from app.core.database import SessionLocal
from app.core.logging_config import setup_logging
from app.pipeline.planning.extractors import draft_reply, job_apply, calendar_event, ignore
from app.pipeline.planning.extractors.base import ExtractionError


logger = logging.getLogger(__name__)

PLANNERS = {
    MessageCategory.APPLY: job_apply.create_action,
    MessageCategory.IGNORE: ignore.do_nothing,
    MessageCategory.INTERVIEW: calendar_event.create_action,
    MessageCategory.REPLY_NEEDED: draft_reply.create_action,
}

def dispatcher(message: Message) -> Action:
    """Dispatch to a planning agent based on the message category

    Args
        message: email message

    Returns
        action: an `Action` object for the given email 
    """

    if not message.category:
        raise ExtractionError("Message category is null")

    planner = PLANNERS.get(message.category)

    if not planner:
        raise NotImplementedError(
            f"No planner found for message_category='{message.category.value}'"
        )
    
    return planner(message)
    


def run():
    logger.info("Starting email planning ...")

    success = 0
    skipped = 0
    failed = 0
    with SessionLocal() as db:
        classified_messages = db.scalars(
            select(Message).where(Message.status == MessageStatus.CLASSIFIED)
        )

        for message in classified_messages:
            try:
                action = dispatcher(message)
                if action:
                    db.add(action)                
                    db.commit()
                    db.refresh(action)
                    logger.info("Created action action_id=%s for message_id=%s", action.id, message.id)
                message.status = MessageStatus.PLANNED
                success += 1
            except NotImplementedError as e:
                logger.warning("Skipping planning for message_id=%s: %s", message.id, e)
                skipped += 1

            except ExtractionError as e:
                failed += 1
                logger.error("Planning failed for message_id=%s: %s", message.id, e)
            
            except Exception as e:
                failed += 1
                logger.exception("Unexpected error for message_id=%s: %s", message.id, e)

        db.commit()


    logger.info(
        "Email planning complete: success=%d skipped=%d failed=%d", 
        success, skipped, failed
    )


if __name__ == "__main__":
    setup_logging()
    load_dotenv()
    run()