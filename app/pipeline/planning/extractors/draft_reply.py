from functools import lru_cache
import logging

from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from pydantic import ValidationError

from app.core.models import Action, ActionStatus, ActionType, Message
from app.core.profile import UserProfile, get_profile
from app.core.schemas import EmailDraft, ReplyRequirements 
from app.pipeline.planning.extractors import reply_details
from app.pipeline.planning.extractors.base import ExtractionError
from app.utils.formatter import to_xml_string


logger = logging.getLogger("agent.extractors.draft_reply")


PROMPT = """
You are drafting a reply email on the user's behalf. The draft will be reviewed and edited \
    by the user before sending — your job is to produce a strong starting point, not a final message.

# GOAL
Given the original email, an extracted list of what was asked, and the user's profile, draft a concise plain-text reply.

# WORKFLOW
1. Read the original email and the list of asks from the sender.
2. Address every ask, in the order they are asked in the original email.
3. Use information from <user_profile> when it directly answers an ask.
4. For asks you cannot answer from the <user_profile>, insert a placeholder like [INSERT AVAILABILITY HERE] or [CONFIRM SALARY EXPECTATIONS].
5. Reference attachments naturally (e.g. "I've attached my resume").
6. Match the requested tone of the email.

# RULES
1. NEVER fabricate facts about the user. If the profile doesn't say it, use a placeholder.
2. NEVER commit to a specific time for availability. Hedge or use placeholder instead.
3. Keep the body to 3-6 sentences. Recruiter replies should be short and concise.
4. Always end with the signature from <user_profile><signature>.
5. `subject` must be the original subject prefixed with "Re: " (only once).
6. `to_address` is taken verbatim from the email's <from_address>.
7. `attachments_to_include` must only contain names that appear in <user_profile><attachments>.

# CONSTRAINTS
- Strictly follow the response format.
- Do not include greetings like "Hope you're well" unless the original email was casual.
- Do not ask follow-up questions of the user.
"""

@lru_cache(maxsize=1)
def _get_agent():
    """
    Build the email drafter agent lazily and cache it.
    """
    logger.info("Creating email drafter agent for 'send_reply' action")

    llm = init_chat_model(model="claude-sonnet-4-6")
    return create_agent(
        model=llm,
        system_prompt=PROMPT,
        response_format=EmailDraft,
    )


def _format_drafter_input(
        message: Message, 
        requirements: ReplyRequirements, 
        profile: UserProfile
) -> str:
    """Build an XML style string human message for the drafter agent input"""

    attachments_xml = "\n".join(
        f"  <attachment name=\"{name}\" />"
        for name in profile.attachments
    )

    return f"""\
<email>
  <from_address>{message.from_address}</from_address>
  <subject>{message.subject}</subject>
  <body>{message.body_markdown}</body>
</email>

<reply_requirements>
  <summary>{requirements.message_summary}</summary>
  <asks>
{chr(10).join(f"    <ask>{a}</ask>" for a in requirements.message_ask)}
  </asks>
  <tone>{requirements.tone}</tone>
  <urgency>{requirements.urgency}</urgency>
  <suggested_attachments>
{chr(10).join(f"    <attachment>{a}</attachment>" for a in (requirements.suggested_attachments or []))}
  </suggested_attachments>
</reply_requirements>

<user_profile>
  <name>{profile.name}</name>
  <current_role>{profile.current_role or ""}</current_role>
  <years_experience>{profile.years_experience}</years_experience>
  <notice_period>{profile.notice_period}</notice_period>
  <current_salary>{profile.current_salary or ""}</current_salary>
  <expected_salary>{profile.expected_salary or ""}</expected_salary>
  <availability>{profile.availability or ""}</availability>
  <tone>{profile.tone}</tone>
  <signature>{profile.signature}</signature>
  <attachments>
{attachments_xml}
  </attachments>
</user_profile>
"""
    

def _draft_reply_email(
        message: Message, 
        requirements: ReplyRequirements,
        profile: UserProfile) -> EmailDraft:
    """Draft an email message

    Args
        message: en email of type `Message`

    Returns
        draft_email: a dict of type `EmailDraft`
    """

    logger.debug("Drafting a reply for email id=%s", message.id)

    agent = _get_agent()
    input_message = _format_drafter_input(message, requirements, profile)

    try:
        response = agent.invoke(
            {"messages": [HumanMessage(content=input_message)]}
        )
    except ValidationError as e:
        raise ExtractionError(f"Drafting failed for message_id={message.id}: {e}") from e
    
    structured_response = response["structured_response"]
    
    logger.info(
        "Reply drafted for message_id=%s", message.id,
        extra={
            "agent": "draft_email",
            "model_name": response["messages"][-1].response_metadata["model_name"],
            "email_id": message.id,
            "email_subject": message.subject, 
            "structured_response": structured_response.model_dump(),
        }
    )
    
    return structured_response


def create_action(message: Message):
    """Extract reply requirements, draft a reply, and produce a SEND_REPLY action.
    """
    profile = get_profile()
    requirements = reply_details.extract_requirements(message)

    draft_email = _draft_reply_email(message, requirements, profile)

    payload = {
        "message_id": message.id,
        "thread_id": message.thread_id,
        **draft_email.model_dump(mode="json"),
    }

    return Action(
        message_id=message.id,
        action_type=ActionType.SEND_REPLY,
        status=ActionStatus.PENDING,
        payload=payload
    )
