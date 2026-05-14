import logging

from dotenv import load_dotenv
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.logging_config import setup_logging
from app.core.models import Action, ActionStatus, ActionType, Message, MessageStatus
from app.pipeline.execution._common import dispatch
from app.pipeline.execution.handlers.base import HandlerError

logger = logging.getLogger(__name__)
    

def _spawn_send_action(draft_action: Action):
    """After draft email is created, queue a SEND_REPLY action 
    with awaiting_approval status.
    """
    if not draft_action.result or "draft_id" not in draft_action.result:
        logger.warning(
            "DRAFT_REPLY action_id=%s succeeded without `draft_id`, skipping SEND_REPLY action spawn",
            draft_action.id,
        )
        return
    
    assert draft_action.payload is not None

    payload= {
        "draft_id": draft_action.result["draft_id"],
        # Carry forward useful context for the CLI display
        "message": {
            "to_address": draft_action.payload["to_address"],
            "subject": draft_action.payload["subject"],
            "reply_body": draft_action.payload["reply_body"],
            "attachments_to_include": draft_action.payload["attachments_to_include"],
        },
        "parent_action_id": draft_action.id,
    }

    send_action = Action(
        message_id=draft_action.message_id,
        action_type=ActionType.SEND_REPLY,
        status=ActionStatus.AWAITING_APPROVAL,
        payload = payload
    )

    logger.info(
        "Queued SEND_REPLY action awaiting approval (parent action_id=%s)",
        draft_action.id,
    )
    return send_action



def _is_terminal_for_message(action: Action):
    # DRAFT_REPLY succeeds but it is not work done for the message -
    # the follow-up SEND_REPLY still has to be executed before 
    # the message can be marked ACTIONED
    if action.action_type == ActionType.DRAFT_REPLY:
        return False
    return True


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
                result = dispatch(action)
                action.result = result
                action.status = ActionStatus.EXECUTED

                # Post-hook: spawn the gated SEND_REPLY action after draft creation
                if action.action_type == ActionType.DRAFT_REPLY:
                    send_action = _spawn_send_action(action)
                    db.add(send_action)
                
                # Mark the message ACTIONED only if this action closes its work
                if _is_terminal_for_message(action):
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
        "Actions execution complete: success=%d failed=%d skipped=%d",
        success, failed, skipped,
    )


if __name__ == "__main__":
    setup_logging()
    load_dotenv()
    run()