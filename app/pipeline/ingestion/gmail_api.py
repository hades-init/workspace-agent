from typing import Dict, List, Any
import logging
from functools import lru_cache

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.google_auth import get_credentials


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_service():
    """Construct a Resource for interacting with Gmail API.
    """

    return build("gmail", "v1", credentials=get_credentials())


query = "is:unread (subject:(interview OR opportunity OR application OR role OR job))"    # newer_than:2d 

def fetch_email_list() -> List[Dict[str, Any]]:
    """
    Fetch latest unread email messages from mailbox.
    """
    logger.info("Fetching latest messages list from Gmail servers")
    try:
        service = _get_service()
        results = service.users().messages().list(
            userId="me", labelIds=["INBOX"], q="is:unread",
        ).execute()
        messages = results.get("messages", [])
        return messages

    except HttpError:
        logger.exception("fetch_email_list failed")
        raise



def fetch_email(id: str) -> Dict[str, Any]:
    """
    Fetch specific email by id
    """
    try:
        logger.debug("Fetching email id=%s from Gmail servers", id)
        service = _get_service()
        result = service.users().messages().get(userId="me", id=id).execute()
        return result
    
    except HttpError:
        logger.exception("fetch_email failed for email id=%s", id)
        raise


if __name__ == "__main__":
	pass