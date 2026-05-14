import logging
from typing import Dict, TypedDict, NotRequired
from functools import lru_cache
import re

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.google_auth import get_credentials
from app.core.config import settings
from app.core.schemas import InterviewDetails
from app.pipeline.execution.handlers.base import HandlerError


logger = logging.getLogger(__name__)


class EventTime(TypedDict):
    dateTime: str
    timeZone: str

class EventReminders(TypedDict):
    useDefault: bool

class EventSource(TypedDict):
    title: str

class CalendarEvent(TypedDict):
    summary: str
    start: EventTime
    end: EventTime
    description: NotRequired[str]
    location: NotRequired[str]
    reminders: NotRequired[EventReminders]


_pattern = r'[+-]\d{2}:\d{2}$'
re.compile(_pattern)


def _build_calendar_event(data: Dict, timezone=settings.DEFAULT_TIMEZONE) -> CalendarEvent:
    """Build a calendar event for Google Calendar API
    """
    
    calendar_event: CalendarEvent = {
        "summary": data["title"],
        "start": {"dateTime": data["start_datetime"], "timeZone": timezone},
        "end": {"dateTime": data["end_datetime"], "timeZone": timezone},
        "reminders": {"useDefault": True}
    }
    if data.get("description"):
        calendar_event["description"] = data["description"]
    if data.get("meeting_link"):
        calendar_event["location"] = data["meeting_link"]
    return calendar_event    



@lru_cache(maxsize=1)
def _get_resource():
    """Construct a Resource for interacting with Google Calendar API.
    """

    return build("calendar", "v3", credentials=get_credentials())



def create_event(data: Dict, **kwargs) -> Dict:
    """Create an event in a calendar.
    """
    action_id = kwargs.get("action_id")
    logger.debug("Creating calendar event for action_id=%s", action_id)

    service = _get_resource()
    try:
        event = _build_calendar_event(data)
        response = (
            service.events()
            .insert(
                calendarId='primary', body=event,
            )
            .execute()
        )
        
        logger.info("Calendar event created action_id=%s", action_id)

    except HttpError as e:
        logger.exception("Google Calendar event insert failed")
        raise HandlerError(f"Google Calendar API error: {e}") from e
    
    result = {
        "id": response["id"],
        "status": response["status"],
        "summary": response["summary"],
        "start": response["start"],
        "end": response["end"],
    }

    for k in ("htmlLink", "description", "location"):
        if k in response:
            result[k] = response[k]

    return result