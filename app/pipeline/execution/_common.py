import logging

from app.core.models import Action, ActionType
from app.pipeline.execution.handlers import calendar_handler, draft_handler, email_handler, spreadsheet_handler
from app.pipeline.execution.handlers.base import HandlerError


logger = logging.getLogger(__name__)

# maps action_type to handler
HANDLERS = {
    ActionType.JOB_APPLY: spreadsheet_handler.append_data,
    ActionType.CALENDAR_EVENT: calendar_handler.create_event,
    ActionType.DRAFT_REPLY: draft_handler.create_draft,
    ActionType.SEND_REPLY: email_handler.send_draft
}

def dispatch(action: Action) -> dict | None:
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
