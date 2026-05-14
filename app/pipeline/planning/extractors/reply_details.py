from functools import lru_cache
import logging

from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from pydantic import ValidationError

from app.core.models import Action, ActionStatus, ActionType, Message
from app.core.schemas import ReplyRequirements
from app.pipeline.planning.extractors.base import ExtractionError
from app.utils.formatter import to_xml_string


logger = logging.getLogger("agent.extractors.reply_details")


PROMPT = """
You are extracting structured details from an email that requires a reply from the recipient.

# GOAL
Identify the things or details the sender is asking for, so that a reply can be drafted later.

# WORKFLOW
1. Read the email carefully.
2. Enumerate every distinct ask the sender makes (e.g. "resume", "interview availability", "expected salary", "acknowledgment").
3. Identify which of these asks would naturally be answered with an attachment
   (For example, the ask "share your resume or CV" requires an attachment - "resume").
4. Capture the sender's tone and how urgent the message feels.

# RULES
1. Only include items the sender explicitly asked for. Do not invent asks.
2. Each item in `message_ask` should be a short, self-contained phrase(1-2 words).
3. `message_summary` msut be short and concise 1-2 sentence summary of the thread context.
4. If the email contains no clear ask, return an empty list for `message_ask`.

# CONSTRAINTS
- Strictly follow the response format.
- Do not paraphrase the email beyond `message_summary`.
- Do not ask follow-up questions.
"""

@lru_cache(maxsize=1)
def _get_agent():
    """
    Build the information extraction agent lazily and cache it.
    """
    logger.info("Creating extraction agent for reply requirments")

    llm = init_chat_model(model="claude-sonnet-4-6")
    return create_agent(
        model=llm,
        system_prompt=PROMPT,
        response_format=ReplyRequirements,
    )


def extract_requirements(message: Message) -> ReplyRequirements:
    """Run the extraction agent and return a validated `ReplyRequirements` object

    Args
        message: en email of type `Message`

    Returns
        reply_requirements: a dict of type `ReplyRequirements`
    """

    logger.debug("Extracting reply requirements from email id=%s", message.id)

    agent = _get_agent()
    input_message = to_xml_string(message)

    try: 
        response = agent.invoke(
            {"messages": [HumanMessage(content=input_message)]}
        )
    except ValidationError as e:
        raise ExtractionError(
            f"Reply-requirements extraction failed for message_id={message.id}: {e}"
        ) from e

    structured_response = response["structured_response"]

    logger.info(
        "Information extracted from email id=%s", message.id,
        extra={
            "agent": "reply_details",
            "model_name": response["messages"][-1].response_metadata["model_name"],
            "email_id": message.id,
            "email_subject": message.subject, 
            "structured_response": structured_response.model_dump(),
        }
    )
    
    return structured_response
