from functools import lru_cache
import logging

from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from pydantic import ValidationError

from app.core.models import Action, ActionStatus, ActionType, Message
from app.core.schemas import ApplyDetails
from app.pipeline.planning.extractors.base import ExtractionError
from app.utils.formatter import to_xml_string


logger = logging.getLogger("agent.extractors.job_apply")


PROMPT = """
You are extracting structured details from an email that invites the recipient \
    to apply for a job (for example, recruiter outreach, job posting alerts).

# GOAL
You are given an email's subject and body. You goal is to extract the fields given in the response schema.

# RULES
1. Extract only information that is **explicitly present** in the email. \
    Do not infer, guess, or use outside knowledge.
2. If a field cannot be confidently determined from the email, leave it null. \
    Missing data is acceptable — but fabricated data is not.
3. For `company`:
   - Use the hiring company's name, not the sender's company (recruiters often work for agencies — extract the *hiring* company).
   - If the email is from a job platform (LinkedIn, Wellfound, Indeed), the platform is NOT the company.
4. For `role`:
   - Use the exact job title as stated in the email.
   - Do not add seniority levels or qualifiers that aren't present (e.g., don't add "Senior" if the email just says "Engineer").
5. For `apply_link`:
   - Prefer the most direct application URL (e.g., a job board listing, an "Apply now" button target).
   - If multiple job posting links exist, pick those which are most clearly tied to applying. 
   - Skip generic links (homepage, unsubscribe, application tracking link).
   - Preserve the URL exactly — do not shorten, normalize, or strip query parameters.
6. For `source_platform`:
   - Identify the platform that delivered or hosts the posting (LinkedIn, Wellfound, Indeed, Greenhouse, Lever, Instahyre, "direct recruiter outreach", etc.).
   - Leave null if unclear.

# CONSTRAINTS
- Do not summarize or paraphrase the email.
- Do not ask follow-up questions.
- Do not include reasoning in any field — fields hold facts, **not explanations**.
- If the email does not actually invite an application (it was misclassified), populate `company` and `role` with best-effort values and leave the rest null. \
    The classifier upstream is responsible for category accuracy; your job is extraction only.
"""

@lru_cache(maxsize=1)
def _get_agent():
    """
    Build the information extraction agent lazily and cache it.
    """
    logger.info("Creating extraction agent for 'job_apply' action")

    llm = init_chat_model(model="claude-sonnet-4-6")
    return create_agent(
        model=llm,
        system_prompt=PROMPT,
        response_format=ApplyDetails,
    )


def _run_extraction_agent(message: Message) -> dict:
    """Extract the necessary information from email message, 
    required to apply for job.

    Args
        message: en email of type `Message`

    Returns
        apply_details: an dict of type `AppylDetails`
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
            "agent": "job_apply",
            "model_name": response["messages"][-1].response_metadata["model_name"],
            "email_id": message.id,
            "email_subject": message.subject, 
            "structured_response": response["structured_response"].model_dump(),
        }
    )
    
    return response["structured_response"].model_dump()


def create_action(message: Message):
    """
    Extract job details from the email message
    and produce a JOB_APPLY action.
    """

    try:
        payload = _run_extraction_agent(message)
        
    except ValidationError as e:
        raise ExtractionError(f"Extraction validation failed for message_id=%s: {e}") from e

    return Action(
        message_id=message.id,
        action_type=ActionType.JOB_APPLY,
        status=ActionStatus.PENDING,
        payload=payload
    )