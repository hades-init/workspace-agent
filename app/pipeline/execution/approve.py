import logging

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.logging_config import setup_logging
from app.core.models import Action, ActionStatus, Message, MessageStatus
from app.pipeline.execution._common import dispatch
from app.pipeline.execution.handlers.base import HandlerError

logger = logging.getLogger(__name__)


def run():
    logger.info("Starting execution of approved actions ...")

    success = 0
    failed = 0
    skipped = 0
    with SessionLocal() as db:
        approved_actions = db.scalars(
            select(Action).where(Action.status == ActionStatus.APPROVED)
        )

        if not approved_actions:
            logger.info("No approved actions to execute")
            return
        
        for action in approved_actions:
            try:
                result = dispatch(action)
                action.result = result
                action.status = ActionStatus.EXECUTED

                message = db.get(Message, action.message_id)
                assert message is not None
                message.status = MessageStatus.ACTIONED

                success += 1
                logger.info(
                    "Executed action with action_id=%d action_type='%s'", 
                    action.id, action.action_type.value
                )
                logger.debug("Execution results action_id=%s: %s", action.id, result)

            except NotImplementedError as e:
                logger.warning("Skipping action id=%d: %s", action.id, e)
                skipped += 1
                
            except HandlerError as e:
                action.error = str(e)
                action.status = ActionStatus.FAILED
                failed += 1
                logger.error("Action execution failed action_id=%d: %s", action.id, e)

            except Exception as e:
                action.error = f"Unexpected: {e}"
                action.status = ActionStatus.FAILED
                failed += 1
                logger.exception("Unexpected error for action_id=%d", action.id)

        db.commit()

    logger.info(
        "Approved actions execution complete: success=%d failed=%d skipped=%d",
        success, failed, skipped,
    )


if __name__ == "__main__":
    setup_logging()
    load_dotenv()
    run()