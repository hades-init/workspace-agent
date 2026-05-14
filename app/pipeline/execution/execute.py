import logging

from dotenv import load_dotenv
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.logging_config import setup_logging
from app.core.models import Action, ActionStatus, ActionType, Message, MessageStatus
from app.pipeline.execution.handlers import calendar, email, spreadsheet
from app.pipeline.execution.handlers.base import HandlerError

logger = logging.getLogger(__name__)

# maps action_type to handler
HANDLERS = {
    ActionType.JOB_APPLY: spreadsheet.append_data,
    ActionType.CALENDAR_EVENT: calendar.create_event,
    ActionType.SEND_REPLY: email.create_draft
}

def dispatcher(action: Action) -> dict | None:
    """Dispatch to a handler based on the action_type

    Args
        action: `Action` object

    Returns
        result: result of the handler's execution 
    """

    handler = HANDLERS.get(action.action_type)

    if not handler:
        raise NotImplementedError(
            f"No handler found for action_type={action.action_type}"
        )
    
    if not action.payload:
        raise HandlerError("Action payload is empty")
    
    return handler(action.payload, action_id=action.id)
    


def run():
    logger.info("Starting actions execution")

    success = 0
    failed = 0
    skipped = 0
    with SessionLocal() as db:
        pending_actions = db.scalars(
            select(Action).where(Action.status == ActionStatus.PENDING)
        )

        for action in pending_actions:
            try:
                result = dispatcher(action)
                action.result = result
                action.status = ActionStatus.EXECUTED
                message = db.get(Message, action.message_id)
                assert message is not None
                message.status = MessageStatus.ACTIONED
                success += 1
                logger.info("Executed action_id=%d action_type='%s'", action.id, action.action_type.value)
                logger.debug("Execution results action_id=%s: %s", action.id, result)

            except NotImplementedError as e:
                logger.warning("Skipping action id=%d: %s", action.id, e)
                skipped += 1
                
            except HandlerError as e:
                action.error = str(e)
                # action.status = ActionStatus.FAILED
                failed += 1
                logger.error("Action execution failed action_id=%d: %s", action.id, e)

            except Exception as e:
                action.error = f"Unexpected: {e}"
                # action.status = ActionStatus.FAILED
                failed += 1
                logger.exception("Unexpected error for action_id=%d", action.id)

        db.commit()

    logger.info(
        "Actions execution complete: success=%d failed=%d skipped=%d",
        success, failed, skipped,
    )


if __name__ == "__main__":
    setup_logging()
    load_dotenv()
    run()