import logging

from app.core.models import Action, ActionType
from app.pipeline.execution.handlers import calendar, email, spreadsheet
from app.pipeline.execution.handlers.base import HandlerError


logger = logging.getLogger(__name__)

# maps action_type to handler
HANDLERS = {
    ActionType.JOB_APPLY: spreadsheet.append_data,
    ActionType.CALENDAR_EVENT: calendar.create_event,
    ActionType.DRAFT_REPLY: email.create_draft,
    ActionType.SEND_REPLY: email.send_draft
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
