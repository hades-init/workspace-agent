from typing import Literal
import logging
from functools import lru_cache

from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain.messages import HumanMessage

from app.core.models import Message
from app.utils.formatter import to_xml_string


logger = logging.getLogger("agent.classification")


# Field names match `Message` model columns so we can splat directly onto the row.
class EmailCategory(BaseModel):
    category: Literal['apply', 'interview', 'reply_needed', 'ignore']
    confidence_score: float
    model_reasoning: str


PROMPT = """
## GOAL
You are classifying a job-related email across the following categories:
- `apply`: invites you to apply for a role (for example, recruiter outreach, job posting alerts)
- `interview`: schedules or proposes an interview time
- `reply_needed`: asks you for information (for example, resume, interview availability, answers)
- `ignore`: anything else (rejections, newsletters, generic updates)

## WORKFLOW
1. Classify the email based on the subject and body of the email
2. Provide a confidence score between 0.0 and 1.0
3. Provide a short one-sentence reasoning about why it was classified in that category.
4. Using the reasoning and confidence score, validate the classification of the email
5. Use the response schema to generate and structure your response.

## RULES
1. If multiple categories apply, pick the most actionable one. 
2. Use `ignore` if unsure.
3. Strictly follow the response format for output.
4. Do not ask follow up questions.
"""


# Lazy cached factory (a lazy singleton)
@lru_cache(maxsize=1)
def _get_agent():
    """
    Build the classification agent lazily and cache it 

    Why lazy evaluation - importing this module doesn't require 
    ANTHROPIC_API_KEY to be set (e.g. during tests, schema migrations).
    
    Why caching - we build it only once per process.
    """
    logger.info("Creating agent for classification")

    llm = init_chat_model(model="claude-haiku-4-5")
    return create_agent(
        model=llm,
        system_prompt=PROMPT,
        response_format=EmailCategory,
    )


def classify_email(message: Message) -> EmailCategory:
    """Classify of email across the following 
    categories - {'apply', 'interview', 'reply_needed', 'ignore'}

    Args
        email: email message

    Returns
        output: `EmailCategory` object - pydantic model with 
                attributes 'category', 'confidence_score' and 'model_reasoning' 
    """
    logger.debug("Classifying email with id=%s", message.id)
    
    input_message = to_xml_string(message)
    agent = _get_agent()

    response = agent.invoke(
        {"messages": [HumanMessage(content=input_message)]},
    )

    logger.info(
        "Email classified id=%s", message.id,
        extra={
            "agent": "classify_email",
            "model_name": response["messages"][-1].response_metadata["model_name"],
            "email_id": message.id,
            "email_subject": message.subject, 
            "structured_response": response["structured_response"].model_dump(),
        }
    )
    
    return response["structured_response"]