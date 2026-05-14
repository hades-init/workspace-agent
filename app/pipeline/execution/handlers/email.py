import logging
import base64
from pathlib import Path
from functools import lru_cache
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.google_auth import get_credentials
from app.core.profile import get_profile
from app.pipeline.execution.handlers.base import HandlerError


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_resource():
    """Construct a Resource for interacting with Gmail API.
    """
    return build("gmail", "v1", credentials=get_credentials())


def _build_mime_message(data: dict) -> MIMEMultipart:
    """Build an RFC 2822 MIME message from the drafter's payload."""
    profile = get_profile()

    mime = MIMEMultipart()
    mime["To"] = data["to_address"]
    mime["Subject"] = data["subject"]

    # Body
    mime.attach(MIMEText(data["reply_body"], "plain"))

    # Attachments — look up file path from profile
    for name in data.get("attachments_to_include") or []:
        file_path = profile.attachments.get(name)
        if not file_path:
            logger.warning(
                "Drafter requested attachment '%s' not in profile; skipping",
                name,
            )
            continue

        path = Path(file_path)
        if not path.exists():
            logger.warning(
                "Attachment file not found at %s; skipping", file_path
            )
            continue

        with path.open("rb") as f:
            part = MIMEApplication(f.read(), Name=path.name)
        part["Content-Disposition"] = f'attachment; filename="{path.name}"'
        mime.attach(part)

    return mime


def _build_draft_body(data: dict) -> dict:
    """Wrap a MIME message into the Gmail drafts.create API request body"""
    mime = _build_mime_message(data)
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("utf-8")

    body = {
        "message": {
            "raw": raw,
            "threadId": data["thread_id"]
        }
    }

    return body


def create_draft(data: dict, **kwargs) -> dict:
    """Create a draft with the `DRAFT` label in the mailbox
    """
    action_id = kwargs.get("action_id")
    logger.debug("Creating draft email for action_id=%s", action_id)

    service = _get_resource()
    try:
        body = _build_draft_body(data)
        response = (
            service.users()
            .drafts()
            .create(userId="me", body=body)
            .execute()
        )

        logger.info("Gmail draft created action_id=%s", action_id)
    except HttpError as e:
        logger.exception("Gmail create draft failed")
        raise HandlerError(f"Gmail API error: {e}") from e
    
    return {
        "draft_id": response["id"],
        "message": response["message"]
    }
