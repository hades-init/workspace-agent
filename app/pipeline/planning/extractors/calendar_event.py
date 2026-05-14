from functools import lru_cache
import logging

from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from pydantic import ValidationError

from app.core.models import Action, ActionStatus, ActionType, Message
from app.core.schemas import InterviewDetails
from app.pipeline.planning.extractors.base import ExtractionError
from app.utils.formatter import to_xml_string


logger = logging.getLogger("agent.extractors.calendar_event")

PROMPT = """
You are extracting structured details from an email that has already been classified as an interview invite.

# GOAL
You are given an email with a subject and a body. 
You goal is to extract interview details from an email so a calendar event can be created.

# WORKFLOW
1. Read the email carefully and extract each field defined in the response schema.
2. For fields not present in the email, use the default values (where defined) or None.
3. For `start_datetime` and `end_datetime`, normalize to ISO 8601 datetime format For example,
   - "Tuesday May 12 at 2 PM IST" -> "2026-05-12T14:00:00+05:30"
   - "May 12, 9-10am" -> start_time="2026-05-12T09:00:00" and end_time="2026-05-12T10:00:00"
   - Year is the current year or next occurrence of the date, if not stated.

# RULES
1. Extract only information that is **explicitly present** in the email. \
    Do not infer, guess, or use outside knowledge.
2. If multiple time slots are proposed (e.g. "Tuesday or Wednesday"), pick the LATEST proposed slot.
3. Treat the entire email body as a single source — do not assume that signature blocks contain interview details.
4. For `start_datetime` and `end_datetime` fields - do NOT include 'Z' or any other timezone suffix."
5. Use <received_date> to know the current year if not stated in email.

# CONSTRAINTS
- Strictly follow the response format.
- Do not summarize or paraphrase the email.
- Do not ask follow-up questions.
"""

@lru_cache(maxsize=1)
def _get_agent():
    """
    Build the information extraction agent lazily and cache it.
    """
    logger.info("Creating extraction agent for 'calendar_event' action")

    llm = init_chat_model(model="claude-sonnet-4-6")
    return create_agent(
        model=llm,
        system_prompt=PROMPT,
        response_format=InterviewDetails,
    )


def _run_extraction_agent(message: Message) -> dict:
    """Extract the necessary information from email message, 
    required to create a calendar event.

    Args
        message: en email of type `Message`

    Returns
        interview_details: a dict of type `InterviewDetails`
    """

    logger.debug("Extracting information from email id=%s", message.id)

    agent = _get_agent()
    input_message = to_xml_string(message)

    response = agent.invoke(
        {"messages": [HumanMessage(content=input_message)]}
    )

    logger.info(
        "Information extracted from email id=%s", message.id,
        extra={
            "agent": "calendar_event",
            "model_name": response["messages"][-1].response_metadata["model_name"],
            "email_id": message.id,
            "email_subject": message.subject, 
            "structured_response": response["structured_response"].model_dump(),
        }
    )
    
    structured_response = response["structured_response"]

    # try:
    #     # convert date from isoformat to naive format
    #     structured_response.start_datetime = structured_response.start_datetime.replace(tzinfo=None)
    #     structured_response.end_datetime = structured_response.end_datetime.replace(tzinfo=None)
    # except Exception as e:
    #     raise ExtractionError(f"Date conversion error for message_id={message.id}: {e}") from e
    
    return structured_response.model_dump(mode="json")


def create_action(message: Message):
    """
    Extract interview details from the email message
    and produce a CALENDAR_EVENT action.
    """

    try:
        payload = _run_extraction_agent(message)
        
    except ValidationError as e:
        raise ExtractionError(f"Extraction validation failed for message_id={message.id}: {e}") from e

    return Action(
        message_id=message.id,
        action_type=ActionType.CALENDAR_EVENT,
        status=ActionStatus.PENDING,
        payload=payload
    )

