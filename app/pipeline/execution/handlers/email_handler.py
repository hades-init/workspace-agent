import logging
from functools import lru_cache

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.google_auth import get_credentials
from app.pipeline.execution.handlers.base import HandlerError


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_resource():
    """Construct a Resource for interacting with Gmail API.
    """
    return build("gmail", "v1", credentials=get_credentials())


def send_draft(data: dict, **kwargs) -> dict:
    """Send an existing Gmail draft, used when SEND_REPLY action is approved
    """
    draft_id = data.get("draft_id")
    if not draft_id:
        raise HandlerError("send_draft requires draft_id in payload")
    
    action_id = kwargs.get("action_id")
    logger.debug("Sending draft email for action_id=%s", action_id)

    service = _get_resource()
    try:
        response = (
            service.users()
            .drafts()
            .send(userId="me", body={"id": draft_id})
            .execute()
        )
        logger.info("Gmail draft sent draft_id=%s for action_id=%s", draft_id, action_id)
    except HttpError as e:
        logger.exception("Gmail send draft failed")
        raise HandlerError(f"Gmail API error: {e}") from e
    
    return {
        "reply_message_id": response["id"],
        "thread_id": response["threadId"],
        "label_ids": response.get("labelIds", []),
    }


def delete_draft(draft_id: str) -> dict:
    """Delete a Gmail draft. Used when a SEND_REPLY action is rejected."""
    service = _get_resource()
    try:
        response = (
            service.users()
            .drafts()
            .delete(userId="me", id=draft_id).execute()
        )
        logger.info("Gmail draft deleted draft_id=%s", draft_id)
        return response
    except HttpError as e:
        # Don't raise — rejection should succeed even if cleanup fails
        logger.warning("Failed to delete draft_id=%s: %s", draft_id, e)
    
    return {
        "draft_id": draft_id,
        "status": "deleted"
    }